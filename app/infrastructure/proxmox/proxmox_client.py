import logging
import time
from urllib.parse import quote

from proxmoxer import ProxmoxAPI

from app.core.config import get_settings
from app.infrastructure.proxmox.ip_utils import pick_guest_ipv4

logger = logging.getLogger(__name__)
settings = get_settings()


class ProxmoxIntegrationError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ProxmoxClient:
    def __init__(self) -> None:
        self.enabled = settings.proxmox_enabled
        if not self.enabled:
            self.api = None
            return

        try:
            self.api = ProxmoxAPI(
                settings.proxmox_host,
                user=settings.proxmox_user,
                token_name=settings.proxmox_token_id,
                token_value=settings.proxmox_token_secret,
                verify_ssl=settings.proxmox_verify_ssl,
                timeout=120,
            )
        except Exception as e:
            raise ProxmoxIntegrationError(
                f"Erreur de connexion à Proxmox: {e}", 500) from e

    def create_vm_from_template(
        self,
        node: str,
        template_vmid: int,
        new_vmid: int,
        name: str,
        memory_mb: int,
        cores: int,
        net0: str,
        ssh_key: str | None = None,
    ) -> dict:
        if not self.enabled or self.api is None:
            return {"vmid": new_vmid, "status": "created"}

        full = settings.proxmox_clone_full
        clone_args: dict = {
            "newid": new_vmid,
            "name": name,
            "full": 1 if full else 0,
            "target": node,
        }
        # Un clone complet doit indiquer un storage de destination ; un clone
        # lié (full=0) ne l'accepte pas et reste sur le storage du template.
        if full and settings.proxmox_vm_storage:
            clone_args["storage"] = settings.proxmox_vm_storage

        try:
            upid = self.api.nodes(node).qemu(template_vmid).clone.post(**clone_args)
            # Le clonage est asynchrone : la VM est verrouillée tant que la tâche
            # n'est pas terminée, donc la configuration échouerait sans attente.
            self._wait_for_task(node, upid, settings.proxmox_clone_timeout)

            update_data: dict = {"memory": memory_mb,
                                 "cores": cores, "net0": net0}
            if ssh_key:
                # Proxmox attend une clé SSH URL-encodée (sinon « invalid
                # urlencoded string »). proxmoxer n'encode pas ce champ.
                update_data["sshkeys"] = quote(ssh_key.strip(), safe="")
            # PUT (synchrone) et non POST : sur une VM fraîchement clonée, le
            # POST place les changements matériels en « pending » sans les
            # appliquer ; le PUT les applique immédiatement.
            self.api.nodes(node).qemu(new_vmid).config.put(**update_data)
            return {"vmid": new_vmid, "status": "created"}
        except ProxmoxIntegrationError:
            raise
        except Exception as e:
            raise ProxmoxIntegrationError(
                f"Erreur lors du clonage de la VM: {e}", 502) from e

    def _wait_for_task(self, node: str, upid: object, timeout: int) -> None:
        """Attend la fin d'une tâche Proxmox (UPID) et vérifie son succès."""
        if not upid or self.api is None:
            return
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = self.api.nodes(node).tasks(upid).status.get()
            if status.get("status") == "stopped":
                exit_status = status.get("exitstatus")
                if exit_status not in ("OK", None):
                    raise ProxmoxIntegrationError(
                        f"Tâche Proxmox échouée ({upid}): {exit_status}", 502)
                return
            time.sleep(2)
        raise ProxmoxIntegrationError(
            f"Délai dépassé en attendant la tâche Proxmox {upid}", 504)

    def get_vm_ip_address(self, node: str, vmid: int, timeout: int | None = None) -> str | None:
        """Interroge qemu-guest-agent jusqu'à obtenir une IPv4 (DHCP/cloud-init)."""
        if not self.enabled or self.api is None:
            return None
        poll_timeout = timeout if timeout is not None else settings.proxmox_ip_poll_timeout
        deadline = time.monotonic() + poll_timeout
        while time.monotonic() < deadline:
            try:
                data = self.api.nodes(node).qemu(vmid).agent("network-get-interfaces").get()
                ip = pick_guest_ipv4(data.get("result") or [])
                if ip:
                    return ip
            except Exception:
                pass
            time.sleep(3)
        return None

    def start_vm(self, node: str, vmid: int) -> None:
        if not self.enabled or self.api is None:
            return
        try:
            self.api.nodes(node).qemu(vmid).status.start.post()
        except Exception as e:
            raise ProxmoxIntegrationError(
                f"Erreur lors du démarrage de la VM: {e}", 502) from e

    def stop_vm(self, node: str, vmid: int, wait: bool = False) -> None:
        if not self.enabled or self.api is None:
            return
        try:
            upid = self.api.nodes(node).qemu(vmid).status.stop.post()
            if wait:
                self._wait_for_task(node, upid, 60)
        except Exception as e:
            raise ProxmoxIntegrationError(
                f"Erreur lors de l'arrêt de la VM: {e}", 502) from e

    def delete_vm(self, node: str, vmid: int) -> None:
        if not self.enabled or self.api is None:
            return
        try:
            # L'arrêt est asynchrone : on attend qu'il se termine, sinon la
            # suppression échoue avec « VM is running ».
            try:
                self.stop_vm(node, vmid, wait=True)
            except Exception:
                pass
            self.api.nodes(node).qemu(vmid).delete(purge=1)
        except Exception as e:
            raise ProxmoxIntegrationError(
                f"Erreur lors de la suppression de la VM: {e}", 502) from e

    def get_vm_status(self, node: str, vmid: int) -> dict:
        if not self.enabled or self.api is None:
            return {}
        try:
            return self.api.nodes(node).qemu(vmid).status.current.get()
        except Exception as e:
            raise ProxmoxIntegrationError(
                f"Erreur lors de la récupération du statut: {e}", 502) from e

    def get_next_vmid(self) -> int:
        start = settings.proxmox_vmid_range_start
        end = settings.proxmox_vmid_range_end
        if not self.enabled or self.api is None:
            return start or 100
        try:
            # Sans plage configurée, on délègue à Proxmox (prochain ID global).
            if not (start and end):
                return int(self.api.cluster.nextid.get())
            used = {
                int(r["vmid"])
                for r in self.api.cluster.resources.get(type="vm")
                if r.get("vmid") is not None
            }
            for vmid in range(start, end + 1):
                if vmid not in used:
                    return vmid
            raise ProxmoxIntegrationError(
                f"Aucun VMID libre dans la plage {start}-{end}", 507)
        except ProxmoxIntegrationError:
            raise
        except Exception as e:
            raise ProxmoxIntegrationError(
                f"Impossible d'obtenir le prochain VMID: {e}") from e

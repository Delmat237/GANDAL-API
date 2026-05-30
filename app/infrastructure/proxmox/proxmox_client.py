import logging

from proxmoxer import ProxmoxAPI

from app.core.config import get_settings

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

        try:
            self.api.nodes(node).qemu(template_vmid).clone.post(
                newid=new_vmid,
                name=name,
                full=1,
                target=node,
            )
            update_data: dict = {"memory": memory_mb,
                                 "cores": cores, "net0": net0}
            if ssh_key:
                update_data["sshkeys"] = ssh_key
            self.api.nodes(node).qemu(new_vmid).config.post(**update_data)
            return {"vmid": new_vmid, "status": "created"}
        except Exception as e:
            raise ProxmoxIntegrationError(
                f"Erreur lors du clonage de la VM: {e}", 502) from e

    def start_vm(self, node: str, vmid: int) -> None:
        if not self.enabled or self.api is None:
            return
        try:
            self.api.nodes(node).qemu(vmid).status.start.post()
        except Exception as e:
            raise ProxmoxIntegrationError(
                f"Erreur lors du démarrage de la VM: {e}", 502) from e

    def stop_vm(self, node: str, vmid: int) -> None:
        if not self.enabled or self.api is None:
            return
        try:
            self.api.nodes(node).qemu(vmid).status.stop.post()
        except Exception as e:
            raise ProxmoxIntegrationError(
                f"Erreur lors de l'arrêt de la VM: {e}", 502) from e

    def delete_vm(self, node: str, vmid: int) -> None:
        if not self.enabled or self.api is None:
            return
        try:
            try:
                self.stop_vm(node, vmid)
            except Exception:
                pass
            self.api.nodes(node).qemu(vmid).delete()
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
        if not self.enabled or self.api is None:
            return 100
        try:
            return self.api.cluster.nextid.get()
        except Exception as e:
            raise ProxmoxIntegrationError(
                f"Impossible d'obtenir le prochain VMID: {e}") from e

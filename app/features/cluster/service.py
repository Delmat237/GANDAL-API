"""Service du plan de contrôle cluster : agrège topologie + RBAC + persistance des liens.

Le gateway fournit la réalité cluster (VMs, internet, distribution) ; ce service y greffe
la propriété (DB), filtre selon le rôle, et persiste les arêtes réseau (NetworkLink).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.shared.models import NetworkLink, User, VM
from app.shared.policies.permissions import AuthorizationPolicy

from .schemas import TopologyLink, TopologyResponse, TopologyVM


class ClusterService:
    def __init__(self, db: Session, gateway) -> None:
        self.db = db
        self.gw = gateway

    # ── Topologie pour la toile ──────────────────────────────────────────────
    def topology(self, only_owner_id: int | None = None) -> TopologyResponse:
        data = _safe(lambda: self.gw.topology(), {"hosts": [], "vms": []})

        # Mapping vmid → (owner_id, owner_name) depuis la DB.
        owners: dict[int, tuple[int, str]] = {}
        for vm, username in (
            self.db.query(VM, User.username).join(User, VM.user_id == User.id).all()
        ):
            if vm.id_proxmox is not None:
                owners[vm.id_proxmox] = (vm.user_id, username)

        vms: list[TopologyVM] = []
        visible_vmids: set[int] = set()
        for v in data.get("vms", []):
            vmid = v["vmid"]
            owner = owners.get(vmid)
            if only_owner_id is not None and (owner is None or owner[0] != only_owner_id):
                continue  # étudiant : ne voit que ses VMs
            visible_vmids.add(vmid)
            vms.append(TopologyVM(
                vmid=vmid, name=v.get("name"), node=v.get("node"),
                status=v.get("status", "stopped"), ip=v.get("ip"),
                internet=v.get("internet", False), maxcpu=v.get("maxcpu"),
                maxmem=v.get("maxmem"), vram_mib=v.get("vram_mib", 0),
                owner_id=owner[0] if owner else None,
                owner_name=owner[1] if owner else None,
            ))

        # Arêtes : liens réseau persistés, restreints aux VMs visibles.
        links: list[TopologyLink] = []
        for link in self.db.query(NetworkLink).all():
            if only_owner_id is not None and not (
                link.vmid_a in visible_vmids and link.vmid_b in visible_vmids
            ):
                continue
            links.append(TopologyLink(source=link.vmid_a, target=link.vmid_b,
                                      group_name=link.group_name))

        hosts = data.get("hosts", [])
        return TopologyResponse(hosts=hosts, vms=vms, links=links)

    # ── Distribution / réconciliation ────────────────────────────────────────
    def distribution(self) -> list[dict]:
        return _safe(lambda: self.gw.distribution_status(), [])

    def reconcile(self) -> bool:
        return _safe(lambda: self.gw.reconcile_now(), False)

    def gpu_status(self) -> list[dict]:
        return _safe(lambda: self.gw.gpu_status(), [])

    def migrations(self) -> list[dict]:
        return _safe(lambda: self.gw.migrations(), [])

    # ── Actions (RBAC + script + persistance) ────────────────────────────────
    def _vm_by_vmid(self, vmid: int) -> VM | None:
        return self.db.query(VM).filter(VM.id_proxmox == vmid).first()

    def _ensure_can_manage_vmid(self, user: User, vmid: int) -> VM | None:
        """Autorise l'action sur la VM.

        - admin/enseignant : peut gérer N'IMPORTE QUELLE VM omega du cluster (même
          celles non enregistrées dans l'app — VMs préexistantes du cluster).
        - étudiant : uniquement SES VMs enregistrées dans la base.
        """
        vm = self._vm_by_vmid(vmid)
        if AuthorizationPolicy.is_admin_or_superadmin(user) or _is_teacher(user):
            return vm  # peut être None (VM cluster hors app) → autorisé pour l'admin
        if vm is None:
            raise NotFoundError(f"VM {vmid} inconnue dans l'inventaire")
        if not AuthorizationPolicy.can_manage_vm(user, vm):
            raise ForbiddenError("Vous n'avez pas les droits sur cette VM.")
        return vm

    def create_vm(self, user: User, *, name: str | None, vcpu: int, ram_gb: int,
                  disk_gb: int, vram_gb: int, internet: bool, autostart: bool) -> dict:
        """Crée et provisionne une VM directement (bouton « + »).

        La VM est enregistrée pour le propriétaire (user), puis provisionnée en tâche de
        fond. Options post-provision (GPU/internet/always-on) appliquées à la fin.
        """
        from app.shared.models import VM as _VM
        from app.shared.policies.states import VMStatePolicy

        # Réserve le VMID DÈS MAINTENANT (cluster + VMIDs déjà réservés en base) pour
        # éviter que deux créations concurrentes prennent le même → l'enregistre
        # immédiatement (id_proxmox) ce qui fixe aussi le mapping propriétaire.
        reserved = {v.id_proxmox for v in self.db.query(_VM).all() if v.id_proxmox}
        vmid = self.gw.reserve_vmid(exclude=reserved)

        vm = _VM(size_rom=disk_gb, size_ram=ram_gb, n_cpu=vcpu, iso="debian12",
                 iso_image="debian12", status=VMStatePolicy.WAITING,
                 id_proxmox=vmid, ssh_public_key="", user_id=user.id)
        self.db.add(vm)
        self.db.commit()
        self.db.refresh(vm)

        _provision_vm_async(
            vm_id=vm.id, vmid=vmid, name=name or f"omega-vm-{vm.id}", ram_gb=float(ram_gb),
            vcpu=vcpu, vram_gb=vram_gb, internet=internet, autostart=autostart)
        return {"vm_id": vm.id, "vmid": vmid, "status": "provisioning"}

    def set_internet(self, user: User, vmid: int, enable: bool) -> dict:
        self._ensure_can_manage_vmid(user, vmid)
        self.gw.set_internet(vmid, enable)
        return {"vmid": vmid, "internet": enable}

    def set_llm_access(self, user: User, vmid: int, enable: bool) -> dict:
        self._ensure_can_manage_vmid(user, vmid)
        self.gw.set_llm_access(vmid, enable)
        return {"vmid": vmid, "llm_access": enable}

    def reconcile_llm_access(self, prune: bool = False) -> dict:
        """Réconcilie l'accès LLM de TOUTES les VMs (vram>0 → accès). Admin."""
        return self.gw.reconcile_llm_access(prune=prune)

    def reconfigure(self, user: User, vmid: int, **kw) -> dict:
        self._ensure_can_manage_vmid(user, vmid)
        return self.gw.reconfigure_vm(vmid, **kw)

    def set_gpu(self, user: User, vmid: int, vram_mib: int) -> dict:
        self._ensure_can_manage_vmid(user, vmid)
        return self.gw.set_gpu(vmid, vram_mib)

    def set_autostart(self, user: User, vmid: int, enable: bool) -> dict:
        self._ensure_can_manage_vmid(user, vmid)
        return self.gw.set_autostart(vmid, enable)

    def dns_register(self, user: User, vmid: int, hostname: str | None) -> dict:
        self._ensure_can_manage_vmid(user, vmid)
        return self.gw.dns_register(vmid, hostname)

    def expose_service(self, user: User, vmid: int, **kw) -> dict:
        self._ensure_can_manage_vmid(user, vmid)
        return self.gw.expose_service(vmid, **kw)

    def add_domain(self, user: User, vmid: int, hostname: str, port: int,
                   enable: bool) -> dict:
        self._ensure_can_manage_vmid(user, vmid)
        return self.gw.add_domain(vmid, hostname, port, enable)

    def delete_vm(self, user: User, vmid: int) -> None:
        vm = self._ensure_can_manage_vmid(user, vmid)
        self.gw.destroy_vm(vmid)
        if vm is not None:
            self.db.delete(vm)
            self.db.commit()

    def lifecycle(self, user: User, vmid: int, action: str) -> dict:
        """Démarre/arrête une VM par VMID (le gateway résout le nœud-hôte)."""
        self._ensure_can_manage_vmid(user, vmid)
        if action == "start":
            self.gw.start_vm("", vmid)
        elif action == "stop":
            self.gw.stop_vm("", vmid)
        else:
            raise ForbiddenError(f"Action inconnue : {action}")
        return {"vmid": vmid, "action": action}

    def link(self, user: User, vmids: list[int], enable: bool,
             group_name: str | None) -> dict:
        if len(vmids) < 2:
            raise ForbiddenError("Au moins deux VMs sont requises pour un lien.")
        for vmid in vmids:
            self._ensure_can_manage_vmid(user, vmid)
        self.gw.link_vms(vmids, enable, group_name)
        # Persiste/retire les arêtes (maillage complet du groupe).
        pairs = [(a, b) for i, a in enumerate(vmids) for b in vmids[i + 1:]]
        if enable:
            for a, b in pairs:
                if not self._link_exists(a, b):
                    self.db.add(NetworkLink(vmid_a=a, vmid_b=b, group_name=group_name))
        else:
            for a, b in pairs:
                for link in self._find_links(a, b):
                    self.db.delete(link)
        self.db.commit()
        return {"vm_ids": vmids, "enabled": enable, "group_name": group_name}

    def _find_links(self, a: int, b: int) -> list[NetworkLink]:
        q = self.db.query(NetworkLink).filter(
            ((NetworkLink.vmid_a == a) & (NetworkLink.vmid_b == b))
            | ((NetworkLink.vmid_a == b) & (NetworkLink.vmid_b == a))
        )
        return list(q.all())

    def _link_exists(self, a: int, b: int) -> bool:
        return bool(self._find_links(a, b))


def _safe(fn, default):
    """Exécute une lecture cluster, renvoie default si le cluster est injoignable."""
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return default


def _is_teacher(user: User) -> bool:
    from app.shared.models import Teacher
    return isinstance(user, Teacher)


def _provision_vm_async(vm_id: int, vmid: int, name: str, ram_gb: float, vcpu: int,
                        vram_gb: int, internet: bool, autostart: bool) -> None:
    """Provisionne une VM (VMID réservé) en arrière-plan puis applique GPU/internet/always-on."""
    import logging
    import threading

    from app.infrastructure import factories
    from app.shared.policies.states import VMStatePolicy

    log = logging.getLogger(__name__)

    def _run() -> None:
        from app.core.database import SessionLocal
        gw = factories.get_proxmox_gateway()
        try:
            result = gw.provision_new_vm(name=name, template_vmid=9001, ram_gb=ram_gb,
                                         vcpu=vcpu, ssh_pub_key="", vlan_id=30, vmid=vmid)
        except Exception:  # noqa: BLE001
            log.exception("Création VM %s : provisionnement échoué", vm_id)
            # On laisse l'enregistrement (id_proxmox réservé) ; statut erreur.
            db = SessionLocal()
            try:
                vm = db.get(VM, vm_id)
                if vm:
                    vm.status = "stopped"
                    db.commit()
            finally:
                db.close()
            return
        db = SessionLocal()
        try:
            vm = db.get(VM, vm_id)
            if vm:
                vm.id_proxmox = result.vmid
                vm.node = result.node
                vm.status = VMStatePolicy.UP
                db.commit()
        finally:
            db.close()
        # Options post-provision (best-effort, n'échouent pas la création).
        for opt, fn in (
            (vram_gb > 0, lambda: gw.set_gpu(result.vmid, vram_gb * 1024)),
            (internet, lambda: gw.set_internet(result.vmid, True)),
            (autostart, lambda: gw.set_autostart(result.vmid, True)),
        ):
            if opt:
                try:
                    fn()
                except Exception:  # noqa: BLE001
                    log.warning("Option post-provision échouée pour VM %s", vm_id)

    threading.Thread(target=_run, daemon=True).start()

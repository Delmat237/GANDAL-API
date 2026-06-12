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
                maxmem=v.get("maxmem"),
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

    def _ensure_can_manage_vmid(self, user: User, vmid: int) -> VM:
        vm = self._vm_by_vmid(vmid)
        if vm is None:
            raise NotFoundError(f"VM {vmid} inconnue dans l'inventaire")
        if not AuthorizationPolicy.can_manage_vm(user, vm):
            raise ForbiddenError("Vous n'avez pas les droits sur cette VM.")
        return vm

    def set_internet(self, user: User, vmid: int, enable: bool) -> dict:
        self._ensure_can_manage_vmid(user, vmid)
        self.gw.set_internet(vmid, enable)
        return {"vmid": vmid, "internet": enable}

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

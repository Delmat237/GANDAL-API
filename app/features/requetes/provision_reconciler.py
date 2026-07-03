"""Réconciliateur de provisioning AUTOMATIQUE.

Tâche de fond permanente (thread démon démarré au lancement de l'API) qui repère les VMs
restées bloquées en `waiting` (provisioning jamais abouti — drop SSH, congestion, etc.) et
les re-provisionne TOUTE SEULE, sans intervention. C'est le filet d'auto-guérison : une
approbation dont le provisioning échoue finit toujours par aboutir au tick suivant.

Garde-fou anti-doublon : on ne touche qu'aux VMs `waiting` SANS vmid et créées depuis plus
de `grace` (défaut 3 min), pour ne jamais entrer en concurrence avec un provisioning en
cours (qui, lui, vient d'être lancé et a < 3 min). La boucle est séquentielle (pas de
chevauchement) et le gateway retente déjà les drops SSH transitoires.
"""
from __future__ import annotations

import logging
import threading
import time

from app.features.requetes import provision_state

logger = logging.getLogger(__name__)


def _reconcile_once() -> None:
    from app.core.database import SessionLocal
    from app.infrastructure import factories
    from app.shared.models import Student, VM
    from app.shared.policies.states import VMStatePolicy

    db = SessionLocal()
    try:
        # En cours de provisioning (approbation fraîche) → on NE TOUCHE PAS (anti-doublon).
        busy = provision_state.snapshot()
        stuck = [
            vm for vm in db.query(VM)
            .filter(VM.status == VMStatePolicy.WAITING, VM.id_proxmox.is_(None))
            .all()
            if vm.id not in busy
        ]
        if not stuck:
            return
        logger.info("auto-reprovision : %d VM(s) bloquée(s) en waiting", len(stuck))
        gw = factories.get_proxmox_gateway()
        # VMID déjà pris en base → exclus de l'allocation (le gateway y ajoute
        # cluster + registre en-vol sous verrou). On enrichit au fil des créations.
        used = {v for (v,) in db.query(VM.id_proxmox).filter(VM.id_proxmox.isnot(None)).all()}
        for vm in stuck:
            provision_state.mark(vm.id)
            student = db.get(Student, vm.user_id)
            matricule = getattr(student, "matricule", None) if student else None
            name = f"vm-{matricule}-{vm.id}" if matricule else f"omega-{vm.id}"
            dept = (getattr(student, "departement", "") if student else "") or "GI"
            try:
                res = gw.provision_new_vm(
                    name=name, template_vmid=9001,
                    ram_gb=float(vm.size_ram), vcpu=vm.n_cpu or 2,
                    disk_gb=int(vm.size_rom or 20),
                    ssh_pub_key=vm.ssh_public_key or "", vlan_id=30,
                    exclude_vmids=used,
                )
                vm.id_proxmox = res.vmid
                vm.node = res.node
                vm.status = VMStatePolicy.UP
                db.commit()
                used.add(res.vmid)
                logger.info("auto-reprovision VM %s → vmid=%s node=%s",
                            vm.id, res.vmid, res.node)
            except Exception:  # noqa: BLE001
                db.rollback()
                logger.warning("auto-reprovision VM %s échouée — réessai au prochain tick",
                               vm.id)
            finally:
                provision_state.unmark(vm.id)
    finally:
        db.close()


def start_provision_reconciler() -> None:
    """Démarre la boucle de réconciliation en thread démon (au démarrage de l'API)."""
    from app.core.config import get_settings

    s = get_settings()
    if getattr(s, "proxmox_simulation_mode", False):
        logger.info("réconciliateur provisioning désactivé (mode simulation)")
        return
    interval = int(getattr(s, "provision_reconcile_interval_secs", 120) or 120)

    def _loop() -> None:
        logger.info("réconciliateur provisioning actif (intervalle=%ss)", interval)
        # petit délai initial : laisse les provisionings frais (au démarrage) se marquer.
        time.sleep(20)
        while True:
            try:
                _reconcile_once()
            except Exception:  # noqa: BLE001
                logger.exception("réconciliateur provisioning : tick raté")
            time.sleep(interval)

    threading.Thread(target=_loop, daemon=True, name="provision-reconciler").start()

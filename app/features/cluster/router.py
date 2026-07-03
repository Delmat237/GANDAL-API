"""Routes du plan de contrôle cluster Omega (topologie, distribution, internet, réseau).

Alimente l'interface graphique (toile de nœuds type n8n) : topologie des VMs omega,
liens réseau, statut internet. Les actions internet/réseau pilotent nos scripts.

RBAC : un étudiant ne voit/agit que sur SES VMs (mapping DB id_proxmox→user) ;
enseignant/superadmin voient toute la flotte et le plan de contrôle (distribution, reconcile).
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (get_current_user, require_admin,
                                   require_teacher_or_admin)
from app.infrastructure import factories
from app.shared.models import User, VM
from app.shared.policies.permissions import AuthorizationPolicy

from .schemas import (AutostartRequest, CreateVMRequest, CreateVMResponse,
                      DnsRequest, DomainRequest, ExposeRequest, GpuRequest,
                      InternetToggle, NetworkLinkRequest, ReconcileResult,
                      ReconfigureRequest, TopologyResponse)
from .service import ClusterService

router = APIRouter(prefix="/cluster", tags=["cluster"])


def _service(db: Session) -> ClusterService:
    return ClusterService(db, factories.get_proxmox_gateway())


@router.get("/topology", response_model=TopologyResponse)
def get_topology(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> TopologyResponse:
    """Topologie pour la toile. Super admin = toute la flotte ; enseignant = les VMs de
    ses étudiants supervisés (= celles dont il approuve la création) ; étudiant = ses VMs."""
    if AuthorizationPolicy.is_admin_or_superadmin(user):
        allowed = None  # toute la flotte
    elif _is_teacher(user):
        from app.shared.models import Student
        allowed = {
            sid for (sid,) in db.query(Student.id)
            .filter(Student.supervisor_id == user.id).all()
        }
    else:
        allowed = {user.id}
    return _service(db).topology(allowed_owner_ids=allowed)


@router.post("/vms", response_model=CreateVMResponse, status_code=201)
def create_vm(
    body: CreateVMRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_teacher_or_admin)],
) -> CreateVMResponse:
    """Crée et provisionne une VM directement (bouton « + » de la toile).

    RÉSERVÉ AUX ENSEIGNANTS/ADMINS. Un étudiant ne crée jamais une VM
    directement : il en fait la DEMANDE (`POST /requetes/create-vm`), que son
    enseignant superviseur valide."""
    res = _service(db).create_vm(
        user, name=body.name, vcpu=body.vcpu, ram_gb=body.ram_gb,
        disk_gb=body.disk_gb, vram_gb=body.vram_gb, internet=body.internet,
        autostart=body.autostart)
    return CreateVMResponse(**res)


@router.get("/distribution")
def get_distribution(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_teacher_or_admin)],
):
    """Occupation par nœud vs cible 1/2/2 (lecture seule)."""
    return {"nodes": _service(db).distribution()}


@router.get("/gpu")
def gpu_status(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_teacher_or_admin)],
):
    """État GPU par nœud (VRAM, utilisation, température)."""
    return {"gpus": _service(db).gpu_status()}


@router.get("/migrations")
def migrations(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(require_teacher_or_admin)],
):
    """Historique récent des migrations de VMs (live-migration)."""
    return {"migrations": _service(db).migrations()}


@router.post("/reconcile", response_model=ReconcileResult)
def reconcile(
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> ReconcileResult:
    """Déclenche un tick de réconciliation (migre au plus 1 VM vers la cible)."""
    ok = _service(db).reconcile()
    return ReconcileResult(ok=ok)


@router.post("/vms/{vm_id}/internet")
def toggle_internet(
    vm_id: int,
    body: InternetToggle,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Connecte/déconnecte une VM à internet (geste ludique de la toile)."""
    return _service(db).set_internet(user, vm_id, body.enable)


@router.post("/vms/{vm_id}/llm-access")
def toggle_llm_access(
    vm_id: int,
    body: InternetToggle,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Ouvre/ferme l'accès ÉTROIT d'une VM à la gateway LLM (reste isolée par ailleurs)."""
    return _service(db).set_llm_access(user, vm_id, body.enable)


@router.post("/llm-access/reconcile")
def reconcile_llm_access(
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
    prune: bool = False,
):
    """Réconcilie l'accès LLM : toute VM démarrée avec vram>0 obtient l'accès gateway."""
    return _service(db).reconcile_llm_access(prune=prune)


@router.delete("/vms/{vmid}", status_code=204)
def delete_vm(
    vmid: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Détruit une VM par VMID (DNS retiré + destroy purge) et retire la ligne DB."""
    _service(db).delete_vm(user, vmid)


@router.post("/vms/{vmid}/start")
def start_vm(
    vmid: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Démarre une VM (par VMID Proxmox — espace de la toile)."""
    return _service(db).lifecycle(user, vmid, "start")


@router.post("/vms/{vmid}/stop")
def stop_vm(
    vmid: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Arrête une VM (par VMID Proxmox)."""
    return _service(db).lifecycle(user, vmid, "stop")


@router.post("/vms/{vmid}/reconfigure")
def reconfigure_vm(
    vmid: int,
    body: ReconfigureRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Modifie les caractéristiques d'une VM (vCPU max, RAM, disque, VRAM, nom)."""
    return _service(db).reconfigure(user, vmid, **body.model_dump(exclude_none=True))


@router.post("/vms/{vmid}/gpu")
def set_gpu(
    vmid: int,
    body: GpuRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Alloue ou retire du GPU (VRAM partagée via proxy, pas de passthrough)."""
    return _service(db).set_gpu(user, vmid, body.vram_mib)


@router.post("/vms/{vmid}/autostart")
def set_autostart(
    vmid: int,
    body: AutostartRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Active/désactive le redémarrage automatique (always-on)."""
    return _service(db).set_autostart(user, vmid, body.enable)


@router.post("/vms/{vmid}/expose")
def expose_service(
    vmid: int,
    body: ExposeRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Publie un service de la VM vers le LAN (port-forward pfSense)."""
    return _service(db).expose_service(
        user, vmid, service_port=body.service_port, ext_port=body.ext_port,
        hostname=body.hostname, proto=body.proto, enable=body.enable)


@router.post("/vms/{vmid}/domain")
def add_domain(
    vmid: int,
    body: DomainRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Publie un service VM sous un nom de domaine SANS port (reverse proxy)."""
    return _service(db).add_domain(user, vmid, body.hostname, body.port, body.enable)


@router.post("/vms/{vmid}/dns")
def register_dns(
    vmid: int,
    body: DnsRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Enregistre/renomme l'entrée DNS de la VM (zone enspy-gi.gandal)."""
    return _service(db).dns_register(user, vmid, body.hostname)


@router.post("/network/link")
def network_link(
    body: NetworkLinkRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Relie (maillage) ou isole un groupe de VMs — arêtes de la toile."""
    return _service(db).link(user, body.vm_ids, body.enable, body.group_name)


def _is_teacher(user: User) -> bool:
    from app.shared.models import Teacher
    return isinstance(user, Teacher)

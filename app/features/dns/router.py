from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.features.dns.service import DNSService
from app.shared.models import User
from app.shared.schemas.common import PaginatedResponse, PaginationParams
from app.shared.schemas.dns import DNSEntryCreate, DNSEntryRead, DNSEntryUpdate

router = APIRouter(prefix="/dns", tags=["dns"])


# ── Endpoints publics (admin) ──────────────────────────────────────────────────

@router.get("", response_model=PaginatedResponse[DNSEntryRead])
def list_all_dns(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
) -> PaginatedResponse[DNSEntryRead]:
    """Liste toutes les entrées DNS du système (admin uniquement)."""
    items, total = DNSService(db).list_all(current_user, pagination.page, pagination.size)
    return PaginatedResponse(
        items=[DNSService.to_read(e) for e in items],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


# ── Endpoints par VM ───────────────────────────────────────────────────────────

@router.get("/vms/{vm_id}", response_model=PaginatedResponse[DNSEntryRead])
def list_dns_for_vm(
    vm_id: int,
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PaginatedResponse[DNSEntryRead]:
    """Liste toutes les entrées DNS associées à une VM donnée."""
    items, total = DNSService(db).list_for_vm(
        current_user, vm_id, pagination.page, pagination.size
    )
    return PaginatedResponse(
        items=[DNSService.to_read(e) for e in items],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


# ── CRUD sur les entrées DNS ───────────────────────────────────────────────────

@router.post("", response_model=DNSEntryRead, status_code=201)
def create_dns(
    data: DNSEntryCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DNSEntryRead:
    """
    Crée une nouvelle entrée DNS pour une VM.

    - Le hostname doit être un FQDN valide (ex: `api.projet.dc.enspy.cm`).
    - Un hostname ne peut être attribué qu'à une seule VM à la fois.
    - Seul le propriétaire de la VM (ou un admin) peut créer une entrée DNS.
    """
    entry = DNSService(db).create(current_user, data)
    return DNSService.to_read(entry)


@router.get("/{dns_id}", response_model=DNSEntryRead)
def get_dns(
    dns_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DNSEntryRead:
    """Récupère une entrée DNS par son identifiant."""
    entry = DNSService(db).get(current_user, dns_id)
    return DNSService.to_read(entry)


@router.patch("/{dns_id}", response_model=DNSEntryRead)
def update_dns(
    dns_id: int,
    data: DNSEntryUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DNSEntryRead:
    """Modifie le hostname d'une entrée DNS existante."""
    entry = DNSService(db).update(current_user, dns_id, data)
    return DNSService.to_read(entry)


@router.delete("/{dns_id}", status_code=204)
def delete_dns(
    dns_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Supprime une entrée DNS."""
    DNSService(db).delete(current_user, dns_id)

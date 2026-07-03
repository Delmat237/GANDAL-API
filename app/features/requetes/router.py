from typing import Annotated, Union

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_optional_user
from app.features.requetes.service import RequeteService
from app.shared.models import User
from app.shared.schemas.common import PaginatedResponse, PaginationParams
from app.shared.schemas.requete import (
    RAccountCreate,
    RAccountRead,
    RCreateVMCreate,
    RCreateVMRead,
    RDeleteVMCreate,
    RDeleteVMRead,
    RDomainCreate,
    RDomainRead,
)

router = APIRouter(prefix="/requetes", tags=["requetes"])


class ApproveBody(BaseModel):
    ssh_public_key: str = ""


@router.post("/create-vm", response_model=RCreateVMRead, status_code=201)
def create_vm_request(
    data: RCreateVMCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RCreateVMRead:
    return RequeteService(db).create_r_create_vm(current_user, data)


@router.post("/delete-vm", response_model=RDeleteVMRead, status_code=201)
def delete_vm_request(
    data: RDeleteVMCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RDeleteVMRead:
    return RequeteService(db).create_r_delete_vm(current_user, data)


@router.post("/account", response_model=RAccountRead, status_code=201)
def account_request(
    data: RAccountCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
) -> RAccountRead:
    """Demande d'inscription (auto-signup). PUBLIC : accessible sans être connecté
    (un nouvel étudiant n'a pas encore de compte). L'enseignant choisi la valide."""
    return RequeteService(db).create_r_account(current_user, data)


@router.post("/domain", response_model=RDomainRead, status_code=201)
def domain_request(
    data: RDomainCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RDomainRead:
    """Demande de nom de domaine: nom_choisi → http vers VM_IP:port (reverse-proxy)."""
    return RequeteService(db).create_r_domain(current_user, data)


@router.get("", response_model=PaginatedResponse[Union[RCreateVMRead, RDeleteVMRead, RAccountRead, RDomainRead]])
def list_requetes(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PaginatedResponse:
    items, total = RequeteService(db).list_requetes(
        current_user, pagination.page, pagination.size)
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.get("/{requete_id}")
def get_requete(
    requete_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    req = RequeteService(db).get_requete(requete_id)
    RequeteService(db)._ensure_view(current_user, req)
    return req


@router.post("/{requete_id}/approve")
def approve_requete(
    requete_id: int,
    body: ApproveBody,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return RequeteService(db).approve(current_user, requete_id, body.ssh_public_key)


@router.post("/{requete_id}/reject")
def reject_requete(
    requete_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return RequeteService(db).reject(current_user, requete_id)

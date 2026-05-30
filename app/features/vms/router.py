from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.features.vms.service import VMService
from app.shared.models import User, VM
from app.shared.schemas.common import PaginatedResponse, PaginationParams
from app.shared.schemas.vm import VMCreate, VMRead, VMUpdate

router = APIRouter(prefix="/vms", tags=["vms"])


@router.post("", response_model=VMRead, status_code=201)
def create_vm(
    data: VMCreate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> VM:
    return VMService(db).create_vm_admin(data)


@router.get("", response_model=PaginatedResponse[VMRead])
def list_vms(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PaginatedResponse[VMRead]:
    items, total = VMService(db).list_vms(
        current_user, pagination.page, pagination.size)
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.get("/{vm_id}", response_model=VMRead)
def get_vm(
    vm_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> VM:
    vm = VMService(db).get_vm(vm_id)
    VMService(db)._ensure_can_manage(current_user, vm)
    return vm


@router.patch("/{vm_id}", response_model=VMRead)
def update_vm(
    vm_id: int,
    data: VMUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> VM:
    return VMService(db).update_vm(current_user, vm_id, data)


@router.delete("/{vm_id}", status_code=204)
def delete_vm(
    vm_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    VMService(db).delete_vm(current_user, vm_id)


@router.post("/{vm_id}/start", response_model=VMRead)
def start_vm(
    vm_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> VM:
    return VMService(db).start_vm(current_user, vm_id)


@router.post("/{vm_id}/stop", response_model=VMRead)
def stop_vm(
    vm_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> VM:
    return VMService(db).stop_vm(current_user, vm_id)


@router.post("/{vm_id}/pause", response_model=VMRead)
def pause_vm(
    vm_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> VM:
    return VMService(db).pause_vm(current_user, vm_id)

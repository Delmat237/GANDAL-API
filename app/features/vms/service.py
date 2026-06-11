from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.application.ports.proxmox_gateway import ProxmoxGateway
from app.core.config import get_settings
from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.infrastructure import factories
from app.features.vms.repository import VMRepository
from app.shared.models import User, VM
from app.shared.policies.permissions import AuthorizationPolicy
from app.shared.policies.states import StateTransitionError, VMStatePolicy
from app.shared.schemas.vm import VMCreate, VMUpdate


class VMService:
    def __init__(self, db: Session, proxmox: ProxmoxGateway | None = None) -> None:
        self.db = db
        self.repo = VMRepository(db)
        self._proxmox = proxmox
        self.settings = get_settings()

    @property
    def proxmox(self) -> ProxmoxGateway:
        return self._proxmox or factories.get_proxmox_gateway()

    def get_vm(self, vm_id: int) -> VM:
        vm = self.repo.get(vm_id)
        if vm is None:
            raise NotFoundError("VM introuvable")
        return vm

    def _ensure_can_manage(self, user: User, vm: VM) -> None:
        if not AuthorizationPolicy.can_manage_vm(user, vm):
            raise ForbiddenError("Vous n'avez pas les droits sur cette VM.")

    def list_vms(self, user: User, page: int, size: int) -> tuple[list[VM], int]:
        offset = (page - 1) * size
        if AuthorizationPolicy.is_admin_or_superadmin(user):
            return self.repo.list_all(offset, size)
        return self.repo.list_for_user(user.id, offset, size)

    def create_vm_admin(self, data: VMCreate) -> VM:
        vm = self.repo.create(data)
        self.db.commit()
        self.db.refresh(vm)
        return vm

    def update_vm(self, user: User, vm_id: int, data: VMUpdate) -> VM:
        vm = self.get_vm(vm_id)
        self._ensure_can_manage(user, vm)
        vm = self.repo.update(vm, data)
        self.db.commit()
        self.db.refresh(vm)
        return vm

    def delete_vm(self, user: User, vm_id: int) -> None:
        vm = self.get_vm(vm_id)
        self._ensure_can_manage(user, vm)
        if vm.id_proxmox and vm.node:
            self.proxmox.destroy_vm(vm.id_proxmox)
        self.repo.delete(vm)
        self.db.commit()

    def _transition(self, user: User, vm_id: int, target: str) -> VM:
        vm = self.get_vm(vm_id)
        self._ensure_can_manage(user, vm)
        try:
            VMStatePolicy.validate_transition(vm, target)
        except StateTransitionError as e:
            raise AppError(str(e), status_code=400) from e

        if vm.id_proxmox and vm.node:
            if target == VMStatePolicy.UP:
                self.proxmox.start_vm(vm.node, vm.id_proxmox)
                ip = self.proxmox.get_vm_ip(vm.node, vm.id_proxmox)
                if ip:
                    vm.ip_address = ip
            elif target == VMStatePolicy.STOPPED:
                self.proxmox.stop_vm(vm.node, vm.id_proxmox)

        vm.status = target
        if target == VMStatePolicy.STOPPED:
            vm.date_stop_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(vm)
        return vm

    def start_vm(self, user: User, vm_id: int) -> VM:
        return self._transition(user, vm_id, VMStatePolicy.UP)

    def stop_vm(self, user: User, vm_id: int) -> VM:
        return self._transition(user, vm_id, VMStatePolicy.STOPPED)

    def pause_vm(self, user: User, vm_id: int) -> VM:
        return self._transition(user, vm_id, VMStatePolicy.WAITING)

    def check_quota(self, user_id: int) -> None:
        count = self.repo.count_for_user(user_id)
        if count >= self.settings.max_vms_per_student:
            raise AppError(
                f"Quota de VMs atteint ({self.settings.max_vms_per_student})",
                status_code=400,
            )

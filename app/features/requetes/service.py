import logging
import secrets

from sqlalchemy.orm import Session

from app.application.ports.email_port import EmailPort
from app.application.ports.proxmox_gateway import ProxmoxGateway
from app.core.config import get_settings
from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.features.requetes.repository import RequeteRepository
from app.features.users.service import UserService
from app.features.vms.repository import VMRepository
from app.features.vms.service import VMService
from app.infrastructure import factories
from app.infrastructure.proxmox.constants import resolve_template_for_os, resolve_vlan_for_department
from app.infrastructure.proxmox.proxmox_client import ProxmoxIntegrationError
from app.shared.models import RAccount, RCreateVM, RDeleteVM, Requete, Student, User, VM
from app.shared.policies.permissions import AuthorizationPolicy
from app.shared.policies.states import RequestStatePolicy, StateTransitionError, VMStatePolicy
from app.shared.schemas.requete import RAccountCreate, RCreateVMCreate, RDeleteVMCreate

logger = logging.getLogger(__name__)


class RequeteService:
    def __init__(
        self,
        db: Session,
        proxmox: ProxmoxGateway | None = None,
        email: EmailPort | None = None,
    ) -> None:
        self.db = db
        self.repo = RequeteRepository(db)
        self.vm_repo = VMRepository(db)
        self._proxmox = proxmox
        self._email = email

    @property
    def proxmox(self) -> ProxmoxGateway:
        return self._proxmox or factories.get_proxmox_gateway()

    @property
    def email(self) -> EmailPort:
        return self._email or factories.get_email_sender()

    def get_requete(self, requete_id: int) -> Requete:
        req = self.repo.get(requete_id)
        if req is None:
            raise NotFoundError("Requête introuvable")
        return req

    def _ensure_view(self, user: User, requete: Requete) -> None:
        if not AuthorizationPolicy.can_view_request(user, requete):
            raise ForbiddenError()

    def _ensure_evaluate(self, user: User, requete: Requete) -> None:
        if not AuthorizationPolicy.can_evaluate_request(user, requete):
            raise ForbiddenError("Vous ne pouvez pas évaluer cette requête")

    def list_requetes(self, user: User, page: int, size: int) -> tuple[list[Requete], int]:
        offset = (page - 1) * size
        if AuthorizationPolicy.is_admin_or_superadmin(user):
            return self.repo.list_all(offset, size)
        if isinstance(user, Student):
            return self.repo.list_for_student(user.id, offset, size)
        from app.shared.models import Teacher

        if isinstance(user, Teacher):
            return self.repo.list_for_teacher(user.id, offset, size)
        return [], 0

    def create_r_create_vm(self, user: User, data: RCreateVMCreate) -> RCreateVM:
        if not isinstance(user, Student):
            raise ForbiddenError("Seuls les étudiants peuvent demander une VM")
        VMService(self.db, self.proxmox).check_quota(user.id)
        req = self.repo.create_r_create_vm(data, user.id)
        self.db.commit()
        self.db.refresh(req)
        return req

    def create_r_delete_vm(self, user: User, data: RDeleteVMCreate) -> RDeleteVM:
        if not isinstance(user, Student):
            raise ForbiddenError(
                "Seuls les étudiants peuvent demander une suppression")
        vm = self.vm_repo.get(data.vm_id)
        if vm is None or vm.user_id != user.id:
            raise ForbiddenError("VM invalide")
        req = self.repo.create_r_delete_vm(data, user.id)
        self.db.commit()
        self.db.refresh(req)
        return req

    def create_r_account(self, user: User, data: RAccountCreate) -> RAccount:
        if not isinstance(user, Student):
            raise ForbiddenError(
                "Seuls les étudiants peuvent demander un compte")
        req = self.repo.create_r_account(data, user.id)
        self.db.commit()
        self.db.refresh(req)
        return req

    def approve(self, user: User, requete_id: int, ssh_public_key: str = "") -> Requete:
        requete = self.get_requete(requete_id)
        self._ensure_evaluate(user, requete)
        try:
            RequestStatePolicy.validate_approval(requete)
        except StateTransitionError as e:
            raise AppError(str(e), status_code=400) from e

        if requete.type == "r_create_vm":
            create_req = self.db.get(RCreateVM, requete_id)
            if create_req is None:
                raise NotFoundError("Requête create-vm introuvable")
            self._approve_create_vm(
                create_req, ssh_public_key or "ssh-rsa mock")
        elif requete.type == "r_delete_vm":
            delete_req = self.db.get(RDeleteVM, requete_id)
            if delete_req is None:
                raise NotFoundError("Requête delete-vm introuvable")
            self._approve_delete_vm(delete_req)
        elif requete.type == "r_account":
            account_req = self.db.get(RAccount, requete_id)
            if account_req is None:
                raise NotFoundError("Requête account introuvable")
            self._approve_account(account_req)

        requete.status = RequestStatePolicy.VALIDATED
        self.db.commit()
        self.db.refresh(requete)
        self._notify(requete, "validée")
        return requete

    def reject(self, user: User, requete_id: int) -> Requete:
        requete = self.get_requete(requete_id)
        self._ensure_evaluate(user, requete)
        try:
            RequestStatePolicy.validate_approval(requete)
        except StateTransitionError as e:
            raise AppError(str(e), status_code=400) from e
        requete.status = RequestStatePolicy.REJECTED
        self.db.commit()
        self.db.refresh(requete)
        self._notify(requete, "rejetée")
        return requete

    def _approve_create_vm(self, requete: RCreateVM, ssh_public_key: str) -> None:
        student = self.repo.get_student(requete.student_id)
        if student is None:
            raise NotFoundError("Étudiant introuvable")

        n_cpu = requete.n_cpu or 2
        proxmox_vmid: int | None = None
        node: str | None = None
        status = VMStatePolicy.WAITING

        if not get_settings().proxmox_simulation_mode:
            template = resolve_template_for_os(requete.os)
            vlan = resolve_vlan_for_department(student.departement)
            name = f"vm-{student.matricule}-{requete.id}"
            try:
                result = self.proxmox.provision_new_vm(
                    name=name,
                    template_vmid=template,
                    ram_gb=float(requete.size_ram),
                    vcpu=n_cpu,
                    ssh_pub_key=ssh_public_key,
                    vlan_id=vlan,
                )
                proxmox_vmid = result.vmid
                node = result.node
                status = VMStatePolicy.UP
            except ProxmoxIntegrationError:
                # Proxmox injoignable : on n'échoue pas l'approbation. La VM est
                # enregistrée en base avec le statut "waiting" pour un
                # provisionnement ultérieur (worker ou intervention manuelle).
                logger.exception(
                    "Provisionnement Proxmox échoué pour la requête %s ; VM enregistrée en attente.",
                    requete.id,
                )

        vm = VM(
            size_rom=requete.size_rom,
            size_ram=requete.size_ram,
            n_cpu=n_cpu,
            iso=requete.os,
            iso_image=requete.os,
            id_proxmox=proxmox_vmid,
            node=node,
            status=status,
            ssh_public_key=ssh_public_key,
            user_id=student.id,
        )
        self.db.add(vm)

    def _approve_delete_vm(self, requete: RDeleteVM) -> None:
        vm = self.vm_repo.get(requete.vm_id)
        if vm is None:
            raise NotFoundError("VM introuvable")
        if not get_settings().proxmox_simulation_mode and vm.id_proxmox:
            try:
                self.proxmox.destroy_vm(vm.id_proxmox)
            except ProxmoxIntegrationError:
                # On poursuit la suppression en base même si Proxmox échoue.
                logger.exception(
                    "Suppression Proxmox échouée pour la VM %s ; suppression en base poursuivie.",
                    vm.id,
                )
        self.db.delete(vm)

    def _approve_account(self, requete: RAccount) -> None:
        password = secrets.token_urlsafe(12)
        UserService(self.db).create_user_from_raccount(requete, password)

    def _notify(self, requete: Requete, status_label: str) -> None:
        student = self.repo.get_student(requete.student_id)
        if student:
            self.email.send_request_status_email(
                student.email,
                f"Requête {status_label}",
                f"Votre requête '{requete.object}' a été {status_label}.",
            )

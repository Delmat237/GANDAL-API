import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.security import hash_password
from app.features.users.repository import UserRepository
from app.shared.models import RAccount, Student, Teacher, User
from app.shared.policies.permissions import AuthorizationPolicy
from app.shared.schemas.user import StudentCreate, StudentUpdate, TeacherCreate, TeacherUpdate

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, db: Session) -> None:
        self.repo = UserRepository(db)
        self.db = db

    def get_student(self, student_id: int) -> Student:
        user = self.repo.get_user(student_id)
        if not isinstance(user, Student):
            raise NotFoundError("Étudiant introuvable")
        return user

    def get_teacher(self, teacher_id: int) -> Teacher:
        user = self.repo.get_user(teacher_id)
        if not isinstance(user, Teacher):
            raise NotFoundError("Enseignant introuvable")
        return user

    def list_students(self, page: int, size: int) -> tuple[list[Student], int]:
        offset = (page - 1) * size
        return self.repo.list_students(offset, size)

    def list_students_for(
        self, actor: User, page: int, size: int
    ) -> tuple[list[Student], int]:
        """Super admin voit tous les étudiants ; un enseignant uniquement les
        siens (dont il est superviseur)."""
        offset = (page - 1) * size
        if AuthorizationPolicy.is_superadmin(actor):
            return self.repo.list_students(offset, size)
        if isinstance(actor, Teacher):
            return self.repo.list_students_by_supervisor(actor.id, offset, size)
        raise ForbiddenError()

    def list_teachers(self, page: int, size: int) -> tuple[list[Teacher], int]:
        offset = (page - 1) * size
        return self.repo.list_teachers(offset, size)

    def set_student_active(self, actor: User, student_id: int, active: bool) -> Student:
        """Bloque/débloque un étudiant. Réservé au superviseur ou super admin."""
        student = self.get_student(student_id)
        if not AuthorizationPolicy.can_manage_student(actor, student):
            raise ForbiddenError("Vous ne gérez pas cet étudiant")
        student.is_active = active
        self.db.commit()
        self.db.refresh(student)
        return student

    def set_teacher_active(self, actor: User, teacher_id: int, active: bool) -> Teacher:
        """Bloque/débloque un enseignant. Réservé au super admin."""
        if not AuthorizationPolicy.can_manage_teacher(actor):
            raise ForbiddenError("Seul le super admin gère les enseignants")
        teacher = self.get_teacher(teacher_id)
        if teacher.role == "SuperAdmin":
            raise ForbiddenError("Le super admin ne peut pas être bloqué")
        teacher.is_active = active
        self.db.commit()
        self.db.refresh(teacher)
        return teacher

    def _destroy_user_vms(self, user: User) -> None:
        """Détruit les VMs Proxmox de l'utilisateur avant suppression en base.
        Best-effort : on loggue et on poursuit si Proxmox échoue."""
        if get_settings().proxmox_simulation_mode:
            return
        from app.infrastructure import factories
        gateway = factories.get_proxmox_gateway()
        for vm in list(user.vms):
            if vm.id_proxmox:
                try:
                    gateway.destroy_vm(vm.id_proxmox)
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "Destruction Proxmox VM %s (vmid=%s) échouée ; "
                        "suppression en base poursuivie.", vm.id, vm.id_proxmox)

    def create_student(self, data: StudentCreate, creator: User | None = None,
                       password_hash: str | None = None) -> Student:
        if self.repo.get_by_username(data.username):
            raise ConflictError("Nom d'utilisateur déjà utilisé")
        if self.repo.get_by_email(data.email):
            raise ConflictError("Adresse e-mail déjà utilisée")
        if self.repo.get_by_matricule(data.matricule):
            raise ConflictError("Matricule déjà existant")
        student = self.repo.create_student(data, password_hash or hash_password(data.password))
        # Superviseur : si un enseignant crée l'étudiant, c'est lui ; si le super
        # admin le crée, il peut désigner un superviseur via data.supervisor_id.
        supervisor_id = getattr(data, "supervisor_id", None)
        if isinstance(creator, Teacher) and not AuthorizationPolicy.is_superadmin(creator):
            supervisor_id = creator.id
        if supervisor_id:
            student.supervisor_id = supervisor_id
        self.db.commit()
        self.db.refresh(student)
        return student

    def create_teacher(self, data: TeacherCreate, password_hash: str | None = None) -> Teacher:
        if self.repo.get_by_username(data.username):
            raise ConflictError("Nom d'utilisateur déjà utilisé")
        if self.repo.get_by_email(data.email):
            raise ConflictError("Adresse e-mail déjà utilisée")
        teacher = self.repo.create_teacher(data, password_hash or hash_password(data.password))
        self.db.commit()
        self.db.refresh(teacher)
        return teacher

    def update_student(self, student_id: int, data: StudentUpdate) -> Student:
        student = self.get_student(student_id)
        student = self.repo.update_student(student, data)
        self.db.commit()
        self.db.refresh(student)
        return student

    def update_teacher(self, teacher_id: int, data: TeacherUpdate) -> Teacher:
        teacher = self.get_teacher(teacher_id)
        teacher = self.repo.update_teacher(teacher, data)
        self.db.commit()
        self.db.refresh(teacher)
        return teacher

    def delete_student(self, student_id: int, actor: User | None = None) -> None:
        student = self.get_student(student_id)
        if actor is not None and not AuthorizationPolicy.can_manage_student(actor, student):
            raise ForbiddenError("Vous ne gérez pas cet étudiant")
        self._destroy_user_vms(student)
        self.repo.delete_user(student)  # cascade VMs/publications en base
        self.db.commit()

    def delete_teacher(self, teacher_id: int, actor: User | None = None) -> None:
        if actor is not None and not AuthorizationPolicy.can_manage_teacher(actor):
            raise ForbiddenError("Seul le super admin gère les enseignants")
        teacher = self.get_teacher(teacher_id)
        if teacher.role == "SuperAdmin":
            raise ForbiddenError("Le super admin ne peut pas être supprimé")
        self._destroy_user_vms(teacher)
        self.repo.delete_user(teacher)
        self.db.commit()

    def create_user_from_raccount(self, requete: RAccount, password: str | None,
                                  password_hash: str | None = None) -> User:
        # Le front d'inscription transmet username/level/departement dans
        # `content` (JSON). On les récupère, avec repli sur des valeurs sûres.
        import json

        meta: dict = {}
        if requete.content:
            try:
                meta = json.loads(requete.content)
            except (ValueError, TypeError):
                meta = {}

        username = (meta.get("username") or requete.nom or requete.email.split("@")[0]).strip()
        # Mot de passe en clair seulement si aucun hash fourni (ancien flux aléatoire).
        pwd = password or "x"  # placeholder ; le hash a priorité s'il est fourni
        if requete.matricule:
            data = StudentCreate(
                username=username,
                email=requete.email,
                password=pwd,
                matricule=requete.matricule,
                level=meta.get("level") or "L1",
                departement=meta.get("departement") or requete.organisation or "default",
            )
            return self.create_student(data, password_hash=password_hash)
        role = "Teacher"
        data = TeacherCreate(
            username=username,
            email=requete.email,
            password=pwd,
            role=role,
        )
        return self.create_teacher(data, password_hash=password_hash)

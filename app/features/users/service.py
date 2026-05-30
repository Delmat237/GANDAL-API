from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.features.users.repository import UserRepository
from app.shared.models import RAccount, Student, Teacher, User
from app.shared.schemas.user import StudentCreate, StudentUpdate, TeacherCreate, TeacherUpdate


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

    def list_teachers(self, page: int, size: int) -> tuple[list[Teacher], int]:
        offset = (page - 1) * size
        return self.repo.list_teachers(offset, size)

    def create_student(self, data: StudentCreate) -> Student:
        if self.repo.get_by_username(data.username):
            raise ConflictError("Nom d'utilisateur déjà utilisé")
        student = self.repo.create_student(data, hash_password(data.password))
        self.db.commit()
        self.db.refresh(student)
        return student

    def create_teacher(self, data: TeacherCreate) -> Teacher:
        if self.repo.get_by_username(data.username):
            raise ConflictError("Nom d'utilisateur déjà utilisé")
        teacher = self.repo.create_teacher(data, hash_password(data.password))
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

    def delete_student(self, student_id: int) -> None:
        student = self.get_student(student_id)
        self.repo.delete_user(student)
        self.db.commit()

    def delete_teacher(self, teacher_id: int) -> None:
        teacher = self.get_teacher(teacher_id)
        self.repo.delete_user(teacher)
        self.db.commit()

    def create_user_from_raccount(self, requete: RAccount, password: str) -> User:
        if requete.matricule:
            data = StudentCreate(
                username=requete.email.split("@")[0],
                email=requete.email,
                password=password,
                matricule=requete.matricule,
                level="L1",
                departement=requete.organisation or "default",
            )
            return self.create_student(data)
        role = "Teacher"
        data = TeacherCreate(
            username=requete.email.split("@")[0],
            email=requete.email,
            password=password,
            role=role,
        )
        return self.create_teacher(data)

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.shared.models import Student, Teacher, User
from app.shared.schemas.user import StudentCreate, StudentUpdate, TeacherCreate, TeacherUpdate


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        return self.db.execute(select(User).where(User.username == username)).scalar_one_or_none()

    def get_by_email(self, email: str) -> User | None:
        return self.db.execute(select(User).where(User.email == email)).scalar_one_or_none()

    def get_by_matricule(self, matricule: str) -> Student | None:
        return self.db.execute(
            select(Student).where(Student.matricule == matricule)
        ).scalar_one_or_none()

    def get_by_username_or_email(self, identifier: str) -> User | None:
        return self.db.execute(
            select(User).where(
                (User.username == identifier) | (User.email == identifier)
            )
        ).scalar_one_or_none()

    def list_students(self, offset: int, limit: int) -> tuple[list[Student], int]:
        total = self.db.execute(
            select(func.count()).select_from(Student)).scalar_one()
        items = list(self.db.execute(select(Student).offset(
            offset).limit(limit)).scalars().all())
        return items, total

    def list_students_by_supervisor(
        self, supervisor_id: int, offset: int, limit: int
    ) -> tuple[list[Student], int]:
        cond = Student.supervisor_id == supervisor_id
        total = self.db.execute(
            select(func.count()).select_from(Student).where(cond)).scalar_one()
        items = list(self.db.execute(
            select(Student).where(cond).offset(offset).limit(limit)
        ).scalars().all())
        return items, total

    def list_teachers(self, offset: int, limit: int) -> tuple[list[Teacher], int]:
        total = self.db.execute(
            select(func.count()).select_from(Teacher)).scalar_one()
        items = list(self.db.execute(select(Teacher).offset(
            offset).limit(limit)).scalars().all())
        return items, total

    def create_student(self, data: StudentCreate, password_hash: str) -> Student:
        student = Student(
            username=data.username,
            email=data.email,
            password=password_hash,
            matricule=data.matricule,
            level=data.level,
            departement=data.departement,
        )
        self.db.add(student)
        self.db.flush()
        return student

    def create_teacher(self, data: TeacherCreate, password_hash: str) -> Teacher:
        teacher = Teacher(
            username=data.username,
            email=data.email,
            password=password_hash,
            role=data.role,
        )
        self.db.add(teacher)
        self.db.flush()
        return teacher

    def update_student(self, student: Student, data: StudentUpdate) -> Student:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(student, field, value)
        self.db.flush()
        return student

    def update_teacher(self, teacher: Teacher, data: TeacherUpdate) -> Teacher:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(teacher, field, value)
        self.db.flush()
        return teacher

    def delete_user(self, user: User) -> None:
        self.db.delete(user)
        self.db.flush()

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.shared.models import RAccount, RCreateVM, RDeleteVM, Requete, Student
from app.shared.schemas.requete import RAccountCreate, RCreateVMCreate, RDeleteVMCreate


class RequeteRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, requete_id: int) -> Requete | None:
        return self.db.get(Requete, requete_id)

    def list_for_student(self, student_id: int, offset: int, limit: int) -> tuple[list[Requete], int]:
        q = select(Requete).where(Requete.student_id == student_id)
        total = self.db.execute(
            select(func.count()).select_from(Requete).where(
                Requete.student_id == student_id)
        ).scalar_one()
        items = list(self.db.execute(
            q.offset(offset).limit(limit)).scalars().all())
        return items, total

    def list_for_teacher(self, teacher_id: int, offset: int, limit: int) -> tuple[list[Requete], int]:
        q = select(Requete).where(Requete.teacher_id == teacher_id)
        total = self.db.execute(
            select(func.count()).select_from(Requete).where(
                Requete.teacher_id == teacher_id)
        ).scalar_one()
        items = list(self.db.execute(
            q.offset(offset).limit(limit)).scalars().all())
        return items, total

    def list_all(self, offset: int, limit: int) -> tuple[list[Requete], int]:
        total = self.db.execute(
            select(func.count()).select_from(Requete)).scalar_one()
        items = list(self.db.execute(select(Requete).offset(
            offset).limit(limit)).scalars().all())
        return items, total

    def create_r_create_vm(self, data: RCreateVMCreate, student_id: int) -> RCreateVM:
        req = RCreateVM(
            object=data.object,
            content=data.content,
            student_id=student_id,
            teacher_id=data.teacher_id,
            size_rom=data.size_rom,
            size_ram=data.size_ram,
            os=data.os,
        )
        self.db.add(req)
        self.db.flush()
        return req

    def create_r_delete_vm(self, data: RDeleteVMCreate, student_id: int) -> RDeleteVM:
        req = RDeleteVM(
            object=data.object,
            content=data.content,
            student_id=student_id,
            teacher_id=data.teacher_id,
            vm_id=data.vm_id,
        )
        self.db.add(req)
        self.db.flush()
        return req

    def create_r_account(self, data: RAccountCreate, student_id: int) -> RAccount:
        req = RAccount(
            object=data.object,
            content=data.content,
            student_id=student_id,
            teacher_id=data.teacher_id,
            nom=data.nom,
            email=data.email,
            justification=data.justification,
            matricule=data.matricule,
            organisation=data.organisation,
        )
        self.db.add(req)
        self.db.flush()
        return req

    def get_student(self, student_id: int) -> Student | None:
        return self.db.get(Student, student_id)

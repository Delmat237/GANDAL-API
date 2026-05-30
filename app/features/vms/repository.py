from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.shared.models import VM, User
from app.shared.schemas.vm import VMCreate, VMUpdate


class VMRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, vm_id: int) -> VM | None:
        return self.db.get(VM, vm_id)

    def count_for_user(self, user_id: int) -> int:
        return self.db.execute(
            select(func.count()).select_from(VM).where(VM.user_id == user_id)
        ).scalar_one()

    def list_for_user(self, user_id: int | None, offset: int, limit: int) -> tuple[list[VM], int]:
        query = select(VM)
        count_query = select(func.count()).select_from(VM)
        if user_id is not None:
            query = query.where(VM.user_id == user_id)
            count_query = count_query.where(VM.user_id == user_id)
        total = self.db.execute(count_query).scalar_one()
        items = list(self.db.execute(query.offset(
            offset).limit(limit)).scalars().all())
        return items, total

    def list_all(self, offset: int, limit: int) -> tuple[list[VM], int]:
        return self.list_for_user(None, offset, limit)

    def create(self, data: VMCreate) -> VM:
        vm = VM(**data.model_dump())
        self.db.add(vm)
        self.db.flush()
        return vm

    def update(self, vm: VM, data: VMUpdate) -> VM:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(vm, field, value)
        self.db.flush()
        return vm

    def delete(self, vm: VM) -> None:
        self.db.delete(vm)
        self.db.flush()

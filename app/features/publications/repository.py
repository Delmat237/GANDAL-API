from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.shared.models import Publication
from app.shared.schemas.publication import PublicationCreate, PublicationUpdate


class PublicationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, publication_id: int) -> Publication | None:
        return self.db.get(Publication, publication_id)

    def list_by_user(self, user_id: int, offset: int, limit: int) -> tuple[list[Publication], int]:
        q = select(Publication).where(Publication.user_id == user_id)
        total = self.db.execute(
            select(func.count()).select_from(Publication).where(
                Publication.user_id == user_id)
        ).scalar_one()
        items = list(self.db.execute(
            q.offset(offset).limit(limit)).scalars().all())
        return items, total

    def list_published(self, offset: int, limit: int) -> tuple[list[Publication], int]:
        q = select(Publication).where(Publication.status == "published")
        total = self.db.execute(
            select(func.count()).select_from(Publication).where(
                Publication.status == "published")
        ).scalar_one()
        items = list(self.db.execute(
            q.offset(offset).limit(limit)).scalars().all())
        return items, total

    def list_all(self, offset: int, limit: int) -> tuple[list[Publication], int]:
        total = self.db.execute(
            select(func.count()).select_from(Publication)).scalar_one()
        items = list(self.db.execute(select(Publication).offset(
            offset).limit(limit)).scalars().all())
        return items, total

    def create(self, data: PublicationCreate) -> Publication:
        pub = Publication(**data.model_dump())
        self.db.add(pub)
        self.db.flush()
        return pub

    def update(self, pub: Publication, data: PublicationUpdate) -> Publication:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(pub, field, value)
        self.db.flush()
        return pub

    def delete(self, pub: Publication) -> None:
        self.db.delete(pub)
        self.db.flush()

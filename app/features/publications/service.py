from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.features.publications.repository import PublicationRepository
from app.shared.models import Teacher, User
from app.shared.policies.permissions import AuthorizationPolicy
from app.shared.schemas.publication import PublicationCreate, PublicationUpdate


class PublicationService:
    def __init__(self, db: Session) -> None:
        self.repo = PublicationRepository(db)
        self.db = db

    def _can_manage(self, user: User, pub_user_id: int) -> bool:
        if AuthorizationPolicy.is_admin_or_superadmin(user):
            return True
        if isinstance(user, Teacher):
            return user.id == pub_user_id
        return False

    def get(self, user: User, publication_id: int):
        pub = self.repo.get(publication_id)
        if pub is None:
            raise NotFoundError("Publication introuvable")
        if pub.status == "published":
            return pub
        if not self._can_manage(user, pub.user_id):
            raise ForbiddenError()
        return pub

    def list_public(self, page: int, size: int):
        offset = (page - 1) * size
        return self.repo.list_published(offset, size)

    def list(self, user: User, page: int, size: int):
        offset = (page - 1) * size
        if AuthorizationPolicy.is_admin_or_superadmin(user):
            return self.repo.list_all(offset, size)
        if isinstance(user, Teacher):
            return self.repo.list_by_user(user.id, offset, size)
        return self.repo.list_published(offset, size)

    def create(self, user: User, data: PublicationCreate):
        if not isinstance(user, Teacher) and not AuthorizationPolicy.is_admin_or_superadmin(user):
            raise ForbiddenError("Seuls les enseignants peuvent publier")
        data.user_id = user.id
        pub = self.repo.create(data)
        self.db.commit()
        self.db.refresh(pub)
        return pub

    def update(self, user: User, publication_id: int, data: PublicationUpdate):
        pub = self.repo.get(publication_id)
        if pub is None:
            raise NotFoundError()
        if not self._can_manage(user, pub.user_id):
            raise ForbiddenError()
        pub = self.repo.update(pub, data)
        self.db.commit()
        self.db.refresh(pub)
        return pub

    def delete(self, user: User, publication_id: int) -> None:
        pub = self.repo.get(publication_id)
        if pub is None:
            raise NotFoundError()
        if not self._can_manage(user, pub.user_id):
            raise ForbiddenError()
        self.repo.delete(pub)
        self.db.commit()

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_superadmin
from app.features.publications.service import PublicationService
from app.shared.models import Publication, User
from app.shared.schemas.common import PaginatedResponse, PaginationParams
from app.shared.schemas.publication import PublicationCreate, PublicationRead, PublicationUpdate

router = APIRouter(prefix="/publications", tags=["publications"])


@router.get("/public", response_model=PaginatedResponse[PublicationRead])
def list_public_publications(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> PaginatedResponse[PublicationRead]:
    items, total = PublicationService(db).list_public(
        pagination.page, pagination.size)
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.post("", response_model=PublicationRead, status_code=201)
def create_publication(
    data: PublicationCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Publication:
    return PublicationService(db).create(current_user, data)


@router.get("/pending", response_model=PaginatedResponse[PublicationRead])
def list_pending_publications(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
) -> PaginatedResponse[PublicationRead]:
    """Demandes de publication en attente de validation (super admin)."""
    items, total = PublicationService(db).list_pending(
        current_user, pagination.page, pagination.size)
    return PaginatedResponse(
        items=items, total=total, page=pagination.page, size=pagination.size)


@router.post("/{publication_id}/validate", response_model=PublicationRead)
def validate_publication(
    publication_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
) -> Publication:
    """Valide une publication → elle apparaît au catalogue (super admin)."""
    return PublicationService(db).set_status(current_user, publication_id, "published")


@router.post("/{publication_id}/reject", response_model=PublicationRead)
def reject_publication(
    publication_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
) -> Publication:
    """Rejette une demande de publication (super admin)."""
    return PublicationService(db).set_status(current_user, publication_id, "archived")


@router.get("", response_model=PaginatedResponse[PublicationRead])
def list_publications(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PaginatedResponse[PublicationRead]:
    items, total = PublicationService(db).list(
        current_user, pagination.page, pagination.size)
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.get("/{publication_id}", response_model=PublicationRead)
def get_publication(
    publication_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Publication:
    return PublicationService(db).get(current_user, publication_id)


@router.patch("/{publication_id}", response_model=PublicationRead)
def update_publication(
    publication_id: int,
    data: PublicationUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Publication:
    return PublicationService(db).update(current_user, publication_id, data)


@router.delete("/{publication_id}", status_code=204)
def delete_publication(
    publication_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    PublicationService(db).delete(current_user, publication_id)

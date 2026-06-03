from typing import Annotated, Union

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.features.auth.service import AuthService
from app.shared.models import Teacher, User
from app.shared.schemas.auth import AdminCreate, LoginRequest, TokenResponse
from app.shared.schemas.user import StudentRead, TeacherRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    data: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    return AuthService(db).login(data)


@router.post("/register-admin", response_model=TeacherRead, status_code=201)
def register_admin(
    data: AdminCreate,
    db: Annotated[Session, Depends(get_db)],
) -> Teacher:
    """
    Crée un compte administrateur.

    Endpoint de bootstrap : ne requiert pas d'authentification préalable, mais
    exige la clé secrète SuperAdmin (`secret_key`) définie dans la configuration
    (`SUPERADMIN_SECRET_KEY`).
    """
    return AuthService(db).register_admin(data)


@router.get("/me")
def me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Union[StudentRead, TeacherRead, dict]:
    return AuthService(db).get_me(current_user)

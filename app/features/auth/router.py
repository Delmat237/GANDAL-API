from typing import Annotated, Union

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.features.auth.service import AuthService
from app.shared.models import User
from app.shared.schemas.auth import LoginRequest, TokenResponse
from app.shared.schemas.user import StudentRead, TeacherRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    data: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    return AuthService(db).login(data)


@router.get("/me")
def me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Union[StudentRead, TeacherRead, dict]:
    return AuthService(db).get_me(current_user)

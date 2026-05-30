from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.shared.models import Teacher, User
from app.shared.policies.permissions import AuthorizationPolicy

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError()
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except Exception as exc:
        raise UnauthorizedError("Token invalide") from exc

    user = db.get(User, user_id)
    if user is None:
        raise UnauthorizedError("Utilisateur introuvable")
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not AuthorizationPolicy.is_admin_or_superadmin(user):
        raise ForbiddenError("Droits administrateur requis")
    return user


def require_teacher_or_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not isinstance(user, Teacher):
        raise ForbiddenError("Enseignant ou administrateur requis")
    return user


def require_roles(*roles: str) -> Callable[..., User]:
    def _checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if isinstance(user, Teacher) and user.role in roles:
            return user
        if AuthorizationPolicy.is_admin_or_superadmin(user):
            return user
        raise ForbiddenError(f"Rôle requis : {', '.join(roles)}")

    return _checker

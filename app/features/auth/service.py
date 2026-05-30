from sqlalchemy.orm import Session

from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token, verify_password
from app.features.users.repository import UserRepository
from app.shared.models import Student, Teacher, User
from app.shared.schemas.auth import LoginRequest, TokenResponse
from app.shared.schemas.user import StudentRead, TeacherRead


class AuthService:
    def __init__(self, db: Session) -> None:
        self.repo = UserRepository(db)

    def login(self, data: LoginRequest) -> TokenResponse:
        user = self.repo.get_by_username(data.username)
        if user is None or not verify_password(data.password, user.password):
            raise UnauthorizedError("Identifiants invalides")
        token = create_access_token(user.id, extra_claims={"type": user.type})
        return TokenResponse(access_token=token)

    def get_me(self, user: User) -> StudentRead | TeacherRead | dict:
        if isinstance(user, Student):
            return StudentRead.model_validate(user)
        if isinstance(user, Teacher):
            return TeacherRead.model_validate(user)
        return {"id": user.id, "username": user.username, "email": user.email, "type": user.type}

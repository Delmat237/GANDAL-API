import secrets

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import create_access_token, verify_password
from app.features.users.repository import UserRepository
from app.features.users.service import UserService
from app.shared.models import Student, Teacher, User
from app.shared.schemas.auth import AdminCreate, LoginRequest, TokenResponse
from app.shared.schemas.user import StudentRead, TeacherCreate, TeacherRead


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = UserRepository(db)

    def register_admin(self, data: AdminCreate) -> Teacher:
        """Crée un administrateur après vérification de la clé secrète SuperAdmin."""
        expected = get_settings().superadmin_secret_key
        if not secrets.compare_digest(data.secret_key, expected):
            raise ForbiddenError("Clé secrète SuperAdmin invalide")
        teacher_data = TeacherCreate(
            username=data.username,
            email=data.email,
            password=data.password,
            role=data.role,
        )
        return UserService(self.db).create_teacher(teacher_data)

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

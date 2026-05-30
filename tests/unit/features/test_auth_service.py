from app.core.exceptions import UnauthorizedError
from app.core.security import hash_password
from app.features.auth.service import AuthService
from app.shared.models import Student
from app.shared.schemas.auth import LoginRequest


def test_login_success(db_session):
    s = Student(
        username="u1",
        email="u1@x.com",
        password=hash_password("pass"),
        matricule="M1",
        level="L1",
        departement="CS",
    )
    db_session.add(s)
    db_session.commit()
    token = AuthService(db_session).login(
        LoginRequest(username="u1", password="pass"))
    assert token.access_token


def test_login_failure(db_session):
    import pytest

    with pytest.raises(UnauthorizedError):
        AuthService(db_session).login(
            LoginRequest(username="nobody", password="x"))

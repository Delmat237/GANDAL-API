import os
from pathlib import Path

# Les variables d'environnement doivent être définies AVANT d'importer quoi que
# ce soit depuis `app`, car `app.core.database` crée le moteur SQLAlchemy dès
# l'import (sinon il tenterait de se connecter à PostgreSQL et exigerait psycopg2).
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./.pytest_dc.db"
os.environ["JWT_SECRET"] = "test-secret-key-at-least-32-bytes-long"
os.environ["PROXMOX_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.shared.models import Base, Student, Teacher
from app.main import create_app
from app.infrastructure.proxmox.mock_client import MockProxmoxGateway
from app.core.security import hash_password
from app.core.database import get_db
from app.core.config import get_settings


@pytest.fixture
def db_engine(monkeypatch):
    db_path = Path(__file__).resolve().parent.parent / ".pytest_dc.db"
    if db_path.exists():
        db_path.unlink()
    get_settings.cache_clear()
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(
        autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr("app.core.database.engine", engine)
    monkeypatch.setattr("app.core.database.SessionLocal",
                        testing_session_local)
    yield engine, testing_session_local
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if db_path.exists():
        db_path.unlink()
    get_settings.cache_clear()


@pytest.fixture
def db_session(db_engine) -> Session:
    _, session_factory = db_engine
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def mock_proxmox():
    return MockProxmoxGateway()


@pytest.fixture
def client(db_engine, mock_proxmox):
    _, session_factory = db_engine

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    from app.infrastructure import factories

    mp = pytest.MonkeyPatch()
    mp.setattr(factories, "get_proxmox_gateway", lambda: mock_proxmox)

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    mp.undo()
    app.dependency_overrides.clear()


@pytest.fixture
def seed_users(db_session):
    pwd = hash_password("changeme123")
    admin = Teacher(username="admin", email="admin@example.com",
                    password=pwd, role="SuperAdmin")
    teacher = Teacher(username="teacher",
                      email="teacher@example.com", password=pwd, role="Teacher")
    student = Student(
        username="student",
        email="student@example.com",
        password=pwd,
        matricule="STU001",
        level="L3",
        departement="Computer Science",
    )
    db_session.add_all([admin, teacher, student])
    db_session.commit()
    db_session.refresh(admin)
    db_session.refresh(teacher)
    db_session.refresh(student)
    return {"admin": admin, "teacher": teacher, "student": student}


def auth_header(client: TestClient, username: str, password: str = "changeme123") -> dict:
    r = client.post("/api/v1/auth/login",
                    json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

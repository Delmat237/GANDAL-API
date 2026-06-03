"""Seed development users. Run: python scripts/seed_dev.py"""

from app.shared.models import Base, Student, Teacher
from app.core.config import get_settings
from app.core.security import hash_password
from app.core.database import SessionLocal, engine
from sqlalchemy.orm import Session
from sqlalchemy import select
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def seed() -> None:
    settings = get_settings()
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    password = hash_password("changeme123")

    if not db.execute(select(Teacher).where(Teacher.username == settings.superadmin_username)).scalar_one_or_none():
        admin = Teacher(
            username=settings.superadmin_username,
            email=settings.superadmin_email,
            password=hash_password(settings.superadmin_password),
            role="SuperAdmin",
        )
        db.add(admin)

    if not db.execute(select(Teacher).where(Teacher.username == "teacher")).scalar_one_or_none():
        teacher = Teacher(
            username="teacher",
            email="teacher@dc.local",
            password=password,
            role="Teacher",
        )
        db.add(teacher)

    if not db.execute(select(Student).where(Student.username == "student")).scalar_one_or_none():
        student = Student(
            username="student",
            email="student@dc.local",
            password=password,
            matricule="STU001",
            level="L3",
            departement="Computer Science",
        )
        db.add(student)

    db.commit()
    db.close()
    print(
        f"Seed OK: {settings.superadmin_username} (SuperAdmin) / teacher / student\n"
        f"  - {settings.superadmin_username}: password={settings.superadmin_password}\n"
        "  - teacher / student: password=changeme123"
    )


if __name__ == "__main__":
    seed()

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.features.users.service import UserService
from app.shared.models import Student, Teacher, User
from app.shared.schemas.common import PaginatedResponse, PaginationParams
from app.shared.schemas.user import (
    StudentCreate,
    StudentRead,
    StudentUpdate,
    TeacherCreate,
    TeacherRead,
    TeacherUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/students", response_model=StudentRead, status_code=201)
def create_student(
    data: StudentCreate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> Student:
    return UserService(db).create_student(data)


@router.get("/students", response_model=PaginatedResponse[StudentRead])
def list_students(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> PaginatedResponse[StudentRead]:
    items, total = UserService(db).list_students(
        pagination.page, pagination.size)
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.get("/students/{student_id}", response_model=StudentRead)
def get_student(
    student_id: int,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> Student:
    return UserService(db).get_student(student_id)


@router.patch("/students/{student_id}", response_model=StudentRead)
def update_student(
    student_id: int,
    data: StudentUpdate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> Student:
    return UserService(db).update_student(student_id, data)


@router.delete("/students/{student_id}", status_code=204)
def delete_student(
    student_id: int,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> None:
    UserService(db).delete_student(student_id)


@router.post("/teachers", response_model=TeacherRead, status_code=201)
def create_teacher(
    data: TeacherCreate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> Teacher:
    return UserService(db).create_teacher(data)


@router.get("/teachers", response_model=PaginatedResponse[TeacherRead])
def list_teachers(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> PaginatedResponse[TeacherRead]:
    items, total = UserService(db).list_teachers(
        pagination.page, pagination.size)
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.get("/teachers/{teacher_id}", response_model=TeacherRead)
def get_teacher(
    teacher_id: int,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> Teacher:
    return UserService(db).get_teacher(teacher_id)


@router.patch("/teachers/{teacher_id}", response_model=TeacherRead)
def update_teacher(
    teacher_id: int,
    data: TeacherUpdate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> Teacher:
    return UserService(db).update_teacher(teacher_id, data)


@router.delete("/teachers/{teacher_id}", status_code=204)
def delete_teacher(
    teacher_id: int,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> None:
    UserService(db).delete_teacher(teacher_id)

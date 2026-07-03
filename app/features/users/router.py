from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    get_current_user,
    require_admin,
    require_superadmin,
    require_teacher_or_admin,
)
from app.features.users.service import UserService
from app.shared.models import Student, Teacher, User
from app.shared.schemas.common import PaginatedResponse, PaginationParams
from app.shared.schemas.user import (
    StudentCreate,
    StudentRead,
    StudentUpdate,
    TeacherCreate,
    TeacherPublic,
    TeacherRead,
    TeacherUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/teachers/public", response_model=list[TeacherPublic])
def list_teachers_public(
    db: Annotated[Session, Depends(get_db)],
) -> list[Teacher]:
    """PUBLIC (sans authentification) : liste des enseignants pour le formulaire
    d'inscription, afin que l'étudiant choisisse son superviseur. Renvoie
    uniquement id + nom. Exclut le super admin (qui n'encadre pas d'étudiants)."""
    items, _ = UserService(db).list_teachers(1, 100)
    return [t for t in items if t.role != "SuperAdmin"]


@router.post("/students", response_model=StudentRead, status_code=201)
def create_student(
    data: StudentCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_teacher_or_admin)],
) -> Student:
    """Un enseignant (ou le super admin) crée un étudiant. L'étudiant est rattaché
    à l'enseignant créateur comme superviseur (le super admin peut préciser un
    autre superviseur via supervisor_id) et son compte est actif immédiatement."""
    return UserService(db).create_student(data, creator=current_user)


@router.get("/students", response_model=PaginatedResponse[StudentRead])
def list_students(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_teacher_or_admin)],
) -> PaginatedResponse[StudentRead]:
    # Super admin → tous les étudiants ; enseignant → seulement les siens.
    items, total = UserService(db).list_students_for(
        current_user, pagination.page, pagination.size)
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


@router.post("/students/{student_id}/block", response_model=StudentRead)
def block_student(
    student_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_teacher_or_admin)],
) -> Student:
    """Bloque (désactive) un étudiant. Superviseur ou super admin uniquement."""
    return UserService(db).set_student_active(current_user, student_id, False)


@router.post("/students/{student_id}/unblock", response_model=StudentRead)
def unblock_student(
    student_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_teacher_or_admin)],
) -> Student:
    """Réactive un étudiant. Superviseur ou super admin uniquement."""
    return UserService(db).set_student_active(current_user, student_id, True)


@router.delete("/students/{student_id}", status_code=204)
def delete_student(
    student_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_teacher_or_admin)],
) -> None:
    """Supprime définitivement un étudiant + ses VMs. Superviseur ou super admin."""
    UserService(db).delete_student(student_id, actor=current_user)


@router.post("/teachers", response_model=TeacherRead, status_code=201)
def create_teacher(
    data: TeacherCreate,
    db: Annotated[Session, Depends(get_db)],
    _sa: Annotated[User, Depends(require_superadmin)],
) -> Teacher:
    """Seul le super admin crée des enseignants. Un enseignant créé est toujours
    un simple « Teacher » (validation de ses propres étudiants) — il n'y a qu'un
    seul super admin, créé au bootstrap (`/auth/register-admin`)."""
    data.role = "Teacher"
    return UserService(db).create_teacher(data)


@router.get("/teachers", response_model=PaginatedResponse[TeacherRead])
def list_teachers(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> PaginatedResponse[TeacherRead]:
    # Liste lisible par tous (un étudiant choisit son enseignant à l'inscription).
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
    _user: Annotated[User, Depends(get_current_user)],
) -> Teacher:
    return UserService(db).get_teacher(teacher_id)


@router.patch("/teachers/{teacher_id}", response_model=TeacherRead)
def update_teacher(
    teacher_id: int,
    data: TeacherUpdate,
    db: Annotated[Session, Depends(get_db)],
    _sa: Annotated[User, Depends(require_superadmin)],
) -> Teacher:
    return UserService(db).update_teacher(teacher_id, data)


@router.post("/teachers/{teacher_id}/block", response_model=TeacherRead)
def block_teacher(
    teacher_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
) -> Teacher:
    return UserService(db).set_teacher_active(current_user, teacher_id, False)


@router.post("/teachers/{teacher_id}/unblock", response_model=TeacherRead)
def unblock_teacher(
    teacher_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
) -> Teacher:
    return UserService(db).set_teacher_active(current_user, teacher_id, True)


@router.delete("/teachers/{teacher_id}", status_code=204)
def delete_teacher(
    teacher_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
) -> None:
    """Seul le super admin supprime un enseignant (+ ses VMs)."""
    UserService(db).delete_teacher(teacher_id, actor=current_user)

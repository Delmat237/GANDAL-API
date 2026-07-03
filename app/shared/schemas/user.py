from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Literal, Optional

# Valeurs de rôle autorisées pour un enseignant. Doit rester aligné avec
# AuthorizationPolicy (app/shared/policies/permissions.py) qui s'appuie sur
# "Admin"/"SuperAdmin" pour les droits d'administration.
TeacherRole = Literal["Teacher", "Admin", "SuperAdmin"]


class UserBase(BaseModel):
    username: str
    email: EmailStr


# ── Student ──────────────────────────────────────────────────────────────────

class StudentCreate(UserBase):
    password: str
    matricule: str
    level: str
    departement: str
    # Optionnel : seul le super admin l'utilise pour désigner le superviseur.
    # Quand c'est un enseignant qui crée, le superviseur = lui (forcé serveur).
    supervisor_id: Optional[int] = None


class StudentUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    level: Optional[str] = None
    departement: Optional[str] = None


class StudentRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: Literal["student"]
    matricule: str
    level: str
    departement: str
    is_active: bool = True
    supervisor_id: Optional[int] = None


# ── Teacher ───────────────────────────────────────────────────────────────────

class TeacherCreate(UserBase):
    password: str
    role: TeacherRole = "Teacher"


class TeacherUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[TeacherRole] = None


class TeacherRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: Literal["teacher"]
    role: str
    is_active: bool = True


class TeacherPublic(BaseModel):
    """Vue minimale exposée publiquement (formulaire d'inscription étudiant) :
    juste de quoi choisir son enseignant superviseur, sans données sensibles."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str

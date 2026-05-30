from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Literal, Optional


class UserBase(BaseModel):
    username: str
    email: EmailStr


# ── Student ──────────────────────────────────────────────────────────────────

class StudentCreate(UserBase):
    password: str
    matricule: str
    level: str
    departement: str


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


# ── Teacher ───────────────────────────────────────────────────────────────────

class TeacherCreate(UserBase):
    password: str
    role: str


class TeacherUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None


class TeacherRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: Literal["teacher"]
    role: str

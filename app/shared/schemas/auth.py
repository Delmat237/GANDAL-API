from typing import Literal

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminCreate(BaseModel):
    """Création d'un compte administrateur, protégée par la clé secrète SuperAdmin."""

    username: str
    email: EmailStr
    password: str
    role: Literal["Admin", "SuperAdmin"] = "Admin"
    secret_key: str

from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Literal, Optional

RequeteStatus = Literal["pending", "validated", "rejected"]


class RequeteBase(BaseModel):
    object: str
    content: Optional[str] = None
    student_id: int
    teacher_id: int


class RequeteReadBase(RequeteBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    status: RequeteStatus


# ── RCreateVM ─────────────────────────────────────────────────────────────────

class RCreateVMCreate(BaseModel):
    object: str
    content: Optional[str] = None
    teacher_id: int
    size_rom: int
    size_ram: int
    n_cpu: int = 2
    os: str


class RCreateVMRead(RCreateVMCreate, RequeteReadBase):
    type: Literal["r_create_vm"]


# ── RDeleteVM ─────────────────────────────────────────────────────────────────

class RDeleteVMCreate(BaseModel):
    object: str
    content: Optional[str] = None
    teacher_id: int
    vm_id: int


class RDeleteVMRead(RDeleteVMCreate, RequeteReadBase):
    type: Literal["r_delete_vm"]


# ── RAccount ──────────────────────────────────────────────────────────────────

class RAccountCreate(BaseModel):
    object: str
    content: Optional[str] = None
    teacher_id: int
    nom: str
    email: EmailStr
    justification: Optional[str] = None
    matricule: Optional[str] = None
    organisation: Optional[str] = None


class RAccountRead(RAccountCreate, RequeteReadBase):
    type: Literal["r_account"]


class RDomainCreate(BaseModel):
    object: str
    content: Optional[str] = None
    teacher_id: int
    vm_id: int
    hostname: str   # nom_choisi (ex: monapp → monapp.enspy-gi.gandal)
    port: int       # port exposé dans la VM (3000, 5000, 8080...)


class RDomainRead(RDomainCreate, RequeteReadBase):
    type: Literal["r_domain"]

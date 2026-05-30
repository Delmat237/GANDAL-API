from pydantic import BaseModel, ConfigDict
from typing import Literal, Optional
from datetime import datetime

VMStatus = Literal["up", "waiting", "stopped"]


class VMBase(BaseModel):
    size_rom: int
    size_ram: int
    n_cpu: int
    status: VMStatus = "stopped"
    iso: Optional[str] = None
    ip_address: Optional[str] = None
    id_proxmox: Optional[int] = None
    node: Optional[str] = None
    iso_image: Optional[str] = None
    ssh_public_key: Optional[str] = None


class VMCreate(VMBase):
    user_id: int


class VMUpdate(BaseModel):
    size_rom: Optional[int] = None
    size_ram: Optional[int] = None
    n_cpu: Optional[int] = None
    status: Optional[str] = None
    iso: Optional[str] = None
    ip_address: Optional[str] = None
    id_proxmox: Optional[int] = None
    node: Optional[str] = None
    iso_image: Optional[str] = None
    ssh_public_key: Optional[str] = None
    date_stop_at: Optional[datetime] = None


class VMRead(VMBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    date_stop_at: Optional[datetime] = None

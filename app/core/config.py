import json
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["local", "production", "test"] = "local"
    database_url: str = "postgresql://dc:dc@localhost:5432/dc_backend"
    test_database_url: str = "sqlite:///:memory:"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    superadmin_username: str = "admin"
    superadmin_email: str = "admin@dc.local"
    superadmin_password: str = "changeme123"
    superadmin_secret_key: str = "change-me-admin-secret"

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001"

    max_vms_per_student: int = 2
    default_page_size: int = 20

    proxmox_enabled: bool = False
    # Mode simulation : l'approbation d'une requête create-vm enregistre la VM
    # en base avec le statut "waiting" sans appeler Proxmox. Utile lorsque
    # l'hyperviseur n'est pas joignable (ex. déploiement Render).
    proxmox_simulation_mode: bool = False
    proxmox_host: str = "192.168.1.100"
    proxmox_user: str = "root@pam"
    proxmox_token_id: str = ""
    proxmox_token_secret: str = ""
    proxmox_verify_ssl: bool = False
    proxmox_default_node: str = "pve"
    proxmox_vm_storage: str = "local-lvm"
    proxmox_net0_template: str = "virtio,bridge=vmbr0"

    email_backend: Literal["log", "smtp"] = "log"
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "noreply@dc-backend.local"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, value: str | list[str]) -> str:
        if isinstance(value, list):
            return ",".join(value)
        return value

    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw.startswith("["):
            return json.loads(raw)
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def is_local(self) -> bool:
        return self.environment == "local"

    @property
    def effective_email_backend(self) -> Literal["log", "smtp"]:
        if self.is_local:
            return "log"
        return self.email_backend


@lru_cache
def get_settings() -> Settings:
    return Settings()

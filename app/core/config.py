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

    # ── Backend Omega on-premise ─────────────────────────────────────────────
    # Sélecteur d'implémentation du ProxmoxGateway :
    #   "auto"   → omega si pvesh local (= sur un nœud PVE) sinon mock
    #   "omega"  → force le gateway Omega (pilote nos scripts omega-remote-paging)
    #   "proxmoxer" → client proxmoxer historique des collègues
    #   "mock"   → mock en mémoire
    proxmox_backend: Literal["auto", "omega", "proxmoxer", "mock"] = "auto"
    # Racine du dépôt omega-remote-paging (contient scripts/). Sur emilia : /opt/omega-remote-paging.
    omega_repo_root: str = "/opt/omega-remote-paging"
    omega_cluster_conf: str = ""        # vide = <repo_root>/scripts/cluster.conf
    omega_controller_host: str = ""     # vide = OMEGA_CONTROLLER de cluster.conf (mode ssh)
    omega_ssh_user: str = "root"
    omega_ssh_key: str = ""             # vide = SSH_KEY de cluster.conf
    omega_exec_mode: Literal["auto", "local", "ssh"] = "auto"
    omega_cmd_timeout_secs: int = 30
    omega_ssh_retries: int = 2          # retries sur échec SSH transitoire (jitter LAN)
    omega_ssh_retry_backoff_secs: float = 0.8
    # Racine des scripts omega PRÉSENTS LOCALEMENT (pour les scripts pfSense exécutés
    # en local sur la console VM, qui joint pfSense contrairement à emilia). Vide =
    # <omega_repo_root>/scripts. Mettre /opt/omega-remote-paging sur la console VM.
    omega_local_scripts: str = "/opt/omega-remote-paging/scripts"
    # IP de l'hôte reverse-proxy (la VM console qui fait tourner Caddy + joint pfSense).
    # Sert à relier le proxy aux VMs backend (lien réseau) pour les domaines sans port.
    omega_proxy_host_ip: str = "10.50.30.50"
    # Exécuter les scripts pfSense (vm-internet/vm-link/dns) en local plutôt que sur
    # le contrôleur (recommandé quand exec_mode=ssh et le backend joint pfSense).
    omega_pfsense_local: bool = True
    # Gateway LLM unifiée (LiteLLM, OpenAI-compatible). Les VMs avec
    # omega_gpu_vram_mib > 0 reçoivent un accès réseau ÉTROIT vers cet hôte:port.
    omega_llm_gateway_ip: str = "192.168.123.100"
    omega_llm_gateway_port: int = 4000

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

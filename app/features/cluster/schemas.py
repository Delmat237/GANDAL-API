"""Schémas de l'API cluster (topologie pour la toile, actions réseau/internet)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class TopologyVM(BaseModel):
    vmid: int
    name: str | None = None
    node: str | None = None              # nœud-hôte PVE (emilia/ram/rem)
    status: str                          # up / stopped / waiting
    ip: str | None = None
    internet: bool = False               # connectée à internet ?
    maxcpu: int | None = None
    maxmem: int | None = None
    vram_mib: int = 0                     # GPU alloué (VRAM partagée)
    owner_id: int | None = None          # propriétaire (mapping DB), si connu
    owner_name: str | None = None


class TopologyLink(BaseModel):
    source: int                          # vmid
    target: int                          # vmid
    group_name: str | None = None


class TopologyResponse(BaseModel):
    hosts: list[str] = Field(default_factory=list)   # nœuds-hôtes (régions de la toile)
    vms: list[TopologyVM] = Field(default_factory=list)
    links: list[TopologyLink] = Field(default_factory=list)


class InternetToggle(BaseModel):
    enable: bool = True


class NetworkLinkRequest(BaseModel):
    vm_ids: list[int]
    enable: bool = True
    group_name: str | None = None


class ReconcileResult(BaseModel):
    ok: bool


class ReconfigureRequest(BaseModel):
    name: str | None = None
    vcpu_max: int | None = None      # plafond vCPU (élasticité conservée, plancher=1)
    ram_mib: int | None = None       # RAM max (Mio)
    disk_gib: int | None = None      # taille disque cible (agrandissement seul)
    vram_mib: int | None = None      # VRAM GPU allouée (0 = pas de GPU)


class GpuRequest(BaseModel):
    vram_mib: int = 4096             # 0 pour retirer le GPU


class AutostartRequest(BaseModel):
    enable: bool = True


class DnsRequest(BaseModel):
    hostname: str | None = None      # vide = nom par défaut omega-<vmid>


class ExposeRequest(BaseModel):
    service_port: int                # port du service DANS la VM
    ext_port: int | None = None      # port externe (pfSense). Vide = même port.
    hostname: str | None = None      # nom DNS → pfSense (accès par nom depuis le LAN)
    proto: str = "tcp"
    enable: bool = True              # False = retirer l'exposition


class DomainRequest(BaseModel):
    """Domaine SANS port : http://nom.enspy-gi.gandal → service VM (reverse proxy)."""
    hostname: str                    # nom (sous-domaine), sans le suffixe
    port: int                        # port du service HTTP dans la VM
    enable: bool = True              # False = retirer le domaine


class CreateVMRequest(BaseModel):
    """Création directe d'une VM (bouton « + » de la toile). Pas de type d'OS :
    le projet impose son image (Debian/omega préparée)."""
    name: str | None = None
    vcpu: int = 4                    # plafond vCPU (élastique, plancher 1)
    ram_gb: int = 4
    disk_gb: int = 20
    vram_gb: int = 0                 # GPU partagé (0 = aucun)
    internet: bool = False           # ouvrir Internet dès la création
    autostart: bool = False          # always-on


class CreateVMResponse(BaseModel):
    vm_id: int                       # id applicatif
    vmid: int | None = None          # VMID Proxmox (dispo une fois alloué)
    status: str
    job: str = "provisioning"

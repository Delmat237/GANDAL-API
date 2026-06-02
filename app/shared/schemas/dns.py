from pydantic import BaseModel, ConfigDict, field_validator
import re
from typing import Optional

# ── Validators ────────────────────────────────────────────────────────────────

HOSTNAME_RE = re.compile(
    r"^(?:[a-zA-Z0-9]"
    r"(?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z]{2,}$"
)


def _validate_hostname(v: str) -> str:
    if not HOSTNAME_RE.match(v):
        raise ValueError(
            f"'{v}' n'est pas un nom de domaine valide (ex: mon-projet.dc.enspy.cm)"
        )
    return v.lower()


# ── Schemas ───────────────────────────────────────────────────────────────────

class DNSEntryBase(BaseModel):
    """Champs partagés entre la création et la lecture d'une entrée DNS."""
    hostname: str
    """Nom de domaine complet (FQDN) pointant vers la VM, ex: api.monprojet.dc.enspy.cm"""

    vm_id: int
    """Identifiant de la VM cible."""

    @field_validator("hostname")
    @classmethod
    def validate_hostname(cls, v: str) -> str:
        return _validate_hostname(v)


class DNSEntryCreate(DNSEntryBase):
    """Payload pour créer une entrée DNS."""
    pass


class DNSEntryUpdate(BaseModel):
    """Payload partiel pour modifier une entrée DNS."""
    hostname: Optional[str] = None

    @field_validator("hostname")
    @classmethod
    def validate_hostname(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return _validate_hostname(v)
        return v


class DNSEntryRead(DNSEntryBase):
    """Réponse renvoyée au client, inclut les champs générés par la BDD."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    ip_address: Optional[str] = None
    """Adresse IP résolue depuis la VM associée (dénormalisée pour la lecture)."""

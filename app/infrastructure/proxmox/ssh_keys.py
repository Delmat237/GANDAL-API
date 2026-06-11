import base64
from dataclasses import dataclass

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

_OPENSSH_PUBKEY_TYPES = (
    "ssh-rsa",
    "ssh-ed25519",
    "ssh-dss",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
)


@dataclass(frozen=True)
class ResolvedSshKey:
    public_key: str
    private_key: str | None = None
    was_generated: bool = False


def is_valid_ssh_public_key(key: str | None) -> bool:
    """Vérifie qu'une chaîne ressemble à une clé publique OpenSSH acceptée par Proxmox."""
    candidate = (key or "").strip()
    if not candidate or "mock" in candidate.lower():
        return False

    parts = candidate.split()
    if len(parts) < 2 or parts[0] not in _OPENSSH_PUBKEY_TYPES:
        return False

    try:
        blob = base64.b64decode(parts[1], validate=True)
    except Exception:
        return False

    # Taille minimale du blob (clé réelle, pas un placeholder court).
    return len(blob) >= 32


def generate_ssh_key_pair() -> tuple[str, str]:
    """Génère une paire Ed25519 au format OpenSSH."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    public_openssh = public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    ).decode()
    private_openssh = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    return public_openssh, private_openssh


def resolve_ssh_public_key(key: str | None) -> ResolvedSshKey:
    """Retourne une clé publique valide ; en génère une si l'entrée est absente ou invalide."""
    candidate = (key or "").strip()
    if is_valid_ssh_public_key(candidate):
        return ResolvedSshKey(public_key=candidate)

    public_key, private_key = generate_ssh_key_pair()
    return ResolvedSshKey(
        public_key=public_key,
        private_key=private_key,
        was_generated=True,
    )

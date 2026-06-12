from app.application.ports.email_port import EmailPort
from app.application.ports.proxmox_gateway import ProxmoxGateway
from app.core.config import get_settings
from app.infrastructure.email.log_sender import LogEmailSender
from app.infrastructure.email.smtp_sender import SmtpEmailSender
from app.infrastructure.proxmox.adapter import ProxmoxGatewayAdapter
from app.infrastructure.proxmox.mock_client import MockProxmoxGateway


def _omega_available() -> bool:
    """Vrai si on peut piloter le cluster Omega (pvesh local OU contrôleur SSH joignable)."""
    import shutil

    from app.infrastructure.proxmox.omega_runner import OmegaRunner
    if shutil.which("pvesh"):
        return True
    try:
        return bool(OmegaRunner().controller)
    except Exception:  # noqa: BLE001
        return False


def get_proxmox_gateway() -> ProxmoxGateway:
    """Sélectionne l'implémentation du port selon settings.proxmox_backend.

    - omega     : pilote nos scripts omega-remote-paging (distribution 1/2/2, etc.)
    - proxmoxer : client proxmoxer historique (collègues)
    - mock      : mock en mémoire (tests/Render)
    - auto      : omega si dispo, sinon (proxmox_enabled→proxmoxer) sinon mock
    """
    settings = get_settings()
    backend = getattr(settings, "proxmox_backend", "auto")

    if backend == "mock":
        return MockProxmoxGateway()
    if backend == "omega":
        from app.infrastructure.proxmox.omega_gateway import OmegaScriptGateway
        return OmegaScriptGateway()
    if backend == "proxmoxer":
        return ProxmoxGatewayAdapter()

    # auto
    if _omega_available():
        from app.infrastructure.proxmox.omega_gateway import OmegaScriptGateway
        return OmegaScriptGateway()
    if settings.proxmox_enabled:
        return ProxmoxGatewayAdapter()
    return MockProxmoxGateway()


def get_email_sender() -> EmailPort:
    settings = get_settings()
    if settings.effective_email_backend == "smtp":
        return SmtpEmailSender()
    return LogEmailSender()

from app.application.ports.email_port import EmailPort
from app.application.ports.proxmox_gateway import ProxmoxGateway
from app.core.config import get_settings
from app.infrastructure.email.log_sender import LogEmailSender
from app.infrastructure.email.smtp_sender import SmtpEmailSender
from app.infrastructure.proxmox.adapter import ProxmoxGatewayAdapter
from app.infrastructure.proxmox.mock_client import MockProxmoxGateway


def get_proxmox_gateway() -> ProxmoxGateway:
    settings = get_settings()
    if not settings.proxmox_enabled:
        return MockProxmoxGateway()
    return ProxmoxGatewayAdapter()


def get_email_sender() -> EmailPort:
    settings = get_settings()
    if settings.effective_email_backend == "smtp":
        return SmtpEmailSender()
    return LogEmailSender()

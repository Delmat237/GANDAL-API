from app.infrastructure import factories
from app.infrastructure.email.log_sender import LogEmailSender
from app.infrastructure.proxmox.mock_client import MockProxmoxGateway


def test_get_proxmox_gateway_mock_when_disabled(monkeypatch):
    monkeypatch.setenv("PROXMOX_ENABLED", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    gw = factories.get_proxmox_gateway()
    assert isinstance(gw, MockProxmoxGateway)
    get_settings.cache_clear()


def test_get_email_sender_log_in_test_env(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "local")
    from app.core.config import get_settings

    get_settings.cache_clear()
    sender = factories.get_email_sender()
    assert isinstance(sender, LogEmailSender)
    get_settings.cache_clear()

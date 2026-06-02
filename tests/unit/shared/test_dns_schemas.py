"""
Tests unitaires – Schémas Pydantic DNS
Vérifie la validation des hostnames FQDN.
"""
import pytest
from pydantic import ValidationError

from app.shared.schemas.dns import DNSEntryCreate, DNSEntryUpdate


# ── DNSEntryCreate ─────────────────────────────────────────────────────────────

class TestDNSEntryCreateValidation:
    def test_valid_hostname_simple(self):
        entry = DNSEntryCreate(hostname="projet.dc.enspy.cm", vm_id=1)
        assert entry.hostname == "projet.dc.enspy.cm"

    def test_valid_hostname_subdomain(self):
        entry = DNSEntryCreate(hostname="api.mon-projet.dc.enspy.cm", vm_id=1)
        assert entry.hostname == "api.mon-projet.dc.enspy.cm"

    def test_hostname_is_lowercased(self):
        entry = DNSEntryCreate(hostname="API.Projet.DC.ENSPY.CM", vm_id=1)
        assert entry.hostname == "api.projet.dc.enspy.cm"

    def test_invalid_hostname_no_tld(self):
        with pytest.raises(ValidationError) as exc_info:
            DNSEntryCreate(hostname="monprojet", vm_id=1)
        assert "valide" in str(exc_info.value)

    def test_invalid_hostname_starts_with_dot(self):
        with pytest.raises(ValidationError):
            DNSEntryCreate(hostname=".projet.dc.enspy.cm", vm_id=1)

    def test_invalid_hostname_empty(self):
        with pytest.raises(ValidationError):
            DNSEntryCreate(hostname="", vm_id=1)

    def test_invalid_hostname_spaces(self):
        with pytest.raises(ValidationError):
            DNSEntryCreate(hostname="mon projet.dc.cm", vm_id=1)

    def test_invalid_hostname_ip_address(self):
        with pytest.raises(ValidationError):
            DNSEntryCreate(hostname="192.168.1.1", vm_id=1)


# ── DNSEntryUpdate ─────────────────────────────────────────────────────────────

class TestDNSEntryUpdateValidation:
    def test_update_with_valid_hostname(self):
        upd = DNSEntryUpdate(hostname="nouveau.dc.enspy.cm")
        assert upd.hostname == "nouveau.dc.enspy.cm"

    def test_update_hostname_none_is_allowed(self):
        """Un update vide est valide (PATCH partiel)."""
        upd = DNSEntryUpdate()
        assert upd.hostname is None

    def test_update_with_invalid_hostname(self):
        with pytest.raises(ValidationError):
            DNSEntryUpdate(hostname="invalid")

    def test_update_hostname_lowercased(self):
        upd = DNSEntryUpdate(hostname="UPPER.DC.ENSPY.CM")
        assert upd.hostname == "upper.dc.enspy.cm"

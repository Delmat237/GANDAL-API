import pytest

from app.infrastructure.proxmox.constants import resolve_template_for_os, resolve_vlan_for_department


def test_resolve_vlan_for_department_known():
    assert resolve_vlan_for_department("Computer Science") == 105


def test_resolve_vlan_for_department_default():
    assert resolve_vlan_for_department("Unknown") == 100


@pytest.mark.parametrize(
    "os_name,expected_template",
    [
        ("Ubuntu", 2299),
        ("ubuntu", 2299),
        ("Ubuntu 22.04", 2299),
        ("  ubuntu   22.04  ", 2299),
        ("Debian", 9001),
        ("debian", 9001),
        ("Debian 12", 9001),
        ("  debian   12  ", 9001),
    ]
)
def test_resolve_template_for_os_valid(os_name, expected_template):
    assert resolve_template_for_os(os_name) == expected_template


@pytest.mark.parametrize(
    "os_name",
    [
        "Windows",
        "CentOS",
        "unknown_os",
        "",
        None,
    ]
)
def test_resolve_template_for_os_invalid(os_name):
    with pytest.raises(ValueError) as exc_info:
        resolve_template_for_os(os_name)
    assert "OS non supporté" in str(exc_info.value)
    assert "Ubuntu 22.04" in str(exc_info.value)
    assert "Debian 12" in str(exc_info.value)


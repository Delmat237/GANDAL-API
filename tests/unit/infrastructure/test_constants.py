import pytest

from app.infrastructure.proxmox.constants import resolve_template_for_os, resolve_vlan_for_department


def test_resolve_vlan_for_department_known():
    assert resolve_vlan_for_department("Computer Science") == 105


def test_resolve_vlan_for_department_default():
    assert resolve_vlan_for_department("Unknown") == 100


def test_resolve_template_for_os_valid():
    assert resolve_template_for_os("Ubuntu 22.04") == 9000


def test_resolve_template_for_os_invalid():
    with pytest.raises(ValueError):
        resolve_template_for_os("Windows XP")

from app.infrastructure.proxmox.mock_client import MockProxmoxGateway


def test_provision_new_vm_returns_result():
    gw = MockProxmoxGateway()
    result = gw.provision_new_vm(
        "vm-test", 9000, 2.0, 2, "ssh-rsa key", vlan_id=105)
    assert result.vmid == 1000
    assert result.name == "vm-test"
    assert len(gw.calls) == 1


def test_start_vm_updates_status():
    gw = MockProxmoxGateway()
    r = gw.provision_new_vm("vm", 9000, 1.0, 1, "key")
    gw.start_vm(r.node, r.vmid)
    assert gw.vms[r.vmid]["status"] == "up"


def test_destroy_vm_removes():
    gw = MockProxmoxGateway()
    r = gw.provision_new_vm("vm", 9000, 1.0, 1, "key")
    gw.destroy_vm(r.vmid)
    assert r.vmid not in gw.vms


def test_get_vm_status():
    gw = MockProxmoxGateway()
    r = gw.provision_new_vm("vm", 9000, 1.0, 1, "key")
    status = gw.get_vm_status(r.node, r.vmid)
    assert "status" in status

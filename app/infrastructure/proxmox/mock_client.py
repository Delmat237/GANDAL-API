from dataclasses import dataclass, field

from app.application.ports.proxmox_gateway import ProvisionResult


@dataclass
class MockProxmoxGateway:
    """Fake Proxmox gateway for local dev and tests."""

    _next_vmid: int = 1000
    calls: list[tuple[str, dict]] = field(default_factory=list)
    vms: dict[int, dict] = field(default_factory=dict)

    def _record(self, method: str, **kwargs: object) -> None:
        self.calls.append((method, kwargs))

    def provision_new_vm(
        self,
        name: str,
        template_vmid: int,
        ram_gb: float,
        vcpu: int,
        ssh_pub_key: str,
        vlan_id: int | None = None,
    ) -> ProvisionResult:
        self._record(
            "provision_new_vm",
            name=name,
            template_vmid=template_vmid,
            ram_gb=ram_gb,
            vcpu=vcpu,
            vlan_id=vlan_id,
        )
        vmid = self._next_vmid
        self._next_vmid += 1
        node = "pve-mock"
        self.vms[vmid] = {"name": name, "status": "up", "node": node}
        return ProvisionResult(vmid=vmid, name=name, node=node, status="up")

    def start_vm(self, node: str, vmid: int) -> None:
        self._record("start_vm", node=node, vmid=vmid)
        if vmid in self.vms:
            self.vms[vmid]["status"] = "up"

    def stop_vm(self, node: str, vmid: int) -> None:
        self._record("stop_vm", node=node, vmid=vmid)
        if vmid in self.vms:
            self.vms[vmid]["status"] = "stopped"

    def destroy_vm(self, vmid: int) -> None:
        self._record("destroy_vm", vmid=vmid)
        self.vms.pop(vmid, None)

    def get_vm_status(self, node: str, vmid: int) -> dict:
        self._record("get_vm_status", node=node, vmid=vmid)
        vm = self.vms.get(vmid, {"status": "stopped"})
        return {"status": vm.get("status", "stopped")}

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ProvisionResult:
    vmid: int
    name: str
    node: str
    status: str
    ip_address: str | None = None


class ProxmoxGateway(Protocol):
    def provision_new_vm(
        self,
        name: str,
        template_vmid: int,
        ram_gb: float,
        vcpu: int,
        ssh_pub_key: str,
        vlan_id: int | None = None,
    ) -> ProvisionResult: ...

    def start_vm(self, node: str, vmid: int) -> None: ...

    def stop_vm(self, node: str, vmid: int) -> None: ...

    def destroy_vm(self, vmid: int) -> None: ...

    def get_vm_status(self, node: str, vmid: int) -> dict: ...

    def get_vm_ip(self, node: str, vmid: int) -> str | None: ...

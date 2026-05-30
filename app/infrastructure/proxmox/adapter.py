from app.application.ports.proxmox_gateway import ProvisionResult
from app.infrastructure.proxmox.service import VMService


class ProxmoxGatewayAdapter:
    """Adapts VMService to the ProxmoxGateway port."""

    def __init__(self, vm_service: VMService | None = None) -> None:
        self._service = vm_service or VMService()

    def provision_new_vm(
        self,
        name: str,
        template_vmid: int,
        ram_gb: float,
        vcpu: int,
        ssh_pub_key: str,
        vlan_id: int | None = None,
    ) -> ProvisionResult:
        return self._service.provision_new_vm(
            name=name,
            template_vmid=template_vmid,
            ram_gb=ram_gb,
            vcpu=vcpu,
            ssh_pub_key=ssh_pub_key,
            vlan_id=vlan_id,
        )

    def start_vm(self, node: str, vmid: int) -> None:
        self._service.client.start_vm(node, vmid)

    def stop_vm(self, node: str, vmid: int) -> None:
        self._service.client.stop_vm(node, vmid)

    def destroy_vm(self, vmid: int) -> None:
        self._service.destroy_vm(vmid)

    def get_vm_status(self, node: str, vmid: int) -> dict:
        return self._service.client.get_vm_status(node, vmid)

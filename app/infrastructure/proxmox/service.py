import logging

from app.application.ports.proxmox_gateway import ProvisionResult
from app.core.config import get_settings
from app.infrastructure.proxmox.proxmox_client import ProxmoxClient, ProxmoxIntegrationError

logger = logging.getLogger(__name__)


class VMService:
    def __init__(self, client: ProxmoxClient | None = None) -> None:
        self.client = client or ProxmoxClient()
        self.settings = get_settings()

    def provision_new_vm(
        self,
        name: str,
        template_vmid: int,
        ram_gb: float,
        vcpu: int,
        ssh_pub_key: str,
        vlan_id: int | None = None,
    ) -> ProvisionResult:
        node = self.settings.proxmox_default_node
        memory_mb = int(ram_gb * 1024)
        new_vmid = self.client.get_next_vmid()

        net0 = self.settings.proxmox_net0_template
        if vlan_id:
            net0 = f"{net0},tag={vlan_id}"

        logger.info("Provisioning VM %s (ID: %s) from template %s",
                    name, new_vmid, template_vmid)

        try:
            self.client.create_vm_from_template(
                node=node,
                template_vmid=template_vmid,
                new_vmid=new_vmid,
                name=name,
                memory_mb=memory_mb,
                cores=vcpu,
                net0=net0,
                ssh_key=ssh_pub_key,
            )
            self.client.start_vm(node, new_vmid)
            ip_address = self.client.get_vm_ip_address(node, new_vmid)
            return ProvisionResult(
                vmid=new_vmid, name=name, node=node, status="up", ip_address=ip_address,
            )
        except ProxmoxIntegrationError:
            logger.exception("Failed to provision VM %s", name)
            raise

    def destroy_vm(self, vmid: int) -> dict:
        node = self.settings.proxmox_default_node
        logger.info("Destroying VM %s", vmid)
        self.client.delete_vm(node, vmid)
        return {"status": "deleted", "vmid": vmid}

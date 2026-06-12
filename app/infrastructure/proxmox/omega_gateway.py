"""OmegaScriptGateway : implémentation du port ProxmoxGateway pilotant le cluster Omega.

Contrairement au client proxmoxer brut, ce gateway délègue aux scripts omega-remote-paging
DÉJÀ TESTÉS (source unique de vérité) : provisioning avec distribution 1 Emilia/2 Ram/2 Rem,
IP par VMID, firewall=0, CPU x86-64-v2-AES, QGA, isolation OVS VLAN 30. Le backend n'a donc
aucune logique cluster à dupliquer ni à maintenir.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from app.application.ports.proxmox_gateway import ProvisionResult
from app.core.config import get_settings
from app.infrastructure.proxmox.omega_runner import OmegaRunner
from app.infrastructure.proxmox.proxmox_client import ProxmoxIntegrationError

logger = logging.getLogger(__name__)

# Statut Proxmox → statut applicatif GANDAL (up/stopped/paused)
_STATUS_MAP = {"running": "up", "stopped": "stopped",
               "paused": "waiting", "suspended": "waiting"}


class OmegaScriptGateway:
    """Adapte les scripts omega-remote-paging au port ProxmoxGateway."""

    def __init__(self, runner: OmegaRunner | None = None) -> None:
        self.s = get_settings()
        self.runner = runner or OmegaRunner(self.s)
        self.scripts = Path(self.runner.scripts_dir)

    # ── Helpers cluster ──────────────────────────────────────────────────────
    def _cluster_vms(self) -> list[dict]:
        r = self.runner.run(["pvesh", "get", "/cluster/resources", "--type", "vm",
                             "--output-format", "json"])
        if not r.ok:
            raise ProxmoxIntegrationError(f"pvesh resources: {r.err.strip() or r.rc}")
        try:
            return json.loads(r.out or "[]")
        except json.JSONDecodeError as e:
            raise ProxmoxIntegrationError("réponse pvesh illisible") from e

    def _find(self, vmid: int) -> dict | None:
        for v in self._cluster_vms():
            if v.get("vmid") == vmid:
                return v
        return None

    def _alloc_vmid(self) -> int:
        base = int(self.runner.conf.get("OMEGA_NET_VM_VMID_BASE", "3000"))
        used = {v.get("vmid") for v in self._cluster_vms()}
        for cand in range(base, base + 1000):
            if cand not in used:
                return cand
        raise ProxmoxIntegrationError("aucun VMID libre dans la plage omega")

    def _node_of(self, vmid: int) -> str | None:
        cv = self._find(vmid)
        return cv.get("node") if cv else None

    def _vm_ip(self, vmid: int, node: str | None = None) -> str | None:
        # pvesh proxifie vers le nœud hôte → marche depuis n'importe quel nœud (pas qm local).
        node = node or self._node_of(vmid)
        if not node:
            return None
        r = self.runner.run(
            ["pvesh", "get", f"/nodes/{node}/qemu/{vmid}/agent/network-get-interfaces",
             "--output-format", "json"], timeout=10)
        if not r.ok:
            return None
        try:
            data = json.loads(r.out or "{}")
            ifaces = data.get("result", data) if isinstance(data, dict) else data
        except json.JSONDecodeError:
            return None
        for itf in ifaces or []:
            if itf.get("name") == "lo":
                continue
            for addr in itf.get("ip-addresses", []) or []:
                ip = addr.get("ip-address", "")
                if addr.get("ip-address-type") == "ipv4" and not ip.startswith("127."):
                    return ip
        return None

    # ── Port ProxmoxGateway ──────────────────────────────────────────────────
    def provision_new_vm(self, name: str, template_vmid: int, ram_gb: float,
                         vcpu: int, ssh_pub_key: str,
                         vlan_id: int | None = None) -> ProvisionResult:
        """Provisionne une VM via le script [p] (distribution 1/2/2 gérée par le script).

        vlan_id est ignoré : l'isolation VLAN 30 OMEGA est imposée par nos scripts
        (vm-isolation.sh) — pas de fuite vers d'autres VLAN académiques.
        """
        vmid = self._alloc_vmid()
        conf = self.runner.conf
        nodes = conf.get("OMEGA_NODES", "")
        disk_gib = int(conf.get("OMEGA_VM_DISK_MAX_GIB", "20"))
        argv = [
            "bash", str(self.scripts / "provision-omega-vms-remote.sh"),
            "--nodes", nodes,
            "--vmids", str(vmid),
            "--name", name or "omega-test",
            "--cores", str(max(1, vcpu)),
            "--memory", str(int(ram_gb * 1024)),
            "--disk-max-gib", str(disk_gib),
            "--resource-only",
        ]
        if conf.get("OMEGA_NET_VM_IP_PREFIX"):
            argv += [
                "--vm-ip-prefix", conf["OMEGA_NET_VM_IP_PREFIX"],
                "--vm-ip-start", conf.get("OMEGA_NET_VM_IP_START", "101"),
                "--vm-vmid-base", conf.get("OMEGA_NET_VM_VMID_BASE", "3000"),
                "--vm-gateway", conf.get("OMEGA_NET_VM_GATEWAY", ""),
                "--vm-netmask", conf.get("OMEGA_NET_VM_NETMASK", "24"),
                "--vm-ip-min", conf.get("OMEGA_NET_VM_IP_MIN", "2"),
                "--vm-ip-max", conf.get("OMEGA_NET_VM_IP_MAX", "253"),
            ]
        logger.info("Omega provision VM %s (vmid=%s) via [p]", name, vmid)
        r = self.runner.run(argv, timeout=900)
        if not r.ok:
            logger.error("Omega provision échec vmid=%s: %s", vmid, r.err[-500:])
            raise ProxmoxIntegrationError(
                f"provisioning vmid {vmid} échoué: {r.err.strip()[-300:] or r.rc}")
        cv = self._find(vmid)
        node = (cv or {}).get("node") or conf.get("OMEGA_CONTROLLER", "")
        status = _STATUS_MAP.get((cv or {}).get("status", "running"), "up")
        return ProvisionResult(vmid=vmid, name=name, node=node, status=status)

    def _status_action(self, node: str, vmid: int, action: str,
                       timeout: int | None = None) -> None:
        # pvesh proxifie vers le nœud hôte → start/stop/shutdown depuis n'importe où.
        node = node or self._node_of(vmid)
        if not node:
            raise ProxmoxIntegrationError(f"nœud de la VM {vmid} introuvable")
        r = self.runner.run(
            ["pvesh", "create", f"/nodes/{node}/qemu/{vmid}/status/{action}"],
            timeout=timeout)
        if not r.ok:
            raise ProxmoxIntegrationError(
                f"pvesh {action} {vmid}: {r.err.strip() or r.out.strip() or r.rc}")

    def start_vm(self, node: str, vmid: int) -> None:
        self._status_action(node, vmid, "start")

    def stop_vm(self, node: str, vmid: int) -> None:
        self._status_action(node, vmid, "shutdown", timeout=60)

    def destroy_vm(self, vmid: int) -> None:
        # Best-effort idempotent : DNS retiré, puis arrêt + destruction purge via pvesh.
        node = self._node_of(vmid)
        self.runner.run(["bash", str(self.scripts / "dns-register.sh"),
                        "--vmid", str(vmid), "--delete"], timeout=60)
        if not node:
            return  # déjà absente
        self.runner.run(["pvesh", "create", f"/nodes/{node}/qemu/{vmid}/status/stop"],
                        timeout=60)
        r = self.runner.run(
            ["pvesh", "delete", f"/nodes/{node}/qemu/{vmid}",
             "--purge", "1", "--destroy-unreferenced-disks", "1"], timeout=120)
        if not r.ok:
            raise ProxmoxIntegrationError(f"pvesh destroy {vmid}: {r.err.strip() or r.rc}")

    def get_vm_status(self, node: str, vmid: int) -> dict:
        cv = self._find(vmid)
        if cv is None:
            return {"status": "stopped", "exists": False}
        return {
            "status": _STATUS_MAP.get(cv.get("status", "stopped"), "stopped"),
            "exists": True,
            "node": cv.get("node"),
            "ip": self._vm_ip(vmid, cv.get("node")) if cv.get("status") == "running" else None,
        }

    # ═══════════════════════════════════════════════════════════════════════
    #  Capacités Omega étendues (au-delà du port générique ProxmoxGateway)
    #  Internet / Réseau / Distribution / Topologie — pilotent nos scripts.
    # ═══════════════════════════════════════════════════════════════════════
    def _assigned_ips(self) -> dict[int, str]:
        """Map vmid→IP lue depuis ipconfig0 des configs (vraie IP, allocation dense .2-.253).

        L'IP n'étant plus dérivée du VMID, on lit la valeur réelle. Une seule commande
        grep cluster-wide sur /etc/pve (monté partout).
        """
        r = self.runner.run_shell(
            "grep -rhoE '^[0-9]+|ipconfig0:.*ip=[0-9.]+/' /dev/null; "
            "for f in /etc/pve/nodes/*/qemu-server/*.conf; do "
            "vmid=$(basename \"$f\" .conf); "
            "ip=$(grep -oE '^ipconfig0:.*ip=[0-9.]+/' \"$f\" 2>/dev/null | grep -oE 'ip=[0-9.]+/' | head -1 | sed 's/ip=//;s#/##'); "
            "[ -n \"$ip\" ] && echo \"$vmid $ip\"; done", timeout=20)
        out: dict[int, str] = {}
        if r.ok:
            for line in r.out.splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[0].isdigit():
                    out[int(parts[0])] = parts[1]
        return out

    def set_internet(self, vmid: int, enable: bool) -> None:
        action = "enable" if enable else "disable"
        r = self.runner.run(["bash", str(self.scripts / "vm-internet.sh"),
                            "--vmid", str(vmid), f"--{action}"], timeout=90)
        if not r.ok:
            raise ProxmoxIntegrationError(
                f"vm-internet {action} {vmid}: {r.err.strip()[-200:] or r.rc}")

    def list_internet_ips(self) -> set[str]:
        """IPs des VMs ayant l'accès internet (parse vm-internet.sh --list)."""
        r = self.runner.run(["bash", str(self.scripts / "vm-internet.sh"), "--list"],
                            timeout=30)
        ips: set[str] = set()
        if r.ok:
            for tok in re.findall(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", r.out):
                ips.add(tok)
        return ips

    def link_vms(self, vmids: list[int], enable: bool, group_name: str | None = None) -> None:
        """Relie (maillage) ou isole un groupe de VMs via vm-link.sh."""
        action = "enable" if enable else "disable"
        argv = ["bash", str(self.scripts / "vm-link.sh"),
                "--group", ",".join(str(v) for v in vmids), f"--{action}"]
        if group_name:
            argv += ["--group-name", group_name]
        r = self.runner.run(argv, timeout=120)
        if not r.ok:
            raise ProxmoxIntegrationError(
                f"vm-link {action}: {r.err.strip()[-200:] or r.rc}")

    def distribution_status(self) -> list[dict]:
        """Occupation par nœud vs cible 1/2/2 (réconciliateur --dry-run, lecture seule)."""
        conf = self.runner.conf
        import shlex
        env = (f"OMEGA_VM_NODE_DISTRIBUTION={shlex.quote(conf.get('OMEGA_VM_NODE_DISTRIBUTION',''))} "
               f"OMEGA_VM_NODE_DEFAULT_MAX={shlex.quote(conf.get('OMEGA_VM_NODE_DEFAULT_MAX','2'))}")
        script = f"{env} bash {self.scripts / 'omega-distribution-reconciler.sh'} --dry-run"
        r = self.runner.run_shell(script, timeout=60)
        out = []
        m = re.search(r"occupation:\s*(.+)", r.out + r.err)
        if m:
            for node, cur, quota, target in re.findall(
                    r"(\S+)=(\d+)/(\d+)\(cible (\d+)\)", m.group(1)):
                out.append({"node": node, "current": int(cur),
                            "quota": int(quota), "target": int(target)})
        return out

    def reconcile_now(self) -> bool:
        r = self.runner.run(["systemctl", "start",
                            "omega-distribution-reconciler.service"], timeout=300)
        return r.ok

    # ── GPU (nvidia-smi par nœud) ────────────────────────────────────────────
    def gpu_status(self) -> list[dict]:
        """État GPU de chaque nœud du cluster (nom, VRAM, utilisation, température)."""
        nodes_csv = self.runner.conf.get("OMEGA_NODES", "")
        nodes = [n.strip() for n in nodes_csv.split(",") if n.strip()]
        ip2name = self._ip_to_name()
        out: list[dict] = []
        query = ("name,memory.used,memory.total,utilization.gpu,temperature.gpu")
        for node_ip in nodes:
            # ssh depuis l'hôte du runner vers chaque nœud (clés root du cluster PVE).
            cmd = (f"ssh -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=6 "
                   f"root@{node_ip} 'nvidia-smi --query-gpu={query} "
                   f"--format=csv,noheader,nounits' 2>/dev/null")
            r = self.runner.run_shell(cmd, timeout=20)
            name = ip2name.get(node_ip, node_ip)
            if not r.ok or not r.out.strip():
                out.append({"node": name, "available": False})
                continue
            for line in r.out.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 5:
                    continue
                try:
                    out.append({
                        "node": name, "available": True, "gpu": parts[0],
                        "mem_used_mib": int(float(parts[1])),
                        "mem_total_mib": int(float(parts[2])),
                        "util_pct": int(float(parts[3])),
                        "temp_c": int(float(parts[4])),
                    })
                except ValueError:
                    out.append({"node": name, "available": False})
        return out

    def _ip_to_name(self) -> dict[str, str]:
        r = self.runner.run(["pvesh", "get", "/cluster/status",
                            "--output-format", "json"])
        mapping: dict[str, str] = {}
        if r.ok:
            try:
                for e in json.loads(r.out or "[]"):
                    if e.get("type") == "node" and e.get("ip") and e.get("name"):
                        mapping[e["ip"]] = e["name"]
            except json.JSONDecodeError:
                pass
        return mapping

    # ── Reconfiguration des caractéristiques VM ──────────────────────────────
    def _vm_config(self, node: str, vmid: int) -> dict:
        r = self.runner.run(["pvesh", "get", f"/nodes/{node}/qemu/{vmid}/config",
                            "--output-format", "json"])
        if not r.ok:
            raise ProxmoxIntegrationError(f"lecture config {vmid}: {r.err.strip() or r.rc}")
        try:
            return json.loads(r.out or "{}")
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _parse_omega_desc(desc: str) -> dict:
        out = {}
        for m in re.finditer(r"(omega_[a-z_]+)=(\d+)", desc or ""):
            out[m.group(1)] = int(m.group(2))
        return out

    @staticmethod
    def _build_omega_desc(d: dict) -> str:
        order = ["omega_min_vcpus", "omega_max_vcpus", "omega_memory_min_mib",
                 "omega_memory_max_mib", "omega_disk_max_gib", "omega_gpu_vram_mib"]
        return " ".join(f"{k}={int(d.get(k, 0))}" for k in order)

    def reconfigure_vm(self, vmid: int, name: str | None = None,
                       vcpu_max: int | None = None, ram_mib: int | None = None,
                       disk_gib: int | None = None, vram_mib: int | None = None) -> dict:
        """Modifie à chaud les caractéristiques d'une VM omega (vCPU max, RAM, disque, VRAM, nom).

        - vCPU max = cores (le plancher reste 1, élasticité préservée) ;
        - RAM = memory ; balloon (min) ramené si supérieur ;
        - disque : agrandissement uniquement (resize +N G) — jamais de réduction ;
        - VRAM : met à jour omega_gpu_vram_mib + tag omega-gpu ;
        Réécrit la description omega_* lue par le watchdog/daemon.
        """
        node = self._node_of(vmid)
        if not node:
            raise ProxmoxIntegrationError(f"VM {vmid} introuvable")
        cfg = self._vm_config(node, vmid)
        omega = self._parse_omega_desc(cfg.get("description", ""))
        cur_cores = int(cfg.get("cores", omega.get("omega_max_vcpus", 4)) or 4)
        cur_mem = int(cfg.get("memory", omega.get("omega_memory_max_mib", 6144)) or 6144)

        set_args: list[str] = []
        if name:
            set_args += ["--name", name]
        if vcpu_max is not None and vcpu_max >= 2:
            set_args += ["--cores", str(vcpu_max)]
            omega["omega_max_vcpus"] = vcpu_max
            omega.setdefault("omega_min_vcpus", 1)
        if ram_mib is not None and ram_mib >= 512:
            set_args += ["--memory", str(ram_mib)]
            omega["omega_memory_max_mib"] = ram_mib
            # balloon (min) ≤ memory
            balloon = int(cfg.get("balloon", omega.get("omega_memory_min_mib", 512)) or 512)
            if balloon >= ram_mib:
                balloon = max(512, ram_mib // 4)
                set_args += ["--balloon", str(balloon)]
            omega["omega_memory_min_mib"] = balloon
        if vram_mib is not None:
            omega["omega_gpu_vram_mib"] = vram_mib
        if disk_gib is not None:
            omega["omega_disk_max_gib"] = disk_gib

        # Description + tags (omega-gpu si VRAM>0)
        set_args += ["--description", self._build_omega_desc(omega)]
        tags = self._merge_tags(cfg.get("tags", ""), gpu=omega.get("omega_gpu_vram_mib", 0) > 0)
        set_args += ["--tags", tags]

        r = self.runner.run(["pvesh", "set", f"/nodes/{node}/qemu/{vmid}/config", *set_args],
                            timeout=60)
        if not r.ok:
            raise ProxmoxIntegrationError(f"reconfigure {vmid}: {r.err.strip()[-200:] or r.rc}")

        # Agrandissement disque (jamais de réduction).
        if disk_gib is not None:
            self._grow_disk(node, vmid, cfg, disk_gib)
        return {"vmid": vmid, "applied": True}

    @staticmethod
    def _merge_tags(tags: str, gpu: bool) -> str:
        parts = [t for t in re.split(r"[;, ]+", tags or "") if t]
        if "omega" not in parts:
            parts.append("omega")
        if gpu and "omega-gpu" not in parts:
            parts.append("omega-gpu")
        if not gpu and "omega-gpu" in parts:
            parts.remove("omega-gpu")
        return ";".join(parts)

    def _grow_disk(self, node: str, vmid: int, cfg: dict, target_gib: int) -> None:
        # Trouve le disque principal (scsi0/virtio0) et sa taille actuelle.
        for key in ("scsi0", "virtio0"):
            val = cfg.get(key)
            if not val:
                continue
            m = re.search(r"size=(\d+)([GMT])", val)
            cur = 0
            if m:
                unit = m.group(2)
                cur = int(m.group(1)) * (1024 if unit == "T" else 1 if unit == "G" else 0)
            if target_gib > cur > 0:
                self.runner.run(
                    ["pvesh", "set", f"/nodes/{node}/qemu/{vmid}/resize",
                     "--disk", key, "--size", f"+{target_gib - cur}G"], timeout=60)
            return

    def set_gpu(self, vmid: int, vram_mib: int) -> dict:
        """Alloue (vram>0) ou retire (0) du GPU à une VM (partage via proxy, pas passthrough)."""
        return self.reconfigure_vm(vmid, vram_mib=vram_mib)

    def set_autostart(self, vmid: int, enable: bool) -> dict:
        """Always-on : onboot=1 (démarre au boot du nœud)."""
        node = self._node_of(vmid)
        if not node:
            raise ProxmoxIntegrationError(f"VM {vmid} introuvable")
        r = self.runner.run(["pvesh", "set", f"/nodes/{node}/qemu/{vmid}/config",
                            "--onboot", "1" if enable else "0"], timeout=30)
        if not r.ok:
            raise ProxmoxIntegrationError(f"autostart {vmid}: {r.err.strip() or r.rc}")
        return {"vmid": vmid, "autostart": enable}

    # ── DNS (dns-register.sh) ────────────────────────────────────────────────
    def dns_register(self, vmid: int, hostname: str | None = None) -> dict:
        argv = ["bash", str(self.scripts / "dns-register.sh"), "--vmid", str(vmid)]
        if hostname:
            argv += ["--name", hostname]
        r = self.runner.run(argv, timeout=60)
        if not r.ok:
            raise ProxmoxIntegrationError(f"dns register {vmid}: {r.err.strip()[-200:] or r.rc}")
        return {"vmid": vmid, "hostname": hostname}

    # ── Migrations (tâches cluster Proxmox) ──────────────────────────────────
    def migrations(self, limit: int = 25) -> list[dict]:
        """Historique récent des migrations de VMs (tâches qmigrate du cluster)."""
        r = self.runner.run(["pvesh", "get", "/cluster/tasks",
                            "--output-format", "json"])
        if not r.ok:
            return []
        try:
            tasks = json.loads(r.out or "[]")
        except json.JSONDecodeError:
            return []
        out = []
        for t in tasks:
            if t.get("type") not in ("qmigrate",):
                continue
            out.append({
                "vmid": t.get("id"),
                "node_from": t.get("node"),
                "status": t.get("status", "running"),
                "starttime": t.get("starttime"),
                "endtime": t.get("endtime"),
                "user": t.get("user"),
            })
            if len(out) >= limit:
                break
        return out

    def topology(self) -> dict:
        """Vue agrégée pour l'UI : nœuds-hôtes, VMs omega (avec internet), prête à grapher."""
        vms = [v for v in self._cluster_vms() if _is_omega(v)]
        internet_ips = self.list_internet_ips()
        ip_map = self._assigned_ips()
        nodes_set = sorted({v.get("node") for v in vms if v.get("node")})
        out_vms = []
        for v in vms:
            vmid = v.get("vmid")
            ip = ip_map.get(vmid)
            out_vms.append({
                "vmid": vmid,
                "name": v.get("name"),
                "node": v.get("node"),
                "status": _STATUS_MAP.get(v.get("status", "stopped"), "stopped"),
                "ip": ip,
                "internet": ip in internet_ips,
                "maxcpu": v.get("maxcpu"),
                "maxmem": v.get("maxmem"),
            })
        return {"hosts": nodes_set, "vms": out_vms}


_OMEGA_TAG = re.compile(r"(^|[;, ])omega([;, ]|$)")
_TEMPLATE_TAG = re.compile(r"(^|[;, ])template([;, ]|$)")


def _is_omega(cv: dict) -> bool:
    """VM de flotte omega : taguée 'omega', ni template PVE, ni taguée 'template'."""
    if cv.get("template"):
        return False
    tags = cv.get("tags") or ""
    if _TEMPLATE_TAG.search(tags):
        return False
    return bool(_OMEGA_TAG.search(tags))

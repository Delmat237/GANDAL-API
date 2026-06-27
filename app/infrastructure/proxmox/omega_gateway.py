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

    def reserve_vmid(self, exclude: set[int] | None = None) -> int:
        """Alloue le prochain VMID libre (cluster + exclusions DB) — à réserver côté
        appelant AVANT le provisionnement pour éviter les collisions concurrentes."""
        base = int(self.runner.conf.get("OMEGA_NET_VM_VMID_BASE", "3000"))
        used = {v.get("vmid") for v in self._cluster_vms()} | (exclude or set())
        for cand in range(base, base + 1000):
            if cand not in used:
                return cand
        raise ProxmoxIntegrationError("aucun VMID libre dans la plage omega")

    # ── Port ProxmoxGateway ──────────────────────────────────────────────────
    def provision_new_vm(self, name: str, template_vmid: int, ram_gb: float,
                         vcpu: int, ssh_pub_key: str,
                         vlan_id: int | None = None,
                         vmid: int | None = None) -> ProvisionResult:
        """Provisionne une VM via le script [p] (distribution 1/2/2 gérée par le script).

        vlan_id est ignoré : l'isolation VLAN 30 OMEGA est imposée par nos scripts
        (vm-isolation.sh) — pas de fuite vers d'autres VLAN académiques.
        vmid : si fourni, utilise ce VMID (réservé par l'appelant) au lieu d'en allouer un.
        """
        if vmid is None:
            vmid = self._alloc_vmid()
        conf = self.runner.conf
        nodes = conf.get("OMEGA_NODES", "")
        controller = conf.get("OMEGA_CONTROLLER", "") or nodes.split(",")[0]
        disk_gib = int(conf.get("OMEGA_VM_DISK_MAX_GIB", "20"))
        storage = conf.get("OMEGA_VM_STORAGE", "stockage.ceph")
        template_id = conf.get("OMEGA_VM_TEMPLATE_ID", "")
        # Bridge OMEGA (vmbr1 OVS) — IMPÉRATIF : le défaut vmbr0 du script de création
        # n'existe pas sur le cluster → la VM ne peut pas démarrer (boucle recreate).
        bridge = conf.get("OMEGA_VM_BRIDGE") or conf.get("OMEGA_NET_VM_BRIDGE") or "vmbr1"
        argv = [
            "bash", str(self.scripts / "provision-omega-vms-remote.sh"),
            "--controller", controller,
            "--nodes", nodes,
            "--storage", storage,
            "--bridge", bridge,
            "--vmids", str(vmid),
            "--name", name or "omega-test",
            "--cores", str(max(1, vcpu)),
            "--memory", str(int(ram_gb * 1024)),
            "--disk-max-gib", str(disk_gib),
            "--resource-only",
        ]
        # Template de clonage (9001) + flags du chemin omega validé ([p]).
        if template_id:
            argv += ["--template-id", str(template_id)]
            if conf.get("OMEGA_VM_LINKED_CLONE", "1") == "1":
                argv.append("--linked-clone")
        if conf.get("OMEGA_VM_IMAGE_PREPARED", "1") == "1":
            argv.append("--image-prepared")
        if conf.get("OMEGA_NET_VM_VLAN_TAG"):
            argv += ["--vm-vlan-tag", conf["OMEGA_NET_VM_VLAN_TAG"]]
        if conf.get("OMEGA_NET_VM_DNS_IP"):
            argv += ["--vm-dns-ip", conf["OMEGA_NET_VM_DNS_IP"]]
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

    def _vm_specs(self) -> dict[int, dict]:
        """Map vmid→{cores, mem_mib, vram_mib} depuis les CONFIGS (valable VM arrêtée,
        contrairement à pvesh /cluster/resources qui renvoie 0 pour une VM stoppée)."""
        script = (
            "for f in /etc/pve/nodes/*/qemu-server/*.conf; do "
            "vmid=$(basename \"$f\" .conf); "
            "cores=$(grep -oE '^cores: [0-9]+' \"$f\" | grep -oE '[0-9]+'); "
            "mem=$(grep -oE '^memory: [0-9]+' \"$f\" | grep -oE '[0-9]+'); "
            "vram=$(grep -oE 'omega_gpu_vram_mib=[0-9]+' \"$f\" | grep -oE '[0-9]+$' | head -1); "
            "echo \"$vmid ${cores:-0} ${mem:-0} ${vram:-0}\"; done")
        r = self.runner.run_shell(script, timeout=20)
        out: dict[int, dict] = {}
        if r.ok:
            for line in r.out.splitlines():
                p = line.split()
                if len(p) == 4 and p[0].isdigit():
                    out[int(p[0])] = {"cores": int(p[1]), "mem_mib": int(p[2]),
                                      "vram_mib": int(p[3])}
        return out

    def _pf_script(self, name: str) -> str:
        """Chemin LOCAL d'un script pfSense (exécuté sur l'hôte qui joint pfSense)."""
        from pathlib import Path as _P
        return str(_P(self.s.omega_local_scripts) / name)

    def _run_pf(self, argv: list[str], timeout: int = 90):
        """Exécute un script pfSense en local si configuré, sinon via le runner normal."""
        if self.s.omega_pfsense_local:
            return self.runner.run_local(argv, timeout=timeout)
        return self.runner.run(argv, timeout=timeout)

    def set_internet(self, vmid: int, enable: bool) -> None:
        action = "enable" if enable else "disable"
        # On passe la VRAIE IP (allocation dense → plus dérivable du VMID).
        ip = self._assigned_ips().get(vmid)
        sel = ["--ip", ip] if ip else ["--vmid", str(vmid)]
        r = self._run_pf(["bash", self._pf_script("vm-internet.sh"),
                         *sel, f"--{action}"], timeout=90)
        if not r.ok:
            raise ProxmoxIntegrationError(
                f"vm-internet {action} {vmid}: {r.err.strip()[-200:] or r.rc}")

    def set_llm_access(self, vmid: int, enable: bool) -> None:
        """Ouvre/ferme l'accès ÉTROIT d'une VM à la gateway LLM (gateway_ip:port),
        via llm-access.sh sur pfSense. La VM reste isolée du reste du LAN."""
        action = "enable" if enable else "disable"
        ip = self._assigned_ips().get(vmid)
        sel = ["--ip", ip] if ip else ["--vmid", str(vmid)]
        r = self._run_pf(["bash", self._pf_script("llm-access.sh"), *sel,
                          f"--{action}", "--gateway", self.s.omega_llm_gateway_ip,
                          "--gw-port", str(self.s.omega_llm_gateway_port)], timeout=90)
        if not r.ok:
            raise ProxmoxIntegrationError(
                f"llm-access {action} {vmid}: {r.err.strip()[-200:] or r.rc}")

    def reconcile_llm_access(self, threshold: int = 0, prune: bool = False) -> dict:
        """Garantit que toute VM Omega DÉMARRÉE avec omega_gpu_vram_mib > threshold
        a l'accès à la gateway LLM. Avec prune, retire l'accès des non-conformes.
        Idempotent (llm-access.sh vérifie l'existant)."""
        specs = self._vm_specs()
        running = {v.get("vmid") for v in self._cluster_vms()
                   if v.get("status") == "running"}
        granted: list[int] = []
        revoked: list[int] = []
        skipped: list[int] = []
        for vmid, spec in specs.items():
            vram = spec.get("vram_mib", 0)
            is_run = vmid in running
            if vram > threshold:
                if not is_run:
                    skipped.append(vmid)
                    continue
                self.set_llm_access(vmid, True)
                granted.append(vmid)
            elif prune and is_run:
                self.set_llm_access(vmid, False)
                revoked.append(vmid)
        return {"granted": granted, "revoked": revoked, "skipped": skipped}

    def list_internet_ips(self) -> set[str]:
        """IPs des VMs ayant l'accès internet — lues DIRECTEMENT depuis les règles pfSense
        chargées (pfctl), via les labels `omega-internet-A-B-C-D`. Fiable (contrairement au
        --list PHP de vm-internet.sh, fragile à travers plusieurs couches SSH)."""
        conf = self.runner.conf
        pf_ip = conf.get("OMEGA_NET_PFSENSE_WAN_IP", "192.168.123.200")
        pf_user = conf.get("OMEGA_NET_PFSENSE_SSH_USER", "admin")
        pf_key = conf.get("SSH_KEY", "")
        ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
                   "-o", "ConnectTimeout=8"]
        if pf_key:
            ssh_cmd += ["-i", pf_key]
        ssh_cmd += [f"{pf_user}@{pf_ip}", "pfctl -sr 2>/dev/null"]
        r = self._run_pf(ssh_cmd, timeout=20)
        ips: set[str] = set()
        if r.ok:
            # label "omega-internet-10-50-30-101" → 10.50.30.101
            for m in re.findall(r"omega-internet-(\d+)-(\d+)-(\d+)-(\d+)", r.out):
                ips.add(".".join(m))
        return ips

    def link_vms(self, vmids: list[int], enable: bool, group_name: str | None = None) -> None:
        """Relie ou isole des VMs via vm-link.sh (flux OVS sur les nœuds).

        vm-link orchestre l'OVS sur TOUS les nœuds → s'exécute sur le contrôleur (qui
        les joint), via le runner normal — PAS en local (la console ne joint pas ram/rem).
        On passe `--nodes` explicite + les VRAIES IP (allocation dense, paires).
        """
        action = "enable" if enable else "disable"
        nodes = self.runner.conf.get("OMEGA_NODES", "")
        ips = self._assigned_ips()
        scripts = str(self.scripts / "vm-link.sh")  # chemin sur le contrôleur (emilia)
        # Maillage complet : toutes les paires du groupe, par IP réelle.
        pairs = [(a, b) for i, a in enumerate(vmids) for b in vmids[i + 1:]]
        for a, b in pairs:
            ip_a, ip_b = ips.get(a), ips.get(b)
            if not ip_a or not ip_b:
                raise ProxmoxIntegrationError(
                    f"IP introuvable pour la paire {a}/{b} (VM démarrée ?)")
            argv = ["bash", scripts, "--nodes", nodes,
                    "--ip-a", ip_a, "--ip-b", ip_b, f"--{action}"]
            r = self.runner.run(argv, timeout=120)
            if not r.ok:
                raise ProxmoxIntegrationError(
                    f"vm-link {action} {a}/{b}: {r.err.strip()[-200:] or r.rc}")

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

    # ── Exposition de service (vm-expose.sh — port-forward pfSense) ──────────
    def expose_service(self, vmid: int, service_port: int, ext_port: int | None = None,
                       hostname: str | None = None, proto: str = "tcp",
                       enable: bool = True) -> dict:
        """Publie/retire un service de la VM vers le LAN via NAT pfSense.

        LAN(192.168.123.200):ext_port → VM_IP:service_port, + DNS nom→pfSense optionnel.
        """
        ip = self._assigned_ips().get(vmid)
        if not ip:
            raise ProxmoxIntegrationError(f"VM {vmid} : IP introuvable")
        ext = ext_port or service_port
        argv = ["bash", self._pf_script("vm-expose.sh"), "--ip", ip,
                "--service-port", str(service_port), "--ext-port", str(ext),
                "--proto", proto]
        if enable and hostname:
            argv += ["--name", hostname]
        argv.append("--enable" if enable else "--disable")
        r = self._run_pf(argv, timeout=90)
        if not r.ok:
            raise ProxmoxIntegrationError(
                f"expose {vmid}: {r.err.strip()[-200:] or r.rc}")
        pf_ip = self.runner.conf.get("OMEGA_NET_PFSENSE_WAN_IP", "192.168.123.200")
        return {"vmid": vmid, "ip": ip, "service_port": service_port,
                "ext_port": ext, "enable": enable, "pfsense": pf_ip,
                "hostname": hostname, "url": f"http://{pf_ip}:{ext}" if enable else None}

    # ── Domaine SANS port (reverse proxy Caddy sur la console) ───────────────
    def add_domain(self, vmid: int, hostname: str, port: int,
                   enable: bool = True) -> dict:
        """Publie un service VM sous un nom de domaine SANS port (http://nom...).

        1) relie le proxy (console) à la VM backend (lien réseau, sur le contrôleur) ;
        2) ajoute/retire le site Caddy + DNS (sur la console qui joint pfSense).
        """
        ip = self._assigned_ips().get(vmid)
        if not ip:
            raise ProxmoxIntegrationError(f"VM {vmid} : IP introuvable")
        proxy_ip = self.s.omega_proxy_host_ip
        if enable:
            # 1) ouvrir le chemin proxy→backend (vm-link sur le contrôleur)
            nodes = self.runner.conf.get("OMEGA_NODES", "")
            lk = self.runner.run(["bash", str(self.scripts / "vm-link.sh"),
                                  "--nodes", nodes, "--ip-a", proxy_ip, "--ip-b", ip,
                                  "--enable"], timeout=120)
            if not lk.ok:
                raise ProxmoxIntegrationError(
                    f"lien proxy↔VM {vmid}: {lk.err.strip()[-150:] or lk.rc}")
            # 2) site Caddy + DNS (sur la console)
            r = self._run_pf(["bash", self._pf_script("proxy-domain.sh"),
                             "--name", hostname, "--ip", ip, "--port", str(port),
                             "--enable"], timeout=60)
        else:
            r = self._run_pf(["bash", self._pf_script("proxy-domain.sh"),
                             "--name", hostname, "--disable"], timeout=60)
        if not r.ok:
            raise ProxmoxIntegrationError(
                f"domaine {hostname}: {r.err.strip()[-200:] or r.rc}")
        suffix = self.runner.conf.get("OMEGA_NET_DNS_DOMAIN", "enspy-gi.gandal")
        url = f"http://{hostname.lower()}.{suffix}" if enable else None
        return {"vmid": vmid, "hostname": hostname, "port": port,
                "enable": enable, "url": url}

    # ── DNS (dns-register.sh) ────────────────────────────────────────────────
    def dns_register(self, vmid: int, hostname: str | None = None) -> dict:
        # On passe --name ET --ip explicitement : dns-register tourne en LOCAL sur la
        # console (qui joint pfSense) et NE PEUT PAS lire les configs des nœuds pour
        # résoudre le nom par --vmid → on lui fournit tout (pas de recherche nœud).
        ip = self._assigned_ips().get(vmid)
        if not ip:
            raise ProxmoxIntegrationError(f"VM {vmid} : IP introuvable (VM provisionnée ?)")
        name = hostname
        if not name:
            cv = self._find(vmid)
            name = (cv.get("name") if cv else None) or f"omega-{vmid}"
        r = self._run_pf(["bash", self._pf_script("dns-register.sh"),
                         "--name", name, "--ip", ip], timeout=60)
        if not r.ok:
            raise ProxmoxIntegrationError(f"dns register {vmid}: {r.err.strip()[-200:] or r.rc}")
        return {"vmid": vmid, "hostname": name, "ip": ip}

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
        specs = self._vm_specs()  # cores/mem/vram fiables (même VM arrêtée)
        nodes_set = sorted({v.get("node") for v in vms if v.get("node")})
        out_vms = []
        for v in vms:
            vmid = v.get("vmid")
            ip = ip_map.get(vmid)
            sp = specs.get(vmid, {})
            # maxcpu/maxmem de pvesh = 0 si VM arrêtée → on retombe sur la config.
            cpu = v.get("maxcpu") or sp.get("cores") or None
            mem_mib = sp.get("mem_mib") or (
                int(v.get("maxmem", 0) / 1024 / 1024) if v.get("maxmem") else 0)
            out_vms.append({
                "vmid": vmid,
                "name": v.get("name"),
                "node": v.get("node"),
                "status": _STATUS_MAP.get(v.get("status", "stopped"), "stopped"),
                "ip": ip,
                "internet": ip in internet_ips,
                "maxcpu": cpu,
                "maxmem": mem_mib * 1024 * 1024 if mem_mib else None,
                "vram_mib": sp.get("vram_mib", 0),
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

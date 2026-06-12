"""Exécution de commandes sur le cluster Proxmox pour le backend Omega.

Deux modes auto-détectés :
- LOCAL : le backend tourne SUR un nœud PVE (pvesh présent) → subprocess direct.
- SSH   : développement hors cluster → SSH vers le contrôleur avec la clé omega.

Le gateway appelle `run([...])` sans se soucier du transport. Les valeurs de connexion
(contrôleur, clé, distribution réseau…) proviennent de la config GANDAL-API ET, à défaut,
du cluster.conf d'omega-remote-paging (source de vérité du cluster).
"""
from __future__ import annotations

import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings, get_settings


@dataclass
class CmdResult:
    rc: int
    out: str
    err: str

    @property
    def ok(self) -> bool:
        return self.rc == 0


def parse_cluster_conf(path: str) -> dict[str, str]:
    """Mini-parseur des affectations VAR="val" de cluster.conf."""
    conf: dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return conf
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.split("#", 1)[0].strip().strip('"').strip("'")
        if key.isidentifier():
            conf[key] = val
    return conf


class OmegaRunner:
    def __init__(self, settings: Settings | None = None):
        self.s = settings or get_settings()
        self.scripts_dir = str(Path(self.s.omega_repo_root) / "scripts")
        conf_path = self.s.omega_cluster_conf or str(
            Path(self.s.omega_repo_root) / "scripts" / "cluster.conf")
        self.conf = parse_cluster_conf(conf_path)
        self.mode = self._resolve_mode()

    def _resolve_mode(self) -> str:
        if self.s.omega_exec_mode in ("local", "ssh"):
            return self.s.omega_exec_mode
        return "local" if shutil.which("pvesh") else "ssh"

    @property
    def controller(self) -> str:
        return self.s.omega_controller_host or self.conf.get("OMEGA_CONTROLLER", "")

    @property
    def ssh_key(self) -> str:
        return self.s.omega_ssh_key or self.conf.get("SSH_KEY", "")

    def _ssh_prefix(self) -> list[str]:
        cmd = ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "BatchMode=yes",
               "-o", "ConnectTimeout=8"]
        if self.ssh_key:
            cmd += ["-i", self.ssh_key]
        cmd.append(f"{self.s.omega_ssh_user}@{self.controller}")
        return cmd

    def run(self, argv: list[str], timeout: int | None = None,
            input_text: str | None = None) -> CmdResult:
        timeout = timeout or self.s.omega_cmd_timeout_secs
        if self.mode == "ssh":
            if not self.controller:
                return CmdResult(127, "", "OMEGA_CONTROLLER non défini (mode ssh)")
            remote = " ".join(shlex.quote(a) for a in argv)
            full = self._ssh_prefix() + [remote]
        else:
            full = argv
        try:
            proc = subprocess.run(full, capture_output=True, text=True,
                                  timeout=timeout, input=input_text)
            return CmdResult(proc.returncode, proc.stdout, proc.stderr)
        except subprocess.TimeoutExpired:
            return CmdResult(124, "", f"timeout après {timeout}s")
        except FileNotFoundError as e:
            return CmdResult(127, "", str(e))

    def run_shell(self, script: str, timeout: int | None = None) -> CmdResult:
        return self.run(["bash", "-c", script], timeout=timeout)

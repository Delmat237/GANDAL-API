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
import time
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

    @staticmethod
    def _is_connect_failure(res: CmdResult) -> bool:
        """SSH n'a JAMAIS établi la session → la commande distante n'a PAS tourné, donc
        retenter est SÛR (même pour une opération mutante). On exige rc 255 (échec ssh) ET
        un message de phase de connexion. On EXCLUT volontairement :
        - rc 124 (notre TimeoutExpired) : le process distant a pu démarrer et continue de
          tourner côté contrôleur même si le client SSH abandonne → un retry le DOUBLERAIT
          (cf. provisioning concurrent sur le même VMID) ;
        - 'broken pipe'/'reset by peer' : la session était établie, la commande a pu agir."""
        if res.rc != 255:
            return False
        e = (res.err or "").lower()
        established = "broken pipe" in e or "reset by peer" in e
        return (not established) and (
            "connect to host" in e or "connection timed out" in e
            or "connection refused" in e or "no route to host" in e
            or "banner exchange" in e or "operation timed out" in e
            # SSH coupé pendant l'établissement (échange de clés) → rien n'a tourné à distance
            or "kex_exchange_identification" in e or "connection closed by remote host" in e)

    def run(self, argv: list[str], timeout: int | None = None,
            input_text: str | None = None, retry: bool = False) -> CmdResult:
        """retry=True : ré-essaie SI ET SEULEMENT SI la connexion SSH a échoué avant
        d'exécuter quoi que ce soit (sûr car rien n'a tourné côté distant). À RÉSERVER aux
        lectures idempotentes (topologie/specs). JAMAIS sur une opération mutante longue
        (provisioning, destroy…) : un drop réseau en cours d'exécution la dupliquerait."""
        timeout = timeout or self.s.omega_cmd_timeout_secs
        if self.mode == "ssh":
            if not self.controller:
                return CmdResult(127, "", "OMEGA_CONTROLLER non défini (mode ssh)")
            remote = " ".join(shlex.quote(a) for a in argv)
            full = self._ssh_prefix() + [remote]
        else:
            full = argv

        attempts = (self.s.omega_ssh_retries if (retry and self.mode == "ssh") else 0) + 1
        res = CmdResult(127, "", "non exécuté")
        for i in range(attempts):
            try:
                proc = subprocess.run(full, capture_output=True, text=True,
                                      timeout=timeout, input=input_text)
                res = CmdResult(proc.returncode, proc.stdout, proc.stderr)
            except subprocess.TimeoutExpired:
                res = CmdResult(124, "", f"timeout après {timeout}s")
            except FileNotFoundError as e:
                return CmdResult(127, "", str(e))
            if res.ok or not self._is_connect_failure(res) or i == attempts - 1:
                return res
            time.sleep(self.s.omega_ssh_retry_backoff_secs * (i + 1))
        return res

    def run_shell(self, script: str, timeout: int | None = None,
                  retry: bool = False) -> CmdResult:
        return self.run(["bash", "-c", script], timeout=timeout, retry=retry)

    def run_local(self, argv: list[str], timeout: int | None = None) -> CmdResult:
        """Exécute TOUJOURS en local (subprocess), quel que soit le mode.

        Sert aux scripts qui touchent pfSense : ils doivent tourner sur un hôte qui
        joint pfSense (la console VM), pas sur le contrôleur PVE (emilia ne joint pas
        pfSense:22). Suppose donc que le backend tourne sur un hôte du VLAN omega.
        """
        timeout = timeout or self.s.omega_cmd_timeout_secs
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
            return CmdResult(proc.returncode, proc.stdout, proc.stderr)
        except subprocess.TimeoutExpired:
            return CmdResult(124, "", f"timeout après {timeout}s")
        except FileNotFoundError as e:
            return CmdResult(127, "", str(e))

"""Registre en mémoire des provisionings EN COURS (thread-safe).

Partagé entre l'approbation (`_provision_async`) et le réconciliateur d'auto-guérison :
le réconciliateur ne re-provisionne JAMAIS une VM déjà en cours de provisioning → pas de
doublon. Au redémarrage de l'API, le registre est vide ET les threads de provisioning sont
morts → toute VM restée `waiting` est légitimement reprise par le réconciliateur.
"""
from __future__ import annotations

import threading

_lock = threading.Lock()
_in_progress: set[int] = set()


def mark(vm_id: int) -> None:
    with _lock:
        _in_progress.add(vm_id)


def unmark(vm_id: int) -> None:
    with _lock:
        _in_progress.discard(vm_id)


def is_in_progress(vm_id: int) -> bool:
    with _lock:
        return vm_id in _in_progress


def snapshot() -> set[int]:
    with _lock:
        return set(_in_progress)

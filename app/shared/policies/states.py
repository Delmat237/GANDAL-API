from app.shared.models import VM, Requete


class StateTransitionError(Exception):
    """Exception levée lorsqu'une transition d'état est invalide."""
    pass


class VMStatePolicy:
    # Définition des états constants
    UP = "up"
    WAITING = "waiting"
    STOPPED = "stopped"

    @classmethod
    def can_start(cls, vm: VM) -> bool:
        """Une VM peut être démarrée ou redémarrée si elle est en pause ou arrêtée."""
        return vm.status in [cls.WAITING, cls.STOPPED]

    @classmethod
    def can_stop(cls, vm: VM) -> bool:
        """Une VM peut être arrêtée si elle est en cours d'exécution ou en pause."""
        return vm.status in [cls.UP, cls.WAITING]

    @classmethod
    def can_pause(cls, vm: VM) -> bool:
        """Une VM ne peut être mise en pause que si elle est en cours d'exécution."""
        return vm.status == cls.UP

    @classmethod
    def validate_transition(cls, vm: VM, target_status: str):
        """Valide et applique virtuellement la transition avant de toucher à Proxmox."""
        if target_status == cls.UP and not cls.can_start(vm):
            raise StateTransitionError(
                f"Impossible de démarrer la VM. État actuel: {vm.status}")

        if target_status == cls.STOPPED and not cls.can_stop(vm):
            raise StateTransitionError(
                f"Impossible d'arrêter la VM. État actuel: {vm.status}")

        if target_status == cls.WAITING and not cls.can_pause(vm):
            raise StateTransitionError(
                f"Impossible de mettre la VM en pause. État actuel: {vm.status}")


class RequestStatePolicy:
    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"

    @classmethod
    def can_be_evaluated(cls, requete: Requete) -> bool:
        """Une requête ne peut être validée ou rejetée que si elle est en attente."""
        return requete.status == cls.PENDING

    @classmethod
    def validate_approval(cls, requete: Requete):
        if not cls.can_be_evaluated(requete):
            raise StateTransitionError(
                "Cette requête a déjà été traitée et ne peut plus être modifiée.")

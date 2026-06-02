from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.features.dns.repository import DNSRepository
from app.features.vms.repository import VMRepository
from app.shared.models import DNSEntry, User
from app.shared.policies.permissions import AuthorizationPolicy
from app.shared.schemas.dns import DNSEntryCreate, DNSEntryRead, DNSEntryUpdate


class DNSService:
    """
    Service métier pour la gestion des entrées DNS.

    Règles d'accès :
    - Lister / Voir    : propriétaire de la VM ou Admin/SuperAdmin
    - Créer / Modifier : propriétaire de la VM ou Admin/SuperAdmin
    - Supprimer        : propriétaire de la VM ou Admin/SuperAdmin
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = DNSRepository(db)
        self.vm_repo = VMRepository(db)

    # ── Helpers internes ───────────────────────────────────────────────────────

    def _get_entry_or_404(self, dns_id: int) -> DNSEntry:
        entry = self.repo.get(dns_id)
        if entry is None:
            raise NotFoundError("Entrée DNS introuvable")
        return entry

    def _ensure_can_manage(self, user: User, vm_id: int) -> None:
        """Vérifie que l'utilisateur est propriétaire de la VM ou admin."""
        vm = self.vm_repo.get(vm_id)
        if vm is None:
            raise NotFoundError("VM introuvable")
        if vm.user_id != user.id and not AuthorizationPolicy.is_admin_or_superadmin(user):
            raise ForbiddenError(
                "Vous n'avez pas les droits pour gérer les DNS de cette VM."
            )

    def _check_hostname_unique(self, hostname: str, exclude_id: int | None = None) -> None:
        """Lève une ConflictError si le hostname est déjà utilisé."""
        existing = self.repo.get_by_hostname(hostname)
        if existing is not None and existing.id != exclude_id:
            raise ConflictError(
                f"Le nom de domaine '{hostname}' est déjà attribué à une autre VM."
            )

    # ── Lecture ────────────────────────────────────────────────────────────────

    def list_for_vm(self, user: User, vm_id: int, page: int, size: int) -> tuple[list[DNSEntry], int]:
        """Retourne toutes les entrées DNS d'une VM (filtrée par droits)."""
        self._ensure_can_manage(user, vm_id)
        offset = (page - 1) * size
        return self.repo.list_for_vm(vm_id, offset, size)

    def list_all(self, user: User, page: int, size: int) -> tuple[list[DNSEntry], int]:
        """Retourne toutes les entrées DNS (admin seulement)."""
        if not AuthorizationPolicy.is_admin_or_superadmin(user):
            raise ForbiddenError("Droits administrateur requis")
        offset = (page - 1) * size
        return self.repo.list_all(offset, size)

    def get(self, user: User, dns_id: int) -> DNSEntry:
        """Retourne une entrée DNS par son identifiant."""
        entry = self._get_entry_or_404(dns_id)
        self._ensure_can_manage(user, entry.vm_id)
        return entry

    # ── Écriture ───────────────────────────────────────────────────────────────

    def create(self, user: User, data: DNSEntryCreate) -> DNSEntry:
        """
        Crée une nouvelle entrée DNS pour une VM.
        - Vérifie que l'utilisateur peut gérer la VM cible.
        - Vérifie l'unicité du hostname sur l'ensemble du système.
        - Enrichit la réponse avec l'IP de la VM associée.
        """
        self._ensure_can_manage(user, data.vm_id)
        self._check_hostname_unique(data.hostname)
        entry = self.repo.create(data)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def update(self, user: User, dns_id: int, data: DNSEntryUpdate) -> DNSEntry:
        """Modifie le hostname d'une entrée DNS existante."""
        entry = self._get_entry_or_404(dns_id)
        self._ensure_can_manage(user, entry.vm_id)
        if data.hostname is not None:
            self._check_hostname_unique(data.hostname, exclude_id=dns_id)
        entry = self.repo.update(entry, data)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def delete(self, user: User, dns_id: int) -> None:
        """Supprime une entrée DNS."""
        entry = self._get_entry_or_404(dns_id)
        self._ensure_can_manage(user, entry.vm_id)
        self.repo.delete(entry)
        self.db.commit()

    # ── Sérialisation enrichie ─────────────────────────────────────────────────

    @staticmethod
    def to_read(entry: DNSEntry) -> DNSEntryRead:
        """Construit le schéma de lecture en injectant l'IP de la VM associée."""
        ip = entry.vm.ip_address if entry.vm else None
        return DNSEntryRead(
            id=entry.id,
            hostname=entry.hostname,
            vm_id=entry.vm_id,
            ip_address=ip,
        )

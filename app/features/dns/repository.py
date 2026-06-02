from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.shared.models import DNSEntry
from app.shared.schemas.dns import DNSEntryCreate, DNSEntryUpdate


class DNSRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Lecture ────────────────────────────────────────────────────────────────

    def get(self, dns_id: int) -> DNSEntry | None:
        return self.db.get(DNSEntry, dns_id)

    def get_by_hostname(self, hostname: str) -> DNSEntry | None:
        return self.db.execute(
            select(DNSEntry).where(DNSEntry.hostname == hostname.lower())
        ).scalar_one_or_none()

    def list_for_vm(self, vm_id: int, offset: int, limit: int) -> tuple[list[DNSEntry], int]:
        q = select(DNSEntry).where(DNSEntry.vm_id == vm_id)
        total = self.db.execute(
            select(func.count()).select_from(DNSEntry).where(DNSEntry.vm_id == vm_id)
        ).scalar_one()
        items = list(self.db.execute(q.offset(offset).limit(limit)).scalars().all())
        return items, total

    def list_all(self, offset: int, limit: int) -> tuple[list[DNSEntry], int]:
        total = self.db.execute(
            select(func.count()).select_from(DNSEntry)
        ).scalar_one()
        items = list(
            self.db.execute(select(DNSEntry).offset(offset).limit(limit)).scalars().all()
        )
        return items, total

    # ── Écriture ───────────────────────────────────────────────────────────────

    def create(self, data: DNSEntryCreate) -> DNSEntry:
        entry = DNSEntry(hostname=data.hostname.lower(), vm_id=data.vm_id)
        self.db.add(entry)
        self.db.flush()
        return entry

    def update(self, entry: DNSEntry, data: DNSEntryUpdate) -> DNSEntry:
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "hostname" and value is not None:
                value = value.lower()
            setattr(entry, field, value)
        self.db.flush()
        return entry

    def delete(self, entry: DNSEntry) -> None:
        self.db.delete(entry)
        self.db.flush()

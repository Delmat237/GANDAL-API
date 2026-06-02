"""
Tests unitaires – DNSService
Vérifie la logique métier (droits, unicité hostname, CRUD) avec une DB SQLite en mémoire.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.features.dns.service import DNSService
from app.shared.models import Base, DNSEntry, Student, Teacher, VM
from app.shared.schemas.dns import DNSEntryCreate, DNSEntryUpdate


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def users_and_vm(db):
    pwd = hash_password("secret123")
    admin = Teacher(username="admin", email="admin@dc.cm", password=pwd, role="SuperAdmin")
    teacher = Teacher(username="teacher", email="teacher@dc.cm", password=pwd, role="Teacher")
    student = Student(
        username="student", email="stu@dc.cm", password=pwd,
        matricule="STU001", level="L3", departement="Informatique",
    )
    db.add_all([admin, teacher, student])
    db.flush()

    vm = VM(
        size_rom=20, size_ram=2, n_cpu=2,
        status="up", ip_address="10.0.1.50",
        user_id=student.id,
    )
    db.add(vm)
    db.commit()
    db.refresh(admin)
    db.refresh(teacher)
    db.refresh(student)
    db.refresh(vm)
    return {"admin": admin, "teacher": teacher, "student": student, "vm": vm}


# ── Tests de création ──────────────────────────────────────────────────────────

class TestDNSServiceCreate:
    def test_owner_can_create_dns(self, db, users_and_vm):
        student = users_and_vm["student"]
        vm = users_and_vm["vm"]
        svc = DNSService(db)
        entry = svc.create(student, DNSEntryCreate(hostname="api.projet.dc.enspy.cm", vm_id=vm.id))
        assert entry.hostname == "api.projet.dc.enspy.cm"
        assert entry.vm_id == vm.id

    def test_admin_can_create_dns_for_any_vm(self, db, users_and_vm):
        admin = users_and_vm["admin"]
        vm = users_and_vm["vm"]
        svc = DNSService(db)
        entry = svc.create(admin, DNSEntryCreate(hostname="admin.projet.dc.enspy.cm", vm_id=vm.id))
        assert entry.id is not None

    def test_non_owner_teacher_cannot_create_dns(self, db, users_and_vm):
        teacher = users_and_vm["teacher"]
        vm = users_and_vm["vm"]
        svc = DNSService(db)
        with pytest.raises(ForbiddenError):
            svc.create(teacher, DNSEntryCreate(hostname="hack.dc.enspy.cm", vm_id=vm.id))

    def test_duplicate_hostname_raises_conflict(self, db, users_and_vm):
        student = users_and_vm["student"]
        vm = users_and_vm["vm"]
        svc = DNSService(db)
        svc.create(student, DNSEntryCreate(hostname="dupe.dc.enspy.cm", vm_id=vm.id))
        with pytest.raises(ConflictError):
            svc.create(student, DNSEntryCreate(hostname="dupe.dc.enspy.cm", vm_id=vm.id))

    def test_create_dns_for_nonexistent_vm_raises_not_found(self, db, users_and_vm):
        student = users_and_vm["student"]
        svc = DNSService(db)
        with pytest.raises(NotFoundError):
            svc.create(student, DNSEntryCreate(hostname="ghost.dc.enspy.cm", vm_id=9999))


# ── Tests de lecture ───────────────────────────────────────────────────────────

class TestDNSServiceGet:
    def test_owner_can_get_dns(self, db, users_and_vm):
        student = users_and_vm["student"]
        vm = users_and_vm["vm"]
        svc = DNSService(db)
        created = svc.create(student, DNSEntryCreate(hostname="get.dc.enspy.cm", vm_id=vm.id))
        fetched = svc.get(student, created.id)
        assert fetched.id == created.id

    def test_get_nonexistent_dns_raises_not_found(self, db, users_and_vm):
        student = users_and_vm["student"]
        svc = DNSService(db)
        with pytest.raises(NotFoundError):
            svc.get(student, 9999)

    def test_non_owner_cannot_get_dns(self, db, users_and_vm):
        student = users_and_vm["student"]
        teacher = users_and_vm["teacher"]
        vm = users_and_vm["vm"]
        svc = DNSService(db)
        created = svc.create(student, DNSEntryCreate(hostname="priv.dc.enspy.cm", vm_id=vm.id))
        with pytest.raises(ForbiddenError):
            svc.get(teacher, created.id)

    def test_list_for_vm_returns_entries(self, db, users_and_vm):
        student = users_and_vm["student"]
        vm = users_and_vm["vm"]
        svc = DNSService(db)
        svc.create(student, DNSEntryCreate(hostname="a.dc.enspy.cm", vm_id=vm.id))
        svc.create(student, DNSEntryCreate(hostname="b.dc.enspy.cm", vm_id=vm.id))
        items, total = svc.list_for_vm(student, vm.id, page=1, size=10)
        assert total == 2
        assert len(items) == 2

    def test_list_all_requires_admin(self, db, users_and_vm):
        student = users_and_vm["student"]
        svc = DNSService(db)
        with pytest.raises(ForbiddenError):
            svc.list_all(student, page=1, size=10)

    def test_list_all_admin_sees_everything(self, db, users_and_vm):
        student = users_and_vm["student"]
        admin = users_and_vm["admin"]
        vm = users_and_vm["vm"]
        svc = DNSService(db)
        svc.create(student, DNSEntryCreate(hostname="x.dc.enspy.cm", vm_id=vm.id))
        items, total = svc.list_all(admin, page=1, size=10)
        assert total >= 1


# ── Tests de modification ──────────────────────────────────────────────────────

class TestDNSServiceUpdate:
    def test_owner_can_update_hostname(self, db, users_and_vm):
        student = users_and_vm["student"]
        vm = users_and_vm["vm"]
        svc = DNSService(db)
        created = svc.create(student, DNSEntryCreate(hostname="old.dc.enspy.cm", vm_id=vm.id))
        updated = svc.update(student, created.id, DNSEntryUpdate(hostname="new.dc.enspy.cm"))
        assert updated.hostname == "new.dc.enspy.cm"

    def test_update_to_existing_hostname_raises_conflict(self, db, users_and_vm):
        student = users_and_vm["student"]
        vm = users_and_vm["vm"]
        svc = DNSService(db)
        svc.create(student, DNSEntryCreate(hostname="taken.dc.enspy.cm", vm_id=vm.id))
        e2 = svc.create(student, DNSEntryCreate(hostname="other.dc.enspy.cm", vm_id=vm.id))
        with pytest.raises(ConflictError):
            svc.update(student, e2.id, DNSEntryUpdate(hostname="taken.dc.enspy.cm"))

    def test_update_same_hostname_is_idempotent(self, db, users_and_vm):
        """Modifier un hostname par lui-même ne doit pas lever de ConflictError."""
        student = users_and_vm["student"]
        vm = users_and_vm["vm"]
        svc = DNSService(db)
        created = svc.create(student, DNSEntryCreate(hostname="same.dc.enspy.cm", vm_id=vm.id))
        updated = svc.update(student, created.id, DNSEntryUpdate(hostname="same.dc.enspy.cm"))
        assert updated.hostname == "same.dc.enspy.cm"

    def test_non_owner_cannot_update(self, db, users_and_vm):
        student = users_and_vm["student"]
        teacher = users_and_vm["teacher"]
        vm = users_and_vm["vm"]
        svc = DNSService(db)
        created = svc.create(student, DNSEntryCreate(hostname="noupdate.dc.enspy.cm", vm_id=vm.id))
        with pytest.raises(ForbiddenError):
            svc.update(teacher, created.id, DNSEntryUpdate(hostname="hacked.dc.enspy.cm"))


# ── Tests de suppression ───────────────────────────────────────────────────────

class TestDNSServiceDelete:
    def test_owner_can_delete_dns(self, db, users_and_vm):
        student = users_and_vm["student"]
        vm = users_and_vm["vm"]
        svc = DNSService(db)
        created = svc.create(student, DNSEntryCreate(hostname="todel.dc.enspy.cm", vm_id=vm.id))
        svc.delete(student, created.id)
        with pytest.raises(NotFoundError):
            svc.get(student, created.id)

    def test_admin_can_delete_any_dns(self, db, users_and_vm):
        student = users_and_vm["student"]
        admin = users_and_vm["admin"]
        vm = users_and_vm["vm"]
        svc = DNSService(db)
        created = svc.create(student, DNSEntryCreate(hostname="admindel.dc.enspy.cm", vm_id=vm.id))
        svc.delete(admin, created.id)
        with pytest.raises(NotFoundError):
            svc.get(admin, created.id)

    def test_non_owner_cannot_delete(self, db, users_and_vm):
        student = users_and_vm["student"]
        teacher = users_and_vm["teacher"]
        vm = users_and_vm["vm"]
        svc = DNSService(db)
        created = svc.create(student, DNSEntryCreate(hostname="nodelete.dc.enspy.cm", vm_id=vm.id))
        with pytest.raises(ForbiddenError):
            svc.delete(teacher, created.id)

    def test_delete_nonexistent_raises_not_found(self, db, users_and_vm):
        student = users_and_vm["student"]
        svc = DNSService(db)
        with pytest.raises(NotFoundError):
            svc.delete(student, 9999)


# ── Test to_read enrichit l'IP ─────────────────────────────────────────────────

class TestDNSServiceToRead:
    def test_to_read_injects_vm_ip(self, db, users_and_vm):
        student = users_and_vm["student"]
        vm = users_and_vm["vm"]
        svc = DNSService(db)
        entry = svc.create(student, DNSEntryCreate(hostname="ip.dc.enspy.cm", vm_id=vm.id))
        read = DNSService.to_read(entry)
        assert read.ip_address == "10.0.1.50"
        assert read.hostname == "ip.dc.enspy.cm"

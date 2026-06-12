from datetime import datetime
from sqlalchemy import UniqueConstraint
from sqlalchemy import (
    Column, Integer, String, Text, Enum, ForeignKey, DateTime, Boolean
)
from sqlalchemy.orm import relationship, DeclarativeBase


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False, unique=True)
    email = Column(String(255), nullable=False, unique=True)
    password = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)

    vms = relationship("VM", back_populates="user",
                       cascade="all, delete-orphan")
    publications = relationship(
        "Publication", back_populates="user", cascade="all, delete-orphan")

    __mapper_args__ = {
        "polymorphic_on": type,
        "polymorphic_identity": "user",
    }


class Student(User):
    __tablename__ = "students"

    id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    matricule = Column(String(50), nullable=False, unique=True)
    level = Column(String(50), nullable=False)
    departement = Column(String(100), nullable=False)

    sent_requests = relationship(
        "Requete", foreign_keys="Requete.student_id", back_populates="student")

    __mapper_args__ = {
        "polymorphic_identity": "student",
    }


class Teacher(User):
    __tablename__ = "teachers"

    id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    role = Column(String(100), nullable=False)

    received_requests = relationship(
        "Requete", foreign_keys="Requete.teacher_id", back_populates="teacher")

    __mapper_args__ = {
        "polymorphic_identity": "teacher",
    }


class VM(Base):
    __tablename__ = "vms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    size_rom = Column(Integer, nullable=False)
    size_ram = Column(Integer, nullable=False)
    iso = Column(String(255))
    ip_address = Column(String(50))
    id_proxmox = Column(Integer)
    node = Column(String(100))
    n_cpu = Column(Integer, nullable=False)
    iso_image = Column(String(255))
    status = Column(
        Enum("up", "waiting", "stopped", name="vm_status"),
        nullable=False,
        default="stopped",
    )
    date_stop_at = Column(DateTime)
    ssh_public_key = Column(Text)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="vms")

    delete_requests = relationship("RDeleteVM", back_populates="vm")
    dns_entries = relationship("DNSEntry", back_populates="vm", cascade="all, delete-orphan")


class NetworkLink(Base):
    """Lien réseau (arête de la toile) entre deux VMs omega, par VMID Proxmox.

    Stocke l'INTENTION (qui est relié à qui) ; l'enforcement réel est fait par
    vm-link.sh sur les nœuds. Source fiable pour dessiner les arêtes du graphe.
    """
    __tablename__ = "network_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vmid_a = Column(Integer, nullable=False, index=True)
    vmid_b = Column(Integer, nullable=False, index=True)
    group_name = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)


class Requete(Base):
    __tablename__ = "requetes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    object = Column(String(255), nullable=False)
    content = Column(Text)
    type = Column(String(50), nullable=False)
    status = Column(
        Enum("pending", "validated", "rejected", name="requete_status"),
        nullable=False,
        default="pending",
    )

    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)

    student = relationship("Student", foreign_keys=[
                           student_id], back_populates="sent_requests")
    teacher = relationship("Teacher", foreign_keys=[
                           teacher_id], back_populates="received_requests")

    __mapper_args__ = {
        "polymorphic_on": type,
        "polymorphic_identity": "requete",
    }


class RCreateVM(Requete):
    __tablename__ = "r_create_vms"

    id = Column(Integer, ForeignKey("requetes.id"), primary_key=True)
    size_rom = Column(Integer, nullable=False)
    size_ram = Column(Integer, nullable=False)
    n_cpu = Column(Integer, nullable=False, default=2, server_default="2")
    os = Column(String(100), nullable=False)

    __mapper_args__ = {
        "polymorphic_identity": "r_create_vm",
    }


class RDeleteVM(Requete):
    __tablename__ = "r_delete_vms"

    id = Column(Integer, ForeignKey("requetes.id"), primary_key=True)
    vm_id = Column(Integer, ForeignKey("vms.id"), nullable=False)

    vm = relationship("VM", back_populates="delete_requests")

    __mapper_args__ = {
        "polymorphic_identity": "r_delete_vm",
    }


class RAccount(Requete):
    __tablename__ = "r_accounts"

    id = Column(Integer, ForeignKey("requetes.id"), primary_key=True)
    nom = Column(String(150), nullable=False)
    email = Column(String(255), nullable=False)
    justification = Column(Text)
    matricule = Column(String(50))
    organisation = Column(String(150))

    __mapper_args__ = {
        "polymorphic_identity": "r_account",
    }


class Publication(Base):
    __tablename__ = "publications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nom = Column(String(255), nullable=False)
    lien = Column(String(500))
    description = Column(Text)
    photo = Column(String(500))
    status = Column(
        Enum("draft", "published", "archived", name="publication_status"),
        nullable=False,
        default="draft",
    )

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="publications")


class DNSEntry(Base):
    """
    Entrée DNS associant un nom de domaine (hostname FQDN) à une VM.
    Un même hostname ne peut pointer que vers une seule VM (unicité globale).
    """
    __tablename__ = "dns_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hostname = Column(String(255), nullable=False, unique=True)
    """Nom de domaine complet, ex: api.monprojet.dc.enspy.cm"""

    vm_id = Column(Integer, ForeignKey("vms.id"), nullable=False)
    vm = relationship("VM", back_populates="dns_entries")

    __table_args__ = (
        UniqueConstraint("hostname", name="uq_dns_hostname"),
    )

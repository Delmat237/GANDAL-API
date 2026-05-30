"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "students",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("matricule", sa.String(length=50), nullable=False),
        sa.Column("level", sa.String(length=50), nullable=False),
        sa.Column("departement", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(["id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("matricule"),
    )
    op.create_table(
        "teachers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(["id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "vms",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("size_rom", sa.Integer(), nullable=False),
        sa.Column("size_ram", sa.Integer(), nullable=False),
        sa.Column("iso", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=50), nullable=True),
        sa.Column("id_proxmox", sa.Integer(), nullable=True),
        sa.Column("node", sa.String(length=100), nullable=True),
        sa.Column("n_cpu", sa.Integer(), nullable=False),
        sa.Column("iso_image", sa.String(length=255), nullable=True),
        sa.Column("status", sa.Enum("up", "waiting", "stopped",
                  name="vm_status"), nullable=False),
        sa.Column("date_stop_at", sa.DateTime(), nullable=True),
        sa.Column("ssh_public_key", sa.Text(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "requetes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("object", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "validated", "rejected", name="requete_status"),
            nullable=False,
        ),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "r_create_vms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("size_rom", sa.Integer(), nullable=False),
        sa.Column("size_ram", sa.Integer(), nullable=False),
        sa.Column("os", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(["id"], ["requetes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "r_delete_vms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vm_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["id"], ["requetes.id"]),
        sa.ForeignKeyConstraint(["vm_id"], ["vms.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "r_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nom", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("matricule", sa.String(length=50), nullable=True),
        sa.Column("organisation", sa.String(length=150), nullable=True),
        sa.ForeignKeyConstraint(["id"], ["requetes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "publications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nom", sa.String(length=255), nullable=False),
        sa.Column("lien", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("photo", sa.String(length=500), nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "published", "archived",
                    name="publication_status"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("publications")
    op.drop_table("r_accounts")
    op.drop_table("r_delete_vms")
    op.drop_table("r_create_vms")
    op.drop_table("requetes")
    op.drop_table("vms")
    op.drop_table("teachers")
    op.drop_table("students")
    op.drop_table("users")
    sa.Enum(name="vm_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="requete_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="publication_status").drop(op.get_bind(), checkfirst=True)

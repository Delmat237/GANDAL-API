"""RBAC: users.is_active + students.supervisor_id + requetes.teacher_id nullable

Hiérarchie : super admin -> enseignants -> étudiants. Un étudiant choisit son
enseignant à l'inscription ; l'enseignant valide le compte et devient son
superviseur (supervisor_id). Un compte inactif (is_active=False) = bloqué ou
en attente de validation. teacher_id devient nullable (demandes de domaine
routées au super admin, demandes en attente d'affectation).

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users.is_active (par défaut actif pour les comptes existants)
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
    )

    # students.supervisor_id -> teachers.id (nullable)
    with op.batch_alter_table("students") as batch:
        batch.add_column(sa.Column("supervisor_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_students_supervisor_id_teachers",
            "teachers",
            ["supervisor_id"],
            ["id"],
        )

    # requetes.teacher_id et student_id -> nullable (self-signup r_account)
    with op.batch_alter_table("requetes") as batch:
        batch.alter_column(
            "teacher_id", existing_type=sa.Integer(), nullable=True
        )
        batch.alter_column(
            "student_id", existing_type=sa.Integer(), nullable=True
        )


def downgrade() -> None:
    with op.batch_alter_table("requetes") as batch:
        batch.alter_column(
            "student_id", existing_type=sa.Integer(), nullable=False
        )
        batch.alter_column(
            "teacher_id", existing_type=sa.Integer(), nullable=False
        )
    with op.batch_alter_table("students") as batch:
        batch.drop_constraint("fk_students_supervisor_id_teachers", type_="foreignkey")
        batch.drop_column("supervisor_id")
    op.drop_column("users", "is_active")

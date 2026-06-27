"""add r_domains table (demande de nom de domaine VM_IP:port -> nom_choisi)

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "r_domains",
        sa.Column("id", sa.Integer(), sa.ForeignKey("requetes.id"), primary_key=True),
        sa.Column("vm_id", sa.Integer(), sa.ForeignKey("vms.id"), nullable=False),
        sa.Column("hostname", sa.String(length=100), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("r_domains")

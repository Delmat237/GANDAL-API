"""add dns_entries table

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dns_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("vm_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["vm_id"], ["vms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hostname", name="uq_dns_hostname"),
    )
    op.create_index("ix_dns_entries_vm_id", "dns_entries", ["vm_id"])


def downgrade() -> None:
    op.drop_index("ix_dns_entries_vm_id", table_name="dns_entries")
    op.drop_table("dns_entries")

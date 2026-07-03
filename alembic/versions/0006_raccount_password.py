"""r_accounts.password_hash : l'étudiant choisit son mot de passe à l'inscription

Le mot de passe saisi au signup est stocké HACHÉ dans la demande d'inscription,
puis réutilisé à l'approbation pour créer le compte (au lieu d'un mot de passe
aléatoire que l'étudiant ne connaîtrait pas).

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "r_accounts",
        sa.Column("password_hash", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("r_accounts", "password_hash")

"""add discovery columns

Revision ID: b1c2d3e4f5a6
Revises: 7cd1193b651b
Create Date: 2026-06-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "7cd1193b651b"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("discovery_status", sa.String(), nullable=False, server_default="none"),
    )
    op.add_column(
        "companies",
        sa.Column("discovery_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("companies", "discovery_message")
    op.drop_column("companies", "discovery_status")

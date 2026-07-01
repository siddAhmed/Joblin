"""add activities_content to resume

Revision ID: f3a4b5c6d7e8
Revises: d9213ed6bef3
Create Date: 2026-07-01

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, None] = "d9213ed6bef3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("resume", sa.Column("activities_content", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("resume", "activities_content")

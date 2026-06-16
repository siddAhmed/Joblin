"""add preview_only to jobs and total_new_jobs to runs

Revision ID: d2e3f4a5b6c7
Revises: b1c2d3e4f5a6
Create Date: 2026-06-16

Jobs indexed by preview runs were never processable by real runs, causing
real runs to report 0 confirmed even when thousands of jobs existed.
preview_only=True marks jobs that need to be processed by the first real run.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("preview_only", sa.Boolean(), nullable=False, server_default="1"))
    # All existing jobs were indexed by preview runs — mark them for re-processing
    op.execute("UPDATE jobs SET preview_only = 1")
    # Remove server_default so future inserts must supply the value explicitly
    op.alter_column("jobs", "preview_only", server_default=None)

    op.add_column("runs", sa.Column("total_new_jobs", sa.Integer(), nullable=False, server_default="0"))
    op.alter_column("runs", "total_new_jobs", server_default=None)


def downgrade() -> None:
    op.drop_column("jobs", "preview_only")
    op.drop_column("runs", "total_new_jobs")

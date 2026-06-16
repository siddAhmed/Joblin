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


def _existing_columns(table: str) -> set:
    conn = op.get_bind()
    rows = conn.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return {row[1] for row in rows}


def upgrade() -> None:
    # Guard against re-runs: a prior partial run may have added the column
    # without recording the revision in alembic_version.
    jobs_cols = _existing_columns("jobs")
    if "preview_only" not in jobs_cols:
        op.execute(sa.text("ALTER TABLE jobs ADD COLUMN preview_only BOOLEAN NOT NULL DEFAULT 1"))
    # Mark all existing jobs for re-processing by the first real run
    op.execute(sa.text("UPDATE jobs SET preview_only = 1"))

    runs_cols = _existing_columns("runs")
    if "total_new_jobs" not in runs_cols:
        op.execute(sa.text("ALTER TABLE runs ADD COLUMN total_new_jobs INTEGER NOT NULL DEFAULT 0"))


def downgrade() -> None:
    pass

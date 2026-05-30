"""add job_skills table

Revision ID: c8f2a1b3d4e5
Revises: b7e3f9a12c45
Create Date: 2026-05-29

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "c8f2a1b3d4e5"
down_revision: Union[str, None] = "b7e3f9a12c45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_skills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("skill_name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("job_id", "skill_name", name="uq_job_skill"),
    )
    op.create_index("ix_job_skills_skill_name", "job_skills", ["skill_name"])
    op.create_index("ix_job_skills_job_id", "job_skills", ["job_id"])


def downgrade() -> None:
    op.drop_table("job_skills")

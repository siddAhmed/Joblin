"""add token_usage table

Revision ID: b7e3f9a12c45
Revises: cd04a68573d1
Create Date: 2026-05-28

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "b7e3f9a12c45"
down_revision: Union[str, None] = "cd04a68573d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "token_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("call_type", sa.String(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), default=0),
        sa.Column("completion_tokens", sa.Integer(), default=0),
        sa.Column("total_tokens", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_token_usage_run_id", "token_usage", ["run_id"])
    op.create_index("ix_token_usage_provider", "token_usage", ["provider"])
    op.create_index("ix_token_usage_created_at", "token_usage", ["created_at"])


def downgrade() -> None:
    op.drop_table("token_usage")

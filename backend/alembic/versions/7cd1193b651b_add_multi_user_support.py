"""add multi-user support

Revision ID: 7cd1193b651b
Revises: f1a2b3c4d5e6
Create Date: 2026-06-14

"""
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "7cd1193b651b"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(bind, table: str, column: str) -> bool:
    return any(
        col["name"] == column for col in inspect(bind).get_columns(table)
    )


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    # 1. Create users table (guard: create_all may have already created it)
    if not insp.has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("authentik_username", sa.String(), nullable=False),
            sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("authentik_username", name="uq_users_authentik_username"),
        )

    # 2. Seed admin user from ADMIN_USERNAME env var (idempotent)
    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    existing = bind.execute(
        sa.text("SELECT id FROM users WHERE authentik_username = :u"),
        {"u": admin_username},
    ).fetchone()
    if existing is None:
        bind.execute(
            sa.text("INSERT INTO users (authentik_username, is_admin) VALUES (:u, 1)"),
            {"u": admin_username},
        )

    # 3. companies: add user_id, fill, enforce NOT NULL
    # Note: ForeignKey not added via add_column -- SQLite does not support ADD CONSTRAINT via ALTER TABLE.
    # FK relationship is enforced at the ORM layer. batch_alter_table is used to flip nullable=False.
    if not _has_column(bind, "companies", "user_id"):
        op.add_column("companies", sa.Column("user_id", sa.Integer(), nullable=True))
        op.execute("UPDATE companies SET user_id = 1")
        with op.batch_alter_table("companies") as b:
            b.alter_column("user_id", existing_type=sa.Integer(), nullable=False)

    # 4. jobs: user_id derived from parent company
    if not _has_column(bind, "jobs", "user_id"):
        op.add_column("jobs", sa.Column("user_id", sa.Integer(), nullable=True))
        op.execute("UPDATE jobs SET user_id = (SELECT c.user_id FROM companies c WHERE c.id = jobs.company_id)")
        with op.batch_alter_table("jobs") as b:
            b.alter_column("user_id", existing_type=sa.Integer(), nullable=False)

    # 5. runs
    if not _has_column(bind, "runs", "user_id"):
        op.add_column("runs", sa.Column("user_id", sa.Integer(), nullable=True))
        op.execute("UPDATE runs SET user_id = 1")
        with op.batch_alter_table("runs") as b:
            b.alter_column("user_id", existing_type=sa.Integer(), nullable=False)

    # 6. application_tracking
    if not _has_column(bind, "application_tracking", "user_id"):
        op.add_column("application_tracking", sa.Column("user_id", sa.Integer(), nullable=True))
        op.execute("UPDATE application_tracking SET user_id = 1")
        with op.batch_alter_table("application_tracking") as b:
            b.alter_column("user_id", existing_type=sa.Integer(), nullable=False)

    # 7. feedback_examples
    if not _has_column(bind, "feedback_examples", "user_id"):
        op.add_column("feedback_examples", sa.Column("user_id", sa.Integer(), nullable=True))
        op.execute("UPDATE feedback_examples SET user_id = 1")
        with op.batch_alter_table("feedback_examples") as b:
            b.alter_column("user_id", existing_type=sa.Integer(), nullable=False)

    # 8. resume
    if not _has_column(bind, "resume", "user_id"):
        op.add_column("resume", sa.Column("user_id", sa.Integer(), nullable=True))
        op.execute("UPDATE resume SET user_id = 1")
        with op.batch_alter_table("resume") as b:
            b.alter_column("user_id", existing_type=sa.Integer(), nullable=False)

    # 9. Recreate settings with surrogate PK + user_id
    # Only migrate if the old schema (no id column) is still present
    settings_cols = {col["name"] for col in insp.get_columns("settings")}
    if "id" not in settings_cols:
        op.rename_table("settings", "_settings_old")
        op.create_table(
            "settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("key", sa.String(), nullable=False),
            sa.Column("value", sa.JSON(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "key", name="uq_settings_user_key"),
        )
        bind.execute(
            sa.text("INSERT INTO settings (user_id, key, value, updated_at) SELECT 1, key, value, updated_at FROM _settings_old")
        )
        op.drop_table("_settings_old")


def downgrade() -> None:
    op.drop_table("settings")
    op.rename_table("_settings_old", "settings")
    with op.batch_alter_table("resume") as b:
        b.drop_column("user_id")
    with op.batch_alter_table("feedback_examples") as b:
        b.drop_column("user_id")
    with op.batch_alter_table("application_tracking") as b:
        b.drop_column("user_id")
    with op.batch_alter_table("runs") as b:
        b.drop_column("user_id")
    with op.batch_alter_table("jobs") as b:
        b.drop_column("user_id")
    with op.batch_alter_table("companies") as b:
        b.drop_column("user_id")
    op.drop_table("users")

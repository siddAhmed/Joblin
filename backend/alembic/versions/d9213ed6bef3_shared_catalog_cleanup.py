"""shared_catalog_cleanup

Revision ID: d9213ed6bef3
Revises: 1e82ee71e62b
Create Date: 2026-06-18 18:18:29.970193

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9213ed6bef3'
down_revision: Union[str, Sequence[str], None] = '1e82ee71e62b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("companies", "_deprecated_companies")
    op.rename_table("jobs", "_deprecated_jobs")


def downgrade() -> None:
    op.rename_table("_deprecated_companies", "companies")
    op.rename_table("_deprecated_jobs", "jobs")

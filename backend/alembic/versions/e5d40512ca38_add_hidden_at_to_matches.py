"""add_hidden_at_to_matches

Revision ID: e5d40512ca38
Revises: d2e3f4a5b6c7
Create Date: 2026-06-17 21:20:37.091601

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5d40512ca38'
down_revision: Union[str, Sequence[str], None] = 'd2e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('matches', sa.Column('hidden_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('matches', 'hidden_at')

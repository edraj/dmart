"""add firebase_token to sessions table

Revision ID: a1b2c3d4e5f6
Revises: 2338186ee676
Create Date: 2026-03-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '2338186ee676'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'sessions',
        sa.Column('firebase_token', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('sessions', 'firebase_token')

"""rename users firebase_token to device_id

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-09

"""
from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'users',
        'firebase_token',
        new_column_name='device_id',
    )


def downgrade() -> None:
    op.alter_column(
        'users',
        'device_id',
        new_column_name='firebase_token',
    )

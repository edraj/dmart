"""ext permission with filter_fields_values

Revision ID: 1cf4e1ee3cb8
Revises: 3c8bca2219cc
Create Date: 2025-09-18 10:37:55.573932

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '1cf4e1ee3cb8'
down_revision: Union[str, None] = '3c8bca2219cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('permissions', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('filter_fields_values', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        )


def downgrade() -> None:
    with op.batch_alter_table('permissions', schema=None) as batch_op:
        batch_op.drop_column('filter_fields_values')

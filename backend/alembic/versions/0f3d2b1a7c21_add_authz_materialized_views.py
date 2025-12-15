"""add authz materialized views and meta table

Revision ID: 0f3d2b1a7c21
Revises: 98ecd6f56f9a
Create Date: 2025-09-25 07:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0f3d2b1a7c21'
down_revision: Union[str, None] = '98ecd6f56f9a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create meta table to track MV refresh times
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS authz_mv_meta (
            id INT PRIMARY KEY,
            last_source_ts TIMESTAMPTZ,
            refreshed_at TIMESTAMPTZ
        )
        """
    )
    # Seed a single row with id=1 if not exists
    op.execute(
        """
        INSERT INTO authz_mv_meta(id, last_source_ts, refreshed_at)
        VALUES (1, to_timestamp(0), now())
        ON CONFLICT (id) DO NOTHING
        """
    )

    # Create materialized view for user->roles
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_user_roles AS
        SELECT u.shortname AS user_shortname,
               r.shortname AS role_shortname
        FROM users u
        JOIN LATERAL jsonb_array_elements_text(u.roles) AS role_name ON TRUE
        JOIN roles r ON r.shortname = role_name
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_user_roles_unique
        ON mv_user_roles (user_shortname, role_shortname)
        """
    )

    # Create materialized view for role->permissions
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_role_permissions AS
        SELECT r.shortname AS role_shortname,
               p.shortname AS permission_shortname
        FROM roles r
        JOIN LATERAL jsonb_array_elements_text(r.permissions) AS perm_name ON TRUE
        JOIN permissions p ON p.shortname = perm_name
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_role_permissions_unique
        ON mv_role_permissions (role_shortname, permission_shortname)
        """
    )


def downgrade() -> None:
    # Drop unique indexes first
    op.execute("DROP INDEX IF EXISTS idx_mv_role_permissions_unique")
    op.execute("DROP INDEX IF EXISTS idx_mv_user_roles_unique")

    # Drop materialized views
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_role_permissions")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_user_roles")

    # Drop meta table
    op.execute("DROP TABLE IF EXISTS authz_mv_meta")

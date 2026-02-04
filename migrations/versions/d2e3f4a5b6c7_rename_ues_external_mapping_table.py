"""rename ues external mapping table

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b7
Create Date: 2026-01-29 00:00:00.000000
"""

from alembic import op
from sqlalchemy import inspect

from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b7"
branch_labels = None
depends_on = None


OLD_TABLE = "gs_union_energy_system_external_mappings"
NEW_TABLE = "gs_fue_em_union_energy_system"


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table(OLD_TABLE, schema=SCHEMA_FUEL):
        op.execute(
            f"ALTER TABLE {SCHEMA_FUEL}.{OLD_TABLE} "
            f"RENAME TO {NEW_TABLE}"
        )
        op.execute(
            f"ALTER SEQUENCE IF EXISTS {SCHEMA_FUEL}.{OLD_TABLE}_id_seq "
            f"RENAME TO {NEW_TABLE}_id_seq"
        )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table(NEW_TABLE, schema=SCHEMA_FUEL):
        op.execute(
            f"ALTER TABLE {SCHEMA_FUEL}.{NEW_TABLE} "
            f"RENAME TO {OLD_TABLE}"
        )
        op.execute(
            f"ALTER SEQUENCE IF EXISTS {SCHEMA_FUEL}.{NEW_TABLE}_id_seq "
            f"RENAME TO {OLD_TABLE}_id_seq"
        )

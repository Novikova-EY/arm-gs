"""rename equipment group set tables

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-01-29 00:00:00.000000
"""

from alembic import op
from sqlalchemy import inspect

from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "e3f4a5b6c7d8"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


OLD_SETS = "equipment_group_sets"
OLD_LINKS = "equipment_group_set_stations"
NEW_SETS = "gs_fue_equipment_group_sets"
NEW_LINKS = "gs_fue_equipment_group_set_stations"


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table(OLD_SETS, schema=SCHEMA_FUEL):
        op.execute(
            f"ALTER TABLE {SCHEMA_FUEL}.{OLD_SETS} "
            f"RENAME TO {NEW_SETS}"
        )
        op.execute(
            f"ALTER SEQUENCE IF EXISTS {SCHEMA_FUEL}.{OLD_SETS}_id_seq "
            f"RENAME TO {NEW_SETS}_id_seq"
        )

    if inspector.has_table(OLD_LINKS, schema=SCHEMA_FUEL):
        op.execute(
            f"ALTER TABLE {SCHEMA_FUEL}.{OLD_LINKS} "
            f"RENAME TO {NEW_LINKS}"
        )
        op.execute(
            f"ALTER SEQUENCE IF EXISTS {SCHEMA_FUEL}.{OLD_LINKS}_id_seq "
            f"RENAME TO {NEW_LINKS}_id_seq"
        )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table(NEW_LINKS, schema=SCHEMA_FUEL):
        op.execute(
            f"ALTER TABLE {SCHEMA_FUEL}.{NEW_LINKS} "
            f"RENAME TO {OLD_LINKS}"
        )
        op.execute(
            f"ALTER SEQUENCE IF EXISTS {SCHEMA_FUEL}.{NEW_LINKS}_id_seq "
            f"RENAME TO {OLD_LINKS}_id_seq"
        )

    if inspector.has_table(NEW_SETS, schema=SCHEMA_FUEL):
        op.execute(
            f"ALTER TABLE {SCHEMA_FUEL}.{NEW_SETS} "
            f"RENAME TO {OLD_SETS}"
        )
        op.execute(
            f"ALTER SEQUENCE IF EXISTS {SCHEMA_FUEL}.{NEW_SETS}_id_seq "
            f"RENAME TO {OLD_SETS}_id_seq"
        )

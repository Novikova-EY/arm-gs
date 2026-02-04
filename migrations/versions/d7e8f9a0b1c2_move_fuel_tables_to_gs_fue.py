"""move fuel tables to gs_fue

Revision ID: d7e8f9a0b1c2
Revises: f3a4b5c6d7e8
Create Date: 2026-01-27 00:00:00.000000
"""

from alembic import op
from sqlalchemy import inspect
from config import SCHEMA_FUEL, SCHEMA_GENERATION


# revision identifiers, used by Alembic.
revision = "d7e8f9a0b1c2"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_FUEL}")

    if inspector.has_table("equipment_group_sets", schema=SCHEMA_GENERATION):
        op.execute(
            f"ALTER TABLE {SCHEMA_GENERATION}.equipment_group_sets SET SCHEMA {SCHEMA_FUEL}"
        )
    if inspector.has_table("equipment_group_set_stations", schema=SCHEMA_GENERATION):
        op.execute(
            f"ALTER TABLE {SCHEMA_GENERATION}.equipment_group_set_stations SET SCHEMA {SCHEMA_FUEL}"
        )

    op.execute(
        f"ALTER SEQUENCE IF EXISTS {SCHEMA_GENERATION}.equipment_group_sets_id_seq "
        f"SET SCHEMA {SCHEMA_FUEL}"
    )
    op.execute(
        f"ALTER SEQUENCE IF EXISTS {SCHEMA_GENERATION}.equipment_group_set_stations_id_seq "
        f"SET SCHEMA {SCHEMA_FUEL}"
    )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_GENERATION}")

    if inspector.has_table("equipment_group_sets", schema=SCHEMA_FUEL):
        op.execute(
            f"ALTER TABLE {SCHEMA_FUEL}.equipment_group_sets SET SCHEMA {SCHEMA_GENERATION}"
        )
    if inspector.has_table("equipment_group_set_stations", schema=SCHEMA_FUEL):
        op.execute(
            f"ALTER TABLE {SCHEMA_FUEL}.equipment_group_set_stations SET SCHEMA {SCHEMA_GENERATION}"
        )

    op.execute(
        f"ALTER SEQUENCE IF EXISTS {SCHEMA_FUEL}.equipment_group_sets_id_seq "
        f"SET SCHEMA {SCHEMA_GENERATION}"
    )
    op.execute(
        f"ALTER SEQUENCE IF EXISTS {SCHEMA_FUEL}.equipment_group_set_stations_id_seq "
        f"SET SCHEMA {SCHEMA_GENERATION}"
    )

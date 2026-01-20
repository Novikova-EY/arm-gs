"""fill database_version_id for station_equipment_groups

Revision ID: c7d8e9f0a1b2
Revises: f1b2c3d4e5f6
Create Date: 2026-01-16 00:00:00.000000

Заполняет station_equipment_groups.database_version_id
по значению database_version_id у станции.
"""

from alembic import op
from sqlalchemy import inspect
from config import SCHEMA_GENERATION


# revision identifiers, used by Alembic.
revision = "c7d8e9f0a1b2"
down_revision = "f1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table("station_equipment_groups", schema=SCHEMA_GENERATION):
        return

    op.execute(
        f"""
        UPDATE {SCHEMA_GENERATION}.station_equipment_groups seg
        SET database_version_id = st.database_version_id
        FROM {SCHEMA_GENERATION}.stations st
        WHERE seg.id_station = st.id
          AND seg.database_version_id IS NULL
          AND st.database_version_id IS NOT NULL
        """
    )


def downgrade():
    # Откат не требуется: заполнение данных
    pass

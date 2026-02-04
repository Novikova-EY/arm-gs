"""fill equipment_group_sets names

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-01-26 00:00:00.000000

Заполняет name для equipment_group_sets как "Станция (Группа оборудования)".
"""

from alembic import op
from config import SCHEMA_GENERATION, SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        f"""
        WITH link_station AS (
            SELECT DISTINCT ON (egs.id)
                egs.id AS equipment_group_set_id,
                link.station_id,
                egs.database_version_id
            FROM {SCHEMA_GENERATION}.equipment_group_sets egs
            JOIN {SCHEMA_GENERATION}.equipment_group_set_stations link
              ON link.equipment_group_set_id = egs.id
            WHERE (
                (egs.database_version_id IS NULL AND link.database_version_id IS NULL)
                OR egs.database_version_id = link.database_version_id
            )
            ORDER BY egs.id, link.station_id
        )
        UPDATE {SCHEMA_GENERATION}.equipment_group_sets egs
        SET name = s.name || ' (' || eg.name || ')'
        FROM link_station ls,
             {SCHEMA_GENERATION}.stations s,
             {SCHEMA_REFDATA}.gs_equipment_groups eg
        WHERE egs.id = ls.equipment_group_set_id
          AND s.id = ls.station_id
          AND eg.id = egs.id_equipment_group
          AND (egs.name IS NULL OR egs.name = '')
          AND (
            (egs.database_version_id IS NULL AND s.database_version_id IS NULL)
            OR egs.database_version_id = s.database_version_id
          )
          AND (
            (egs.database_version_id IS NULL AND eg.database_version_id IS NULL)
            OR egs.database_version_id = eg.database_version_id
          )
        """
    )


def downgrade():
    op.execute(
        f"""
        UPDATE {SCHEMA_GENERATION}.equipment_group_sets
        SET name = NULL
        """
    )

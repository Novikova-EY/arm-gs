"""drop station name+district version unique constraint

Revision ID: q4r5s6t7u8v9
Revises: p2q3r4s5t6u7
Create Date: 2026-02-25 12:00:00.000000

Удаляет ограничение уникальности (name, id_regional_district, database_version_id)
из таблицы stations для упрощения копирования версий БД.
"""

from alembic import op
from config import SCHEMA_GENERATION


revision = "q4r5s6t7u8v9"
down_revision = "p2q3r4s5t6u7"
branch_labels = None
depends_on = None


def upgrade():
    schema = SCHEMA_GENERATION or "gs_gen"
    op.execute(
        f"""
        DROP INDEX IF EXISTS {schema}.uq_station_name_district_version;
        ALTER TABLE {schema}.stations DROP CONSTRAINT IF EXISTS uq_station_name_district_version;
        ALTER TABLE {schema}.stations DROP CONSTRAINT IF EXISTS uq_station_name_district;
        """
    )


def downgrade():
    schema = SCHEMA_GENERATION or "gs_gen"
    op.create_unique_constraint(
        "uq_station_name_district",
        "stations",
        ["name", "id_regional_district"],
        schema=schema,
    )
    op.create_index(
        "uq_station_name_district_version",
        "stations",
        ["name", "id_regional_district", "database_version_id"],
        unique=True,
        schema=schema,
    )

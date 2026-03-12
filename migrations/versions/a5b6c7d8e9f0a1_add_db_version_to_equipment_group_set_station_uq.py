"""add database_version_id to equipment_group_set_stations unique constraint

Revision ID: a5b6c7d8e9f0a1
Revises: z3a4b5c6d7e8f9
Create Date: 2026-02-25 08:00:00.000000

Ограничение уникальности uq_equipment_group_set_stations_set_station было на (equipment_group_set_id, station_id),
что не позволяло копировать одну и ту же связь в разные версии БД. Добавляем database_version_id в ограничение,
чтобы (set_id, station_id) было уникально в рамках каждой версии.
"""

from alembic import op
from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "a5b6c7d8e9f0a1"
down_revision = "z3a4b5c6d7e8f9"
branch_labels = None
depends_on = None

TABLE = "gs_fue_equipment_group_set_stations"
OLD_CONSTRAINT = "uq_equipment_group_set_stations_set_station"
NEW_CONSTRAINT = "uq_equipment_group_set_stations_set_station_version"


def upgrade():
    from sqlalchemy import inspect
    inspector = inspect(op.get_bind())
    if not inspector.has_table(TABLE, schema=SCHEMA_FUEL):
        return
    # Удаляем старое ограничение (equipment_group_set_id, station_id)
    op.drop_constraint(
        OLD_CONSTRAINT,
        TABLE,
        schema=SCHEMA_FUEL,
        type_="unique",
    )
    # Создаём новое с учётом database_version_id
    # NULL в database_version_id считаются разными в PostgreSQL, но для версионированных данных обычно задано
    op.create_unique_constraint(
        NEW_CONSTRAINT,
        TABLE,
        ["equipment_group_set_id", "station_id", "database_version_id"],
        schema=SCHEMA_FUEL,
    )


def downgrade():
    from sqlalchemy import inspect
    inspector = inspect(op.get_bind())
    if not inspector.has_table(TABLE, schema=SCHEMA_FUEL):
        return
    op.drop_constraint(
        NEW_CONSTRAINT,
        TABLE,
        schema=SCHEMA_FUEL,
        type_="unique",
    )
    op.create_unique_constraint(
        OLD_CONSTRAINT,
        TABLE,
        ["equipment_group_set_id", "station_id"],
        schema=SCHEMA_FUEL,
    )

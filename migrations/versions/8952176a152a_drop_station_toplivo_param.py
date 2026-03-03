"""drop gs_fue_station_toplivo_param table

Revision ID: 8952176a152a
Revises: r9s0t1u2v3w4
Create Date: 2026-02-26 14:04:03.613611

Удаляет устаревшую таблицу gs_fue_station_toplivo_param из схемы gs_fue.
"""
from alembic import op
from sqlalchemy import inspect
from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = '8952176a152a'
down_revision = 'r9s0t1u2v3w4'
branch_labels = None
depends_on = None

TABLE = "gs_fue_station_toplivo_param"


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if inspector.has_table(TABLE, schema=SCHEMA_FUEL):
        op.drop_table(TABLE, schema=SCHEMA_FUEL)


def downgrade():
    # Таблица удалена; восстановление не предусмотрено.
    pass

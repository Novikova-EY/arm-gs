"""remove_service_life_construction_commissioning_from_prospective_place_aes

Revision ID: u3v4w5x6y7z8
Revises: t2u3v4w5x6y7
Create Date: 2026-03-19

Удаляет поля service_life_years, construction_period_years, commissioning_year
из таблицы station_prospective_place_aes.
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402


revision = "u3v4w5x6y7z8"
down_revision = "t2u3v4w5x6y7"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE = "station_prospective_place_aes"


def upgrade():
    conn = op.get_bind()
    table = column_utils.station_prospective_place_aes_table_name(conn, SCHEMA_GEN)
    if table is None:
        return
    for col in ("service_life_years", "construction_period_years", "commissioning_year"):
        if column_utils.table_has_column(conn, SCHEMA_GEN, table, col):
            op.drop_column(table, col, schema=SCHEMA_GEN)


def downgrade():
    conn = op.get_bind()
    table = column_utils.station_prospective_place_aes_table_name(conn, SCHEMA_GEN)
    if table is None:
        return
    for col in ("service_life_years", "construction_period_years", "commissioning_year"):
        if not column_utils.table_has_column(conn, SCHEMA_GEN, table, col):
            op.add_column(table, sa.Column(col, sa.Integer(), nullable=True), schema=SCHEMA_GEN)

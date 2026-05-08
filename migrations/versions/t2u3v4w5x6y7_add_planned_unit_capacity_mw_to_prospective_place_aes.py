"""add_planned_unit_capacity_mw_to_prospective_place_aes

Revision ID: t2u3v4w5x6y7
Revises: s1t2u3v4w5x6
Create Date: 2026-03-19

Добавляет поле planned_unit_capacity_mw (Планируемая единичная мощность энергоблока, МВт)
в таблицу station_prospective_place_aes.
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402


revision = "t2u3v4w5x6y7"
down_revision = "s1t2u3v4w5x6"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE = "station_prospective_place_aes"


def upgrade():
    conn = op.get_bind()
    table = column_utils.station_prospective_place_aes_table_name(conn, SCHEMA_GEN)
    if table is not None and not column_utils.table_has_column(conn, SCHEMA_GEN, table, "planned_unit_capacity_mw"):
        op.add_column(
            table,
            sa.Column("planned_unit_capacity_mw", sa.Numeric(12, 4), nullable=True),
            schema=SCHEMA_GEN,
        )


def downgrade():
    conn = op.get_bind()
    table = column_utils.station_prospective_place_aes_table_name(conn, SCHEMA_GEN)
    if table is not None and column_utils.table_has_column(conn, SCHEMA_GEN, table, "planned_unit_capacity_mw"):
        op.drop_column(table, "planned_unit_capacity_mw", schema=SCHEMA_GEN)

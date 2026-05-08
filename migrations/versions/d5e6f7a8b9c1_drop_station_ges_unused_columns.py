"""drop_station_ges_unused_columns

Revision ID: d5e6f7a8b9c1
Revises: c4d5e6f7a8b0
Create Date: 2026-03-30

Удаление неиспользуемых полей из station_prospective_place_ges.
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402


revision = "d5e6f7a8b9c1"
down_revision = "c4d5e6f7a8b0"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE = "station_prospective_place_ges"

COLS = (
    "regional_subject_name",
    "planned_unit_capacity_mw",
    "selection_factor",
    "construction_period_years_minenergo_protocol",
)


def upgrade():
    conn = op.get_bind()
    table = column_utils.station_prospective_place_ges_table_name(conn, SCHEMA_GEN)
    if table is None:
        return
    for col in COLS:
        if column_utils.table_has_column(conn, SCHEMA_GEN, table, col):
            op.drop_column(table, col, schema=SCHEMA_GEN)


def downgrade():
    conn = op.get_bind()
    table = column_utils.station_prospective_place_ges_table_name(conn, SCHEMA_GEN)
    if table is None:
        return
    for col, coltype in (
        ("regional_subject_name", sa.String(length=255)),
        ("planned_unit_capacity_mw", sa.Integer()),
        ("selection_factor", sa.Text()),
        ("construction_period_years_minenergo_protocol", sa.Integer()),
    ):
        if not column_utils.table_has_column(conn, SCHEMA_GEN, table, col):
            op.add_column(table, sa.Column(col, coltype, nullable=True), schema=SCHEMA_GEN)

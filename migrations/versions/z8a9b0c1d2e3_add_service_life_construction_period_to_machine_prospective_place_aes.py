"""add_service_life_construction_period_to_machine_prospective_place_aes

Revision ID: z8a9b0c1d2e3
Revises: y7z8a9b0c1d2
Create Date: 2026-03-20

Добавляет поля service_life_years (срок эксплуатации АЭС, лет)
и construction_period_years (срок строительства АЭС, лет) в machine_prospective_place_aes.
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402


revision = "z8a9b0c1d2e3"
down_revision = "y7z8a9b0c1d2"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE = "machine_prospective_place_aes"


def upgrade():
    conn = op.get_bind()
    table = column_utils.machine_prospective_place_aes_table_name(conn, SCHEMA_GEN)
    if table is None:
        return
    for col in ("service_life_years", "construction_period_years"):
        if not column_utils.table_has_column(conn, SCHEMA_GEN, table, col):
            op.add_column(table, sa.Column(col, sa.Integer(), nullable=True), schema=SCHEMA_GEN)


def downgrade():
    conn = op.get_bind()
    table = column_utils.machine_prospective_place_aes_table_name(conn, SCHEMA_GEN)
    if table is None:
        return
    for col in ("service_life_years", "construction_period_years"):
        if column_utils.table_has_column(conn, SCHEMA_GEN, table, col):
            op.drop_column(table, col, schema=SCHEMA_GEN)

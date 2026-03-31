"""add_k_to_equipment_group_specific_fuel_consumption

Revision ID: h0i1j2k3l4m5
Revises: g9h0i1j2k3l4
Create Date: 2026-03-17

Добавляет колонку k (коэффициент экономии от теплофикации) в
gs_fue_equipment_group_specific_fuel_consumption для привязки K к году.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = 'h0i1j2k3l4m5'
down_revision = 'g9h0i1j2k3l4'
branch_labels = None
depends_on = None

SCHEMA = 'gs_fue'
TABLE = 'gs_fue_equipment_group_specific_fuel_consumption'
COLUMN = 'k'


def _column_exists(connection, schema, table, column):
    result = connection.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :column"
        ),
        {"schema": schema, "table": table, "column": column},
    )
    return result.fetchone() is not None


def upgrade():
    conn = op.get_bind()
    if _column_exists(conn, SCHEMA, TABLE, COLUMN):
        return
    op.add_column(
        TABLE,
        sa.Column(COLUMN, sa.Integer(), nullable=True),
        schema=SCHEMA,
    )


def downgrade():
    conn = op.get_bind()
    if not _column_exists(conn, SCHEMA, TABLE, COLUMN):
        return
    op.drop_column(TABLE, COLUMN, schema=SCHEMA)

"""remove_k_from_equipment_group

Revision ID: i1j2k3l4m5n6
Revises: h0i1j2k3l4m5
Create Date: 2026-03-17

Удаляет колонку k из gs_fue_equipment_groups.
K хранится только в EquipmentGroupSpecificFuelConsumption (consumption.k) с привязкой к году.
"""
from alembic import op
from sqlalchemy import text


revision = 'i1j2k3l4m5n6'
down_revision = 'h0i1j2k3l4m5'
branch_labels = None
depends_on = None

SCHEMA = 'gs_fue'
TABLE = 'gs_fue_equipment_groups'
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
    if not _column_exists(conn, SCHEMA, TABLE, COLUMN):
        return
    op.drop_column(TABLE, COLUMN, schema=SCHEMA)


def downgrade():
    import sqlalchemy as sa
    conn = op.get_bind()
    if _column_exists(conn, SCHEMA, TABLE, COLUMN):
        return
    op.add_column(
        TABLE,
        sa.Column(COLUMN, sa.Integer(), nullable=True),
        schema=SCHEMA,
    )

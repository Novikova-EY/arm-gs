"""add_calc_fields_to_equipment_group_specific_fuel_consumption

Revision ID: e6f7a8b9c0d1
Revises: a1b2c3d4e5f6
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'e6f7a8b9c0d1'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None

SCHEMA = 'gs_fue'
TABLE = 'gs_fue_equipment_group_specific_fuel_consumption'
COLUMNS = [
    ('y_calc', sa.Numeric(precision=20, scale=6)),
    ('btp_calc', sa.Numeric(precision=20, scale=6)),
    ('sntp_calc', sa.Numeric(precision=20, scale=6)),
    ('bk_calc', sa.Numeric(precision=20, scale=6)),
    ('snk_calc', sa.Numeric(precision=20, scale=6)),
]


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
    for col_name, col_type in COLUMNS:
        if _column_exists(conn, SCHEMA, TABLE, col_name):
            continue
        op.add_column(
            TABLE,
            sa.Column(col_name, col_type, nullable=True),
            schema=SCHEMA,
        )


def downgrade():
    conn = op.get_bind()
    for col_name, _ in reversed(COLUMNS):
        if not _column_exists(conn, SCHEMA, TABLE, col_name):
            continue
        op.drop_column(TABLE, col_name, schema=SCHEMA)

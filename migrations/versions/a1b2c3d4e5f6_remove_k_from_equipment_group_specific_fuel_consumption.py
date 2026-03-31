"""remove_k_from_equipment_group_specific_fuel_consumption

Revision ID: a1b2c3d4e5f6
Revises: c7288ef7ccbb
Create Date: 2026-03-13

"""
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'c7288ef7ccbb'
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
        sa.Column(COLUMN, sa.Numeric(precision=20, scale=6), nullable=True),
        schema=SCHEMA,
    )

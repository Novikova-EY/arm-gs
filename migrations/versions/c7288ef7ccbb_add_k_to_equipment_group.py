"""add_k_to_equipment_group

Revision ID: c7288ef7ccbb
Revises: d4e5f6a7b8c9
Create Date: 2026-03-13 11:40:56.058307

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'c7288ef7ccbb'
down_revision = 'd4e5f6a7b8c9'
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
    if _column_exists(conn, SCHEMA, TABLE, COLUMN):
        return
    op.add_column(
        TABLE,
        sa.Column(COLUMN, sa.Numeric(precision=20, scale=6), nullable=True),
        schema=SCHEMA,
    )


def downgrade():
    conn = op.get_bind()
    if not _column_exists(conn, SCHEMA, TABLE, COLUMN):
        return
    op.drop_column(TABLE, COLUMN, schema=SCHEMA)

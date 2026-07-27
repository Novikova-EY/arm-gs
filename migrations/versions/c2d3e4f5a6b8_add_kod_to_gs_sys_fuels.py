"""add kod to gs_sys_fuels

Revision ID: c2d3e4f5a6b8
Revises: a9b0c1d2e3f4
Create Date: 2026-07-24 10:05:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "c2d3e4f5a6b8"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None

SCHEMA = "gs_sys"
TABLE = "gs_sys_fuels"
COLUMN = "kod"
INDEX = "ix_gs_sys_fuels_kod"


def _column_exists(connection, table: str, column: str) -> bool:
    result = connection.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :column"
        ),
        {"schema": SCHEMA, "table": table, "column": column},
    )
    return result.fetchone() is not None


def _index_exists(connection, index_name: str) -> bool:
    result = connection.execute(
        text(
            "SELECT 1 FROM pg_indexes "
            "WHERE schemaname = :schema AND indexname = :index_name"
        ),
        {"schema": SCHEMA, "index_name": index_name},
    )
    return result.fetchone() is not None


def upgrade():
    conn = op.get_bind()

    if not _column_exists(conn, TABLE, COLUMN):
        op.add_column(
            TABLE,
            sa.Column(COLUMN, sa.Integer(), nullable=True),
            schema=SCHEMA,
        )

    if not _index_exists(conn, INDEX):
        op.create_index(INDEX, TABLE, [COLUMN], unique=False, schema=SCHEMA)


def downgrade():
    conn = op.get_bind()

    if _index_exists(conn, INDEX):
        op.drop_index(INDEX, table_name=TABLE, schema=SCHEMA)

    if _column_exists(conn, TABLE, COLUMN):
        op.drop_column(TABLE, COLUMN, schema=SCHEMA)

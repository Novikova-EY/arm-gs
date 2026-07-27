"""fuel parent_id and drop fuel_categories

Revision ID: a9b0c1d2e3f4
Revises: x9y0z1a2b3c4
Create Date: 2026-07-24 09:50:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "a9b0c1d2e3f4"
down_revision = "x9y0z1a2b3c4"
branch_labels = None
depends_on = None

SCHEMA = "gs_sys"
FUELS_TABLE = "gs_sys_fuels"
CATEGORIES_TABLE = "gs_sys_fuel_categories"
PARENT_COLUMN = "parent_id"
PARENT_INDEX = "ix_gs_sys_fuels_parent_id"
PARENT_FK = "fk_gs_sys_fuels_parent_id"


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


def _constraint_exists(connection, table: str, constraint_name: str) -> bool:
    result = connection.execute(
        text(
            "SELECT 1 "
            "FROM information_schema.table_constraints "
            "WHERE table_schema = :schema AND table_name = :table "
            "AND constraint_name = :constraint_name"
        ),
        {"schema": SCHEMA, "table": table, "constraint_name": constraint_name},
    )
    return result.fetchone() is not None


def _table_exists(connection, table: str) -> bool:
    result = connection.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :table"
        ),
        {"schema": SCHEMA, "table": table},
    )
    return result.fetchone() is not None


def upgrade():
    conn = op.get_bind()

    if not _column_exists(conn, FUELS_TABLE, PARENT_COLUMN):
        op.add_column(
            FUELS_TABLE,
            sa.Column(PARENT_COLUMN, sa.Integer(), nullable=True),
            schema=SCHEMA,
        )

    if not _index_exists(conn, PARENT_INDEX):
        op.create_index(
            PARENT_INDEX,
            FUELS_TABLE,
            [PARENT_COLUMN],
            unique=False,
            schema=SCHEMA,
        )

    if not _constraint_exists(conn, FUELS_TABLE, PARENT_FK):
        op.create_foreign_key(
            PARENT_FK,
            FUELS_TABLE,
            FUELS_TABLE,
            [PARENT_COLUMN],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA,
            ondelete="SET NULL",
        )

    if _table_exists(conn, CATEGORIES_TABLE):
        op.drop_table(CATEGORIES_TABLE, schema=SCHEMA)


def downgrade():
    conn = op.get_bind()

    if not _table_exists(conn, CATEGORIES_TABLE):
        op.create_table(
            CATEGORIES_TABLE,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("database_version_id", sa.Integer(), nullable=True),
            sa.Column("created_by", sa.String(length=80), nullable=True),
            sa.Column("modified_by", sa.String(length=80), nullable=True),
            sa.Column("version", sa.Integer(), nullable=True),
            sa.Column("ref_uuid", sa.String(length=36), nullable=True),
            schema=SCHEMA,
        )

    if _constraint_exists(conn, FUELS_TABLE, PARENT_FK):
        op.drop_constraint(PARENT_FK, FUELS_TABLE, schema=SCHEMA, type_="foreignkey")

    if _index_exists(conn, PARENT_INDEX):
        op.drop_index(PARENT_INDEX, table_name=FUELS_TABLE, schema=SCHEMA)

    if _column_exists(conn, FUELS_TABLE, PARENT_COLUMN):
        op.drop_column(FUELS_TABLE, PARENT_COLUMN, schema=SCHEMA)

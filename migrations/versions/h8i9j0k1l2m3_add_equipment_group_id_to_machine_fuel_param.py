"""add_equipment_group_id_to_machine_fuel_param

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-04-08 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "h8i9j0k1l2m3"
down_revision = "g7h8i9j0k1l2"
branch_labels = None
depends_on = None

SCHEMA = "gs_fue"
TABLE = "gs_fue_machine_fuel_param"
COLUMN = "equipment_group_id"
INDEX = "ix_gs_fue_machine_fuel_param_equipment_group_id"
FK = "fk_gs_fue_machine_fuel_param_equipment_group_id"


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
            "WHERE table_schema = :schema AND table_name = :table AND constraint_name = :constraint_name"
        ),
        {"schema": SCHEMA, "table": table, "constraint_name": constraint_name},
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

    if not _constraint_exists(conn, TABLE, FK):
        op.create_foreign_key(
            FK,
            TABLE,
            "gs_fue_equipment_groups",
            [COLUMN],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA,
            ondelete="SET NULL",
        )

    if not _index_exists(conn, INDEX):
        op.create_index(INDEX, TABLE, [COLUMN], unique=False, schema=SCHEMA)


def downgrade():
    conn = op.get_bind()

    if _index_exists(conn, INDEX):
        op.drop_index(INDEX, table_name=TABLE, schema=SCHEMA)

    if _constraint_exists(conn, TABLE, FK):
        op.drop_constraint(FK, TABLE, schema=SCHEMA, type_="foreignkey")

    if _column_exists(conn, TABLE, COLUMN):
        op.drop_column(TABLE, COLUMN, schema=SCHEMA)

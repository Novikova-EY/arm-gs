"""add_pgu_machine_names_table

Revision ID: n6o7p8q9r0s1
Revises: m5n6o7p8q9r0
Create Date: 2026-03-18

Создает таблицу pgu_machine_names по аналогии с machine_names (названия компонентов ПГУ по годам).
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils


revision = "n6o7p8q9r0s1"
down_revision = "m5n6o7p8q9r0"
branch_labels = None
depends_on = None

SCHEMA = "gs_gen"
SCHEMA_REF = "gs_sys"
TABLE = "pgu_machine_names"


def upgrade():
    conn = op.get_bind()
    if column_utils.table_exists(conn, SCHEMA, TABLE):
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("year_number", sa.Integer(), nullable=True),
        sa.Column("id_pgu_machine", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_pgu_machine_name_id_pgu_machine",
        TABLE,
        ["id_pgu_machine"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_pgu_machine_name_year_number",
        TABLE,
        ["year_number"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_pgu_machine_names_pgu_machine_year",
        TABLE,
        ["id_pgu_machine", "year_number"],
        schema=SCHEMA,
    )
    # FK на pgu_machines
    op.create_foreign_key(
        None,
        TABLE,
        "pgu_machines",
        ["id_pgu_machine"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="RESTRICT",
    )
    # FK на gs_database_versions
    op.create_foreign_key(
        None,
        TABLE,
        "gs_database_versions",
        ["database_version_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA_REF,
        ondelete="SET NULL",
    )
    # Не создаем FK на gs_years.number (по аналогии с machine_names)


def downgrade():
    op.drop_constraint(None, TABLE, schema=SCHEMA, type_="foreignkey")
    op.drop_constraint(None, TABLE, schema=SCHEMA, type_="foreignkey")
    op.drop_index("ix_pgu_machine_names_pgu_machine_year", table_name=TABLE, schema=SCHEMA)
    op.drop_index("ix_pgu_machine_name_year_number", table_name=TABLE, schema=SCHEMA)
    op.drop_index("ix_pgu_machine_name_id_pgu_machine", table_name=TABLE, schema=SCHEMA)
    op.drop_table(TABLE, schema=SCHEMA)

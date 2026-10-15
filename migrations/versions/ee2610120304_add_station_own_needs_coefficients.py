# -*- coding: utf-8 -*-
"""Коэффициенты собственных нужд электростанций ГЭС/ГАЭС.

Revision ID: ee2610120304
Revises: ee2610120303
Create Date: 2026-10-13
"""
import os
import sys

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "ee2610120304"
down_revision = "ee2610120303"
branch_labels = None
depends_on = None

SCHEMA = "gs_bem"
SCHEMA_GENERATION = "gs_gen"
SCHEMA_REFDATA = "gs_sys"
TABLE = "gs_bem_ee_balance_station_own_needs_coefficients"


def _quoted(schema, table):
    return f'"{schema}"."{table}"'


def upgrade():
    conn = op.get_bind()
    stations_table = column_utils.gs_gen_stations_table_name(conn, SCHEMA_GENERATION)
    versions_table = column_utils.database_versions_physical_table_name(conn, SCHEMA_REFDATA)

    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_station", sa.Integer(), nullable=False),
        sa.Column("station_type_key", sa.String(length=8), nullable=False),
        sa.Column("coefficient", sa.Numeric(25, 16), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_ee_bal_own_needs_station", TABLE, ["id_station"], schema=SCHEMA
    )
    op.create_index(
        "ix_ee_bal_own_needs_type", TABLE, ["station_type_key"], schema=SCHEMA
    )
    op.create_index(
        "ix_ee_bal_own_needs_dbver", TABLE, ["database_version_id"], schema=SCHEMA
    )
    op.execute(
        text(
            f"CREATE UNIQUE INDEX uq_ee_bal_own_needs_station_type_ver "
            f"ON {_quoted(SCHEMA, TABLE)} "
            "(id_station, station_type_key, COALESCE(database_version_id, -1))"
        )
    )

    if stations_table:
        op.create_foreign_key(
            "fk_ee_bal_own_needs_station",
            TABLE,
            stations_table,
            ["id_station"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA_GENERATION,
            ondelete="RESTRICT",
        )
    if versions_table:
        op.create_foreign_key(
            "fk_ee_bal_own_needs_db_version",
            TABLE,
            versions_table,
            ["database_version_id"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA_REFDATA,
            ondelete="SET NULL",
        )


def downgrade():
    op.drop_table(TABLE, schema=SCHEMA)

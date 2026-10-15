# -*- coding: utf-8 -*-
"""КПД электростанций СНЭЭ по версиям БД.

Revision ID: ee2610120306
Revises: ee2610120305
Create Date: 2026-10-14
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

revision = "ee2610120306"
down_revision = "ee2610120305"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REF = "gs_sys"
TABLE = "gs_gen_station_snee_efficiencies"
UNIQUE_INDEX = "uq_station_snee_efficiency_station_ver"


def upgrade():
    conn = op.get_bind()
    ref_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REF)
    if ref_versions is None:
        raise RuntimeError(f"Не найдена таблица версий БД в {SCHEMA_REF}.")
    stations_table = column_utils.gs_gen_stations_table_name(conn, SCHEMA_GEN)
    if stations_table is None:
        raise RuntimeError(f"Не найдена таблица станций в {SCHEMA_GEN}.")

    if not column_utils.table_exists(conn, SCHEMA_GEN, TABLE):
        op.create_table(
            TABLE,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("id_station", sa.Integer(), nullable=False),
            sa.Column("database_version_id", sa.Integer(), nullable=True),
            sa.Column("efficiency_percent", sa.Numeric(25, 16), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("created_by", sa.String(length=255), nullable=True),
            sa.Column("modified_by", sa.String(length=255), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA_GEN,
        )
    if not column_utils.index_exists(conn, SCHEMA_GEN, "ix_station_snee_efficiency_id_station"):
        op.create_index("ix_station_snee_efficiency_id_station", TABLE, ["id_station"], schema=SCHEMA_GEN)
    if not column_utils.index_exists(conn, SCHEMA_GEN, "ix_station_snee_efficiency_database_version_id"):
        op.create_index("ix_station_snee_efficiency_database_version_id", TABLE, ["database_version_id"], schema=SCHEMA_GEN)
    if not column_utils.index_exists(conn, SCHEMA_GEN, UNIQUE_INDEX):
        op.execute(
            text(
                f'CREATE UNIQUE INDEX "{UNIQUE_INDEX}" '
                f'ON "{SCHEMA_GEN}"."{TABLE}" '
                '(id_station, COALESCE(database_version_id, -1))'
            )
        )
    if not column_utils.constraint_exists(conn, SCHEMA_GEN, "fk_station_snee_efficiency_station"):
        op.create_foreign_key(
            "fk_station_snee_efficiency_station", TABLE, stations_table,
            ["id_station"], ["id"], source_schema=SCHEMA_GEN,
            referent_schema=SCHEMA_GEN, ondelete="RESTRICT",
        )
    if not column_utils.constraint_exists(conn, SCHEMA_GEN, "fk_station_snee_efficiency_database_version"):
        op.create_foreign_key(
            "fk_station_snee_efficiency_database_version", TABLE, ref_versions,
            ["database_version_id"], ["id"], source_schema=SCHEMA_GEN,
            referent_schema=SCHEMA_REF, ondelete="SET NULL",
        )


def downgrade():
    conn = op.get_bind()
    if not column_utils.table_exists(conn, SCHEMA_GEN, TABLE):
        return
    for constraint_name in (
        "fk_station_snee_efficiency_database_version",
        "fk_station_snee_efficiency_station",
    ):
        if column_utils.constraint_exists(conn, SCHEMA_GEN, constraint_name):
            op.drop_constraint(constraint_name, TABLE, schema=SCHEMA_GEN, type_="foreignkey")
    if column_utils.index_exists(conn, SCHEMA_GEN, UNIQUE_INDEX):
        op.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA_GEN}"."{UNIQUE_INDEX}"'))
    for index_name in (
        "ix_station_snee_efficiency_database_version_id",
        "ix_station_snee_efficiency_id_station",
    ):
        if column_utils.index_exists(conn, SCHEMA_GEN, index_name):
            op.drop_index(index_name, table_name=TABLE, schema=SCHEMA_GEN)
    op.drop_table(TABLE, schema=SCHEMA_GEN)

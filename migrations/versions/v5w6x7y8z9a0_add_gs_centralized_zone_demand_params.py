# -*- coding: utf-8 -*-
"""Таблица gs_centralized_zone_demand_params — параметры нагрузки для Централизованной зоны (без FK).

Revision ID: v5w6x7y8z9a0
Revises: 9baedd89c064
Create Date: 2026-04-10
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


revision = "v5w6x7y8z9a0"
down_revision = "9baedd89c064"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
SCHEMA_REFDATA = "gs_sys"
TABLE = "gs_centralized_zone_demand_params"


def _schema_exists(connection, schema: str) -> bool:
    r = connection.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema"),
        {"schema": schema},
    )
    return r.fetchone() is not None


def _ensure_indexes(connection, table_name: str) -> None:
    if not column_utils.index_exists(connection, SCHEMA_PD, "ix_gs_centralized_zone_dp_year"):
        op.create_index(
            "ix_gs_centralized_zone_dp_year",
            table_name,
            ["year_number"],
            unique=False,
            schema=SCHEMA_PD,
        )
    if not column_utils.index_exists(connection, SCHEMA_PD, "ix_gs_centralized_zone_dp_dbver"):
        op.create_index(
            "ix_gs_centralized_zone_dp_dbver",
            table_name,
            ["database_version_id"],
            unique=False,
            schema=SCHEMA_PD,
        )
    op.execute(
        sa.text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_centralized_zone_dp_hist
            ON "{SCHEMA_PD}"."{table_name}" (
                COALESCE(database_version_id, 0)
            )
            WHERE is_historical_maximum = true
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_centralized_zone_dp_year
            ON "{SCHEMA_PD}"."{table_name}" (
                year_number,
                COALESCE(database_version_id, 0)
            )
            WHERE is_historical_maximum = false
            """
        )
    )


def upgrade():
    conn = op.get_bind()
    ref_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REFDATA)
    if ref_versions is None:
        raise RuntimeError(
            f"Не найдена таблица версий БД в {SCHEMA_REFDATA} "
            "(gs_sys_database_versions или gs_database_versions как BASE TABLE)"
        )
    if not _schema_exists(conn, SCHEMA_PD):
        op.execute(sa.text(f'CREATE SCHEMA "{SCHEMA_PD}"'))

    existing = column_utils.gs_pd_demand_params_physical_table_name(conn, SCHEMA_PD, TABLE)
    if existing is None:
        op.create_table(
            TABLE,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("is_historical_maximum", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("year_number", sa.Integer(), nullable=True),
            sa.Column("max_power_consumption_mw", sa.Numeric(precision=25, scale=16), nullable=True),
            sa.Column("peak_datetime_msk", sa.DateTime(timezone=True), nullable=True),
            sa.Column("avg_daily_air_temp_c", sa.Numeric(precision=10, scale=2), nullable=True),
            sa.Column("combined_on_oes", sa.Numeric(precision=25, scale=16), nullable=True),
            sa.Column("combined_on_ees", sa.Numeric(precision=25, scale=16), nullable=True),
            sa.Column("combined_on_es", sa.Numeric(precision=25, scale=16), nullable=True),
            sa.Column("created_by", sa.String(length=255), nullable=True),
            sa.Column("modified_by", sa.String(length=255), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("database_version_id", sa.Integer(), nullable=True),
            sa.CheckConstraint(
                "(is_historical_maximum = true AND year_number IS NULL) OR "
                "(is_historical_maximum = false AND year_number IS NOT NULL)",
                name=f"ck_{TABLE}_year_vs_hist",
            ),
            sa.ForeignKeyConstraint(
                ["database_version_id"],
                [f"{SCHEMA_REFDATA}.{ref_versions}.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA_PD,
        )
        existing = TABLE

    _ensure_indexes(conn, existing)


def downgrade():
    conn = op.get_bind()
    pd = "gs_pd_" + TABLE[len("gs_") :]
    for tbl in (pd, TABLE):
        if column_utils.table_exists(conn, SCHEMA_PD, tbl):
            op.execute(sa.text(f'DROP TABLE IF EXISTS "{SCHEMA_PD}"."{tbl}" CASCADE'))

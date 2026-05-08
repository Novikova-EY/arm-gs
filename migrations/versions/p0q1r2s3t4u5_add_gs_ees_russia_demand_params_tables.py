# -*- coding: utf-8 -*-
"""Таблицы gs_ees_russia_demand_params и gs_ees_russia_with_nt_demand_params.

Revision ID: p0q1r2s3t4u5
Revises: n9o0p1q2r3s4
Create Date: 2026-04-09
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


revision = "p0q1r2s3t4u5"
down_revision = "n9o0p1q2r3s4"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
SCHEMA_REFDATA = "gs_sys"

_EES_RUSSIA_SPECS = (
    (
        "gs_ees_russia_demand_params",
        "ix_gs_ees_ru_dp_year",
        "ix_gs_ees_ru_dp_dbver",
        "uq_ees_russia_dp_hist",
        "uq_ees_russia_dp_year",
    ),
    (
        "gs_ees_russia_with_nt_demand_params",
        "ix_gs_ees_ru_nt_dp_year",
        "ix_gs_ees_ru_nt_dp_dbver",
        "uq_ees_russia_nt_dp_hist",
        "uq_ees_russia_nt_dp_year",
    ),
)


def _schema_exists(connection, schema: str) -> bool:
    r = connection.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema"),
        {"schema": schema},
    )
    return r.fetchone() is not None


def _create_ees_russia_table_only(table: str, ref_versions: str) -> None:
    op.create_table(
        table,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("is_historical_maximum", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("year_number", sa.Integer(), nullable=True),
        sa.Column("max_power_consumption_mw", sa.Numeric(precision=25, scale=16), nullable=True),
        sa.Column("peak_datetime_msk", sa.DateTime(timezone=True), nullable=True),
        sa.Column("avg_daily_air_temp_c", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("combined_on_oes", sa.Numeric(precision=25, scale=16), nullable=True),
        sa.Column("combined_on_ees", sa.Numeric(precision=25, scale=16), nullable=True),
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
            name=f"ck_{table}_year_vs_hist",
        ),
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            [f"{SCHEMA_REFDATA}.{ref_versions}.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA_PD,
    )


def _ensure_ees_russia_indexes(
    conn,
    physical: str,
    ix_year: str,
    ix_dbver: str,
    uq_hist: str,
    uq_year: str,
) -> None:
    if not column_utils.index_exists(conn, SCHEMA_PD, ix_year):
        op.create_index(ix_year, physical, ["year_number"], unique=False, schema=SCHEMA_PD)
    if not column_utils.index_exists(conn, SCHEMA_PD, ix_dbver):
        op.create_index(ix_dbver, physical, ["database_version_id"], unique=False, schema=SCHEMA_PD)
    op.execute(
        sa.text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS {uq_hist}
            ON "{SCHEMA_PD}"."{physical}" (
                COALESCE(database_version_id, 0)
            )
            WHERE is_historical_maximum = true
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS {uq_year}
            ON "{SCHEMA_PD}"."{physical}" (
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

    for legacy, ix_y, ix_db, uq_h, uq_y in _EES_RUSSIA_SPECS:
        physical = column_utils.gs_pd_demand_params_physical_table_name(conn, SCHEMA_PD, legacy)
        if physical is None:
            _create_ees_russia_table_only(legacy, ref_versions)
            physical = legacy
        _ensure_ees_russia_indexes(conn, physical, ix_y, ix_db, uq_h, uq_y)


def downgrade():
    conn = op.get_bind()
    for legacy, *_ in reversed(_EES_RUSSIA_SPECS):
        pd_tbl = "gs_pd_" + legacy[len("gs_") :]
        for tbl in (pd_tbl, legacy):
            if column_utils.table_exists(conn, SCHEMA_PD, tbl):
                op.execute(sa.text(f'DROP TABLE IF EXISTS "{SCHEMA_PD}"."{tbl}" CASCADE'))

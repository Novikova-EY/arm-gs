# -*- coding: utf-8 -*-
"""Таблица gs_russia_federation_demand_params — параметры нагрузки для РФ в целом (без FK на справочник).

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
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


revision = "k1l2m3n4o5p6"
down_revision = "j0k1l2m3n4o5"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
SCHEMA_REFDATA = "gs_sys"
TABLE = "gs_russia_federation_demand_params"
TABLE_PD_PREFIX = "gs_pd_russia_federation_demand_params"


def _schema_exists(connection, schema: str) -> bool:
    r = connection.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema"),
        {"schema": schema},
    )
    return r.fetchone() is not None


def _remove_duplicate_rows(connection, table_name: str) -> None:
    """Удаляет дубликаты перед частичными UNIQUE INDEX (данные могли появиться до индексов)."""
    fq = SCHEMA_PD.replace('"', '""')
    tbl = table_name.replace('"', '""')
    connection.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY COALESCE(database_version_id, 0)
                        ORDER BY id DESC
                    ) AS rn
                FROM "{fq}"."{tbl}"
                WHERE is_historical_maximum = true
            )
            DELETE FROM "{fq}"."{tbl}" t
            USING ranked r
            WHERE t.id = r.id AND r.rn > 1
            """
        )
    )
    connection.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY year_number, COALESCE(database_version_id, 0)
                        ORDER BY id DESC
                    ) AS rn
                FROM "{fq}"."{tbl}"
                WHERE is_historical_maximum = false
            )
            DELETE FROM "{fq}"."{tbl}" t
            USING ranked r
            WHERE t.id = r.id AND r.rn > 1
            """
        )
    )


def _ensure_indexes(connection, table_name: str) -> None:
    _remove_duplicate_rows(connection, table_name)
    ix_year = f"ix_{TABLE}_year_number"
    if not column_utils.index_exists(connection, SCHEMA_PD, ix_year):
        op.create_index(ix_year, table_name, ["year_number"], unique=False, schema=SCHEMA_PD)
    ix_ver = f"ix_{TABLE}_database_version_id"
    if not column_utils.index_exists(connection, SCHEMA_PD, ix_ver):
        op.create_index(ix_ver, table_name, ["database_version_id"], unique=False, schema=SCHEMA_PD)
    op.execute(
        sa.text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_russia_federation_demand_params_hist
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
            CREATE UNIQUE INDEX IF NOT EXISTS uq_russia_federation_demand_params_year
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
    for tbl in (TABLE_PD_PREFIX, TABLE):
        if column_utils.table_exists(conn, SCHEMA_PD, tbl):
            op.execute(sa.text(f'DROP TABLE IF EXISTS "{SCHEMA_PD}"."{tbl}" CASCADE'))

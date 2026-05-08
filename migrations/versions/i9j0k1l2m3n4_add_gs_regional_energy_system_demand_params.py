# -*- coding: utf-8 -*-
"""Схема gs_pd и таблица gs_regional_energy_system_demand_params (параметры нагрузки по РЭС).

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
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


revision = "i9j0k1l2m3n4"
down_revision = "h8i9j0k1l2m3"
branch_labels = None
depends_on = None

SCHEMA = "gs_pd"
TABLE = "gs_regional_energy_system_demand_params"
SCHEMA_REFDATA = "gs_sys"


def _schema_exists(connection) -> bool:
    r = connection.execute(
        text(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema"
        ),
        {"schema": SCHEMA},
    )
    return r.fetchone() is not None


def upgrade():
    conn = op.get_bind()
    ref_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REFDATA)
    table_res = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_regional_energy_systems")
    if ref_versions is None:
        raise RuntimeError(
            f"Не найдена таблица версий БД в {SCHEMA_REFDATA} "
            "(gs_sys_database_versions или gs_database_versions как BASE TABLE)"
        )
    if table_res is None:
        return
    if not _schema_exists(conn):
        op.execute(sa.text(f'CREATE SCHEMA "{SCHEMA}"'))

    physical = column_utils.gs_pd_demand_params_physical_table_name(conn, SCHEMA, TABLE)
    if physical is None:
        op.create_table(
            TABLE,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("id_regional_energy_system", sa.Integer(), nullable=False),
            sa.Column(
                "is_historical_maximum",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            ),
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
                name="ck_gs_res_demand_params_year_vs_hist",
            ),
            sa.ForeignKeyConstraint(
                ["id_regional_energy_system"],
                [f"{SCHEMA_REFDATA}.{table_res}.id"],
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["database_version_id"],
                [f"{SCHEMA_REFDATA}.{ref_versions}.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA,
        )
        physical = TABLE

    # Имена индексов ≤ 63 символов (ограничение PostgreSQL)
    if not column_utils.index_exists(conn, SCHEMA, "ix_gs_res_dparam_id_res"):
        op.create_index(
            "ix_gs_res_dparam_id_res",
            physical,
            ["id_regional_energy_system"],
            unique=False,
            schema=SCHEMA,
        )
    if not column_utils.index_exists(conn, SCHEMA, "ix_gs_res_dparam_year"):
        op.create_index(
            "ix_gs_res_dparam_year",
            physical,
            ["year_number"],
            unique=False,
            schema=SCHEMA,
        )
    if not column_utils.index_exists(conn, SCHEMA, "ix_gs_res_dparam_dbver"):
        op.create_index(
            "ix_gs_res_dparam_dbver",
            physical,
            ["database_version_id"],
            unique=False,
            schema=SCHEMA,
        )

    # Уникальность с учётом NULL database_version_id (как одна версия для «пустой» версии)
    op.execute(
        sa.text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_res_demand_params_hist
            ON "{SCHEMA}"."{physical}" (
                id_regional_energy_system,
                COALESCE(database_version_id, 0)
            )
            WHERE is_historical_maximum = true
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_res_demand_params_year
            ON "{SCHEMA}"."{physical}" (
                id_regional_energy_system,
                year_number,
                COALESCE(database_version_id, 0)
            )
            WHERE is_historical_maximum = false
            """
        )
    )


def downgrade():
    conn = op.get_bind()
    pd = "gs_pd_" + TABLE[len("gs_") :]
    for tbl in (pd, TABLE):
        if column_utils.table_exists(conn, SCHEMA, tbl):
            op.execute(sa.text(f'DROP TABLE IF EXISTS "{SCHEMA}"."{tbl}" CASCADE'))
    # схему gs_pd не удаляем — в ней могут появиться другие таблицы

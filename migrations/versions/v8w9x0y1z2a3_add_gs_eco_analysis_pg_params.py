# -*- coding: utf-8 -*-
"""Параметры анализа ПГ (копия/правка отчетных данных ГИС ТЭК).

Revision ID: v8w9x0y1z2a3
Revises: u7v8w9x0y1z2
Create Date: 2026-09-07
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

revision = "v8w9x0y1z2a3"
down_revision = "u7v8w9x0y1z2"
branch_labels = None
depends_on = None

SCHEMA_ECO = "gs_eco"
SCHEMA_REFDATA = "gs_sys"
TABLE = "gs_eco_analysis_pg_params"

_COLUMN_COMMENTS = {
    "id": "Уникальный идентификатор записи",
    "sheet_slug": "Страница анализа: pg-vse или pg-bez-kot",
    "station_numb": "Код группы оборудования (numb1120), связь с отчетными ПГ",
    "year_number": "Год (связь с gs_sys.gs_sys_years по number и database_version_id)",
    "gas_consumption_tce": "Израсходовано газа, тут (GAZ_ek ← Расход газа)",
    "co2_from_gas_t": "Выброшено ПГ от газа, т (CO2_gaz ← Выбросы СО2 от сжигания газа)",
    "oil_fuel_consumption_tce": "Израсходовано мазута, тут (MAZUT_ek ← Расход нефтетоплива)",
    "co2_from_oil_fuel_t": (
        "Выброшено ПГ от мазута, т (CO2_mazut ← Выбросы СО2 от сжигания нефтетоплива)"
    ),
    "solid_fuel_consumption_tce": (
        "Израсходовано твердого топлива, тут (TvTopl_ek ← Расход твердого топлива)"
    ),
    "co2_from_solid_fuel_t": (
        "Выброшено ПГ от твердого топлива, т "
        "(CO2_ugol ← Выбросы СО2 от сжигания твердого топлива)"
    ),
    "note": "Примечание",
    "created_by": "Пользователь, создавший запись",
    "modified_by": "Пользователь, последним изменивший запись",
    "created_at": "Дата и время создания записи",
    "updated_at": "Дата и время последнего изменения записи",
    "database_version_id": "Версия базы данных (FK -> gs_sys.gs_database_versions)",
}


def _schema_exists(connection, schema: str) -> bool:
    r = connection.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema"),
        {"schema": schema},
    )
    return r.fetchone() is not None


def _comment_on_table(conn, schema: str, table: str, comment: str) -> None:
    conn.execute(
        text(f'COMMENT ON TABLE "{schema}"."{table}" IS :comment'),
        {"comment": comment},
    )


def _comment_on_column(conn, schema: str, table: str, column: str, comment: str) -> None:
    conn.execute(
        text(f'COMMENT ON COLUMN "{schema}"."{table}"."{column}" IS :comment'),
        {"comment": comment},
    )


def upgrade():
    conn = op.get_bind()
    ref_db_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REFDATA)
    if ref_db_versions is None:
        raise RuntimeError(f"Не найдена таблица версий БД в {SCHEMA_REFDATA}")
    years = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_years")
    if years is None:
        raise RuntimeError(f"Не найдена таблица годов в {SCHEMA_REFDATA}")
    if not _schema_exists(conn, SCHEMA_ECO):
        op.execute(sa.text(f'CREATE SCHEMA "{SCHEMA_ECO}"'))

    if column_utils.table_exists(conn, SCHEMA_ECO, TABLE):
        return

    numeric = sa.Numeric(36, 16)
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sheet_slug", sa.String(length=40), nullable=False),
        sa.Column("station_numb", sa.Integer(), nullable=False),
        sa.Column("year_number", sa.Integer(), nullable=False),
        sa.Column("gas_consumption_tce", numeric, nullable=True),
        sa.Column("co2_from_gas_t", numeric, nullable=True),
        sa.Column("oil_fuel_consumption_tce", numeric, nullable=True),
        sa.Column("co2_from_oil_fuel_t", numeric, nullable=True),
        sa.Column("solid_fuel_consumption_tce", numeric, nullable=True),
        sa.Column("co2_from_solid_fuel_t", numeric, nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["year_number", "database_version_id"],
            [
                f"{SCHEMA_REFDATA}.gs_sys_years.number",
                f"{SCHEMA_REFDATA}.gs_sys_years.database_version_id",
            ],
            ondelete="RESTRICT",
            name="fk_eco_analysis_pg_year_ver",
        ),
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            [f"{SCHEMA_REFDATA}.{ref_db_versions}.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "sheet_slug",
            "station_numb",
            "year_number",
            "database_version_id",
            name="uq_eco_analysis_pg_sheet_numb_year_ver",
        ),
        schema=SCHEMA_ECO,
    )
    op.create_index(
        f"ix_{TABLE}_sheet_slug",
        TABLE,
        ["sheet_slug"],
        unique=False,
        schema=SCHEMA_ECO,
    )
    op.create_index(
        f"ix_{TABLE}_station_numb",
        TABLE,
        ["station_numb"],
        unique=False,
        schema=SCHEMA_ECO,
    )
    op.create_index(
        f"ix_{TABLE}_year_number",
        TABLE,
        ["year_number"],
        unique=False,
        schema=SCHEMA_ECO,
    )
    op.create_index(
        f"ix_{TABLE}_database_version_id",
        TABLE,
        ["database_version_id"],
        unique=False,
        schema=SCHEMA_ECO,
    )

    _comment_on_table(
        conn,
        SCHEMA_ECO,
        TABLE,
        "Параметры анализа ПГ: выверенная копия отчетных данных ГИС ТЭК "
        "для страниц pg-vse / pg-bez-kot",
    )
    for column, comment in _COLUMN_COMMENTS.items():
        _comment_on_column(conn, SCHEMA_ECO, TABLE, column, comment)


def downgrade():
    conn = op.get_bind()
    if column_utils.table_exists(conn, SCHEMA_ECO, TABLE):
        op.drop_table(TABLE, schema=SCHEMA_ECO)

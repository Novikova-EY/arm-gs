# -*- coding: utf-8 -*-
"""Параметры ВЭД и электроёмкости: year_number -> FK на gs_sys_years (number, database_version_id).

Revision ID: e6f7a8b9c0d4
Revises: d5e6f7a8b9c0
Create Date: 2026-06-03
"""
import os
import sys

from alembic import op
from sqlalchemy import text

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "e6f7a8b9c0d4"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None

SCHEMA_EC = "gs_ec"
SCHEMA_REFDATA = "gs_sys"

# (table, constraint_name)
TABLES = (
    (
        "gs_ec_federal_district_economic_activity_consumption_params",
        "fk_ec_fd_ved_cons_year_ver",
    ),
    (
        "gs_ec_russia_federation_economic_activity_consumption_params",
        "fk_ec_rf_ved_cons_year_ver",
    ),
    (
        "gs_ec_federal_district_economic_activity_accum_fixed_capital_params",
        "fk_ec_fd_afci_year_ver",
    ),
    (
        "gs_ec_russia_federation_economic_activity_accum_fixed_capital_params",
        "fk_ec_rf_afci_year_ver",
    ),
    (
        "gs_ec_federal_district_economic_activity_product_output_params",
        "fk_ec_fd_po_year_ver",
    ),
    (
        "gs_ec_russia_federation_economic_activity_product_output_params",
        "fk_ec_rf_po_year_ver",
    ),
    (
        "gs_ec_federal_district_electrical_intensity_year_params",
        "fk_ec_fd_ei_y_year_ver",
    ),
    (
        "gs_ec_russia_federation_electrical_intensity_year_params",
        "fk_ec_rf_ei_y_year_ver",
    ),
)


def _ensure_missing_years(conn, table: str, table_years: str) -> int:
    """Добавить в справочник годы (number, database_version_id), на которые ссылаются параметры."""
    if not column_utils.table_exists(conn, SCHEMA_EC, table):
        return 0
    if not column_utils.table_has_column(conn, SCHEMA_EC, table, "year_number"):
        return 0
    result = conn.execute(
        text(
            f"""
            INSERT INTO "{SCHEMA_REFDATA}"."{table_years}" (number, database_version_id)
            SELECT DISTINCT t.year_number, t.database_version_id
            FROM "{SCHEMA_EC}"."{table}" AS t
            WHERE t.year_number IS NOT NULL
              AND NOT EXISTS (
                SELECT 1
                FROM "{SCHEMA_REFDATA}"."{table_years}" AS y
                WHERE y.number = t.year_number
                  AND (
                    (t.database_version_id IS NULL AND y.database_version_id IS NULL)
                    OR (t.database_version_id = y.database_version_id)
                  )
              )
            """
        )
    )
    return result.rowcount or 0


def _count_orphan_years(conn, table: str, table_years: str) -> int:
    return conn.execute(
        text(
            f"""
            SELECT COUNT(*)::int
            FROM "{SCHEMA_EC}"."{table}" AS t
            WHERE t.year_number IS NOT NULL
              AND NOT EXISTS (
                SELECT 1
                FROM "{SCHEMA_REFDATA}"."{table_years}" AS y
                WHERE y.number = t.year_number
                  AND (
                    (t.database_version_id IS NULL AND y.database_version_id IS NULL)
                    OR (t.database_version_id = y.database_version_id)
                  )
              )
            """
        )
    ).scalar() or 0


def _add_year_fk(conn, table: str, fk_name: str, table_years: str) -> None:
    if not column_utils.table_exists(conn, SCHEMA_EC, table):
        return
    if not column_utils.table_has_column(conn, SCHEMA_EC, table, "year_number"):
        return
    if column_utils.constraint_exists(conn, SCHEMA_EC, fk_name):
        return

    _ensure_missing_years(conn, table, table_years)

    orphans = _count_orphan_years(conn, table, table_years)
    if orphans:
        raise RuntimeError(
            f"Миграция: для {orphans} строк в {SCHEMA_EC}.{table} не найден год "
            f"в {SCHEMA_REFDATA}.{table_years} (number + database_version_id). "
            "Исправьте year_number или database_version_id в данных."
        )

    op.create_foreign_key(
        fk_name,
        table,
        table_years,
        ["year_number", "database_version_id"],
        ["number", "database_version_id"],
        source_schema=SCHEMA_EC,
        referent_schema=SCHEMA_REFDATA,
        ondelete="RESTRICT",
    )


def upgrade():
    conn = op.get_bind()
    table_years = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_years")
    if table_years is None:
        return
    for table, fk_name in TABLES:
        _add_year_fk(conn, table, fk_name, table_years)


def downgrade():
    conn = op.get_bind()
    for table, fk_name in TABLES:
        if not column_utils.table_exists(conn, SCHEMA_EC, table):
            continue
        if column_utils.constraint_exists(conn, SCHEMA_EC, fk_name):
            op.drop_constraint(fk_name, table, schema=SCHEMA_EC, type_="foreignkey")

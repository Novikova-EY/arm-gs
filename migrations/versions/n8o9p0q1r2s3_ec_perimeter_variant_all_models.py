# -*- coding: utf-8 -*-
"""Потребление (gs_ec): perimeter_variant_code для всех таблиц параметров.

Revision ID: n8o9p0q1r2s3
Revises: m7n8o9p0q1r2
Create Date: 2026-05-21
"""
import os
import sys

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)

revision = "n8o9p0q1r2s3"
down_revision = "m7n8o9p0q1r2"
branch_labels = None
depends_on = None

SCHEMA_EC = "gs_ec"
CODE_WITHOUT_NT = "without_nt"

# (table, fk_column_or_None, index_prefix, pvc_index_name)
TABLE_SPECS: tuple[tuple[str, str | None, str, str], ...] = (
    (
        "gs_ec_regional_energy_system_consumption_params",
        "id_regional_energy_system",
        "regional_energy_system",
        "ix_gs_ec_regional_energy_system_pvc",
    ),
    (
        "gs_ec_regional_district_consumption_params",
        "id_regional_district",
        "regional_district",
        "ix_gs_ec_regional_district_pvc",
    ),
    (
        "gs_ec_synchronous_area_consumption_params",
        "id_synchronous_area",
        "synchronous_area",
        "ix_gs_ec_synchronous_area_pvc",
    ),
    (
        "gs_ec_energy_zone_consumption_params",
        "id_energy_zone",
        "energy_zone",
        "ix_gs_ec_energy_zone_pvc",
    ),
    (
        "gs_ec_energy_area_consumption_params",
        "id_energy_area",
        "energy_area",
        "ix_gs_ec_energy_area_pvc",
    ),
    (
        "gs_ec_energy_unit_consumption_params",
        "id_energy_unit",
        "energy_unit",
        "ix_gs_ec_energy_unit_pvc",
    ),
    (
        "gs_ec_energy_system_type_consumption_params",
        "id_energy_system_type",
        "energy_system_type",
        "ix_gs_ec_energy_system_type_pvc",
    ),
    (
        "gs_ec_centralized_zone_consumption_params",
        None,
        "centralized_zone",
        "ix_gs_ec_centralized_zone_pvc",
    ),
    (
        "gs_ec_ees_consumption_params",
        None,
        "ees",
        "ix_gs_ec_ees_pvc",
    ),
)


def _column_exists(conn, schema: str, table: str, column: str) -> bool:
    r = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :col"
        ),
        {"schema": schema, "table": table, "col": column},
    )
    return r.fetchone() is not None


def _table_exists(conn, schema: str, table: str) -> bool:
    r = conn.execute(
        text(
            "SELECT 1 FROM pg_tables WHERE schemaname = :schema AND tablename = :table"
        ),
        {"schema": schema, "table": table},
    )
    return r.fetchone() is not None


def _dedupe_ec_rows(conn, table: str, fk_col: str | None = None) -> None:
    fk_part = f"{fk_col}, " if fk_col else ""
    conn.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY {fk_part}year_number,
                            COALESCE(database_version_id, 0),
                            COALESCE(perimeter_variant_code, '')
                        ORDER BY id DESC
                    ) AS rn
                FROM {SCHEMA_EC}.{table}
                WHERE year_number IS NOT NULL
            )
            DELETE FROM {SCHEMA_EC}.{table} t
            USING ranked r
            WHERE t.id = r.id AND r.rn > 1
            """
        )
    )
    conn.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY {fk_part}COALESCE(database_version_id, 0),
                            COALESCE(perimeter_variant_code, '')
                        ORDER BY id DESC
                    ) AS rn
                FROM {SCHEMA_EC}.{table}
                WHERE year_number IS NULL
            )
            DELETE FROM {SCHEMA_EC}.{table} t
            USING ranked r
            WHERE t.id = r.id AND r.rn > 1
            """
        )
    )


def _set_default_without_nt(conn, table: str) -> None:
    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA_EC}.{table}
            SET perimeter_variant_code = :code
            WHERE perimeter_variant_code IS NULL
            """
        ),
        {"code": CODE_WITHOUT_NT},
    )


def _drop_ec_unique_indexes(conn, pfx: str) -> None:
    for suffix in ("year", "nullyear"):
        conn.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA_EC}"."uq_gs_ec_{pfx}_{suffix}"'))


def _add_pvc_column(conn, table: str, index_name: str) -> None:
    if not _table_exists(conn, SCHEMA_EC, table):
        return
    if not _column_exists(conn, SCHEMA_EC, table, "perimeter_variant_code"):
        op.add_column(
            table,
            sa.Column("perimeter_variant_code", sa.String(64), nullable=True),
            schema=SCHEMA_EC,
        )
        op.create_index(
            index_name,
            table,
            ["perimeter_variant_code"],
            unique=False,
            schema=SCHEMA_EC,
        )


def _rebuild_no_fk_indexes(conn, table: str, pfx: str) -> None:
    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_ec_{pfx}_year
            ON "{SCHEMA_EC}"."{table}" (
                year_number,
                COALESCE(database_version_id, 0),
                COALESCE(perimeter_variant_code, '')
            )
            WHERE year_number IS NOT NULL
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_ec_{pfx}_nullyear
            ON "{SCHEMA_EC}"."{table}" (
                COALESCE(database_version_id, 0),
                COALESCE(perimeter_variant_code, '')
            )
            WHERE year_number IS NULL
            """
        )
    )


def _rebuild_fk_indexes(conn, table: str, fk_col: str, pfx: str) -> None:
    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_ec_{pfx}_year
            ON "{SCHEMA_EC}"."{table}" (
                {fk_col},
                year_number,
                COALESCE(database_version_id, 0),
                COALESCE(perimeter_variant_code, '')
            )
            WHERE year_number IS NOT NULL
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_ec_{pfx}_nullyear
            ON "{SCHEMA_EC}"."{table}" (
                {fk_col},
                COALESCE(database_version_id, 0),
                COALESCE(perimeter_variant_code, '')
            )
            WHERE year_number IS NULL
            """
        )
    )


def upgrade():
    conn = op.get_bind()
    for table, fk_col, pfx, ix_name in TABLE_SPECS:
        if not _table_exists(conn, SCHEMA_EC, table):
            continue
        _drop_ec_unique_indexes(conn, pfx)
        _add_pvc_column(conn, table, ix_name)
        _set_default_without_nt(conn, table)
        _dedupe_ec_rows(conn, table, fk_col)
        if fk_col:
            _rebuild_fk_indexes(conn, table, fk_col, pfx)
        else:
            _rebuild_no_fk_indexes(conn, table, pfx)


def downgrade():
    pass

# -*- coding: utf-8 -*-
"""FK выработки ЭЭ на справочник Year (number + database_version_id).

Revision ID: z0a1b2c3d4e5
Revises: y9z0a1b2c3d4
Create Date: 2026-06-09
"""
import os
import sys

from alembic import op
from sqlalchemy import text

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "z0a1b2c3d4e5"
down_revision = "y9z0a1b2c3d4"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REF = "gs_sys"
YEARS_TABLE = "gs_sys_years"

TABLES = (
    ("gs_gen_station_energy_generations", "fk_station_energy_gen_year_ver"),
    ("gs_gen_espp_energy_generations", "fk_espp_energy_gen_year_ver"),
    ("gs_gen_regional_energy_system_energy_generations", "fk_res_energy_gen_year_ver"),
)


def _null_orphan_year_numbers(conn, table: str) -> None:
    if not column_utils.table_exists(conn, SCHEMA_GEN, table):
        return
    if not column_utils.table_has_column(conn, SCHEMA_GEN, table, "year_number"):
        return

    conn.execute(
        text(
            f"""
            UPDATE "{SCHEMA_GEN}"."{table}" AS t
            SET year_number = NULL
            WHERE t.year_number IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM "{SCHEMA_REF}"."{YEARS_TABLE}" AS y
                  WHERE y.number = t.year_number
                    AND (
                        (y.database_version_id IS NULL AND t.database_version_id IS NULL)
                        OR y.database_version_id = t.database_version_id
                    )
              )
            """
        )
    )


def _add_year_fk(conn, table: str, constraint_name: str) -> None:
    if not column_utils.table_exists(conn, SCHEMA_GEN, table):
        return
    if column_utils.constraint_exists(conn, SCHEMA_GEN, constraint_name):
        return

    op.create_foreign_key(
        constraint_name,
        table,
        YEARS_TABLE,
        ["year_number", "database_version_id"],
        ["number", "database_version_id"],
        source_schema=SCHEMA_GEN,
        referent_schema=SCHEMA_REF,
        ondelete="RESTRICT",
    )


def upgrade():
    conn = op.get_bind()
    for table, constraint_name in TABLES:
        _null_orphan_year_numbers(conn, table)
        _add_year_fk(conn, table, constraint_name)


def downgrade():
    conn = op.get_bind()
    for table, constraint_name in reversed(TABLES):
        if not column_utils.table_exists(conn, SCHEMA_GEN, table):
            continue
        if not column_utils.constraint_exists(conn, SCHEMA_GEN, constraint_name):
            continue
        op.drop_constraint(constraint_name, table, schema=SCHEMA_GEN, type_="foreignkey")

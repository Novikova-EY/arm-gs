# -*- coding: utf-8 -*-
"""perimeter_variant_code для gs_pd_energy_zone_demand_params и gs_pd_energy_unit_demand_params.

Revision ID: y4z5a6b7c8d9
Revises: x3y4z5a6b7c8
Create Date: 2026-06-29
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

revision = "y4z5a6b7c8d9"
down_revision = "x3y4z5a6b7c8"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"

_TABLES: tuple[tuple[str, str, str], ...] = (
    (
        "gs_pd_energy_zone_demand_params",
        "id_energy_zone",
        "ez",
    ),
    (
        "gs_pd_energy_unit_demand_params",
        "id_energy_unit",
        "eu",
    ),
)


def _column_exists(conn, table: str, column: str) -> bool:
    r = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :col"
        ),
        {"schema": SCHEMA_PD, "table": table, "col": column},
    )
    return r.fetchone() is not None


def _table_exists(conn, table: str) -> bool:
    r = conn.execute(
        text(
            "SELECT 1 FROM pg_tables WHERE schemaname = :schema AND tablename = :table"
        ),
        {"schema": SCHEMA_PD, "table": table},
    )
    return r.fetchone() is not None


def _upgrade_table(conn, table: str, fk_col: str, ix_suffix: str) -> None:
    if not _table_exists(conn, table):
        return

    if not _column_exists(conn, table, "perimeter_variant_code"):
        op.add_column(
            table,
            sa.Column("perimeter_variant_code", sa.String(64), nullable=True),
            schema=SCHEMA_PD,
        )
        op.create_index(
            f"ix_{table}_perimeter_variant_code",
            table,
            ["perimeter_variant_code"],
            unique=False,
            schema=SCHEMA_PD,
        )

    for ix in (
        f"uq_{ix_suffix}_demand_params_hist",
        f"uq_{ix_suffix}_demand_params_year",
    ):
        conn.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA_PD}"."{ix}"'))

    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_{ix_suffix}_demand_params_hist
            ON "{SCHEMA_PD}"."{table}" (
                {fk_col},
                COALESCE(database_version_id, 0),
                COALESCE(perimeter_variant_code, '')
            )
            WHERE is_historical_maximum = true
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_{ix_suffix}_demand_params_year
            ON "{SCHEMA_PD}"."{table}" (
                {fk_col},
                year_number,
                COALESCE(database_version_id, 0),
                COALESCE(perimeter_variant_code, '')
            )
            WHERE is_historical_maximum = false
            """
        )
    )


def _downgrade_table(conn, table: str, fk_col: str, ix_suffix: str) -> None:
    if not _table_exists(conn, table):
        return

    for ix in (
        f"uq_{ix_suffix}_demand_params_hist",
        f"uq_{ix_suffix}_demand_params_year",
    ):
        conn.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA_PD}"."{ix}"'))

    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_{ix_suffix}_demand_params_hist
            ON "{SCHEMA_PD}"."{table}" (
                {fk_col},
                COALESCE(database_version_id, 0)
            )
            WHERE is_historical_maximum = true
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_{ix_suffix}_demand_params_year
            ON "{SCHEMA_PD}"."{table}" (
                {fk_col},
                year_number,
                COALESCE(database_version_id, 0)
            )
            WHERE is_historical_maximum = false
            """
        )
    )

    if _column_exists(conn, table, "perimeter_variant_code"):
        ix_name = f"ix_{table}_perimeter_variant_code"
        if column_utils.index_exists(conn, SCHEMA_PD, ix_name):
            op.drop_index(ix_name, table_name=table, schema=SCHEMA_PD)
        op.drop_column(table, "perimeter_variant_code", schema=SCHEMA_PD)


def upgrade():
    conn = op.get_bind()
    for table, fk_col, ix_suffix in _TABLES:
        _upgrade_table(conn, table, fk_col, ix_suffix)


def downgrade():
    conn = op.get_bind()
    for table, fk_col, ix_suffix in _TABLES:
        _downgrade_table(conn, table, fk_col, ix_suffix)

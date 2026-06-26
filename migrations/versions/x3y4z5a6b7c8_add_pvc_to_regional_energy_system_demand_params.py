# -*- coding: utf-8 -*-
"""perimeter_variant_code для gs_pd_regional_energy_system_demand_params.

Revision ID: x3y4z5a6b7c8
Revises: w2x3y4z5a6b7
Create Date: 2026-06-26
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

revision = "x3y4z5a6b7c8"
down_revision = "w2x3y4z5a6b7"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
TABLE = "gs_pd_regional_energy_system_demand_params"
FK_COL = "id_regional_energy_system"


def _column_exists(conn, column: str) -> bool:
    r = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :col"
        ),
        {"schema": SCHEMA_PD, "table": TABLE, "col": column},
    )
    return r.fetchone() is not None


def _table_exists(conn) -> bool:
    r = conn.execute(
        text(
            "SELECT 1 FROM pg_tables WHERE schemaname = :schema AND tablename = :table"
        ),
        {"schema": SCHEMA_PD, "table": TABLE},
    )
    return r.fetchone() is not None


def upgrade():
    conn = op.get_bind()
    if not _table_exists(conn):
        return

    if not _column_exists(conn, "perimeter_variant_code"):
        op.add_column(
            TABLE,
            sa.Column("perimeter_variant_code", sa.String(64), nullable=True),
            schema=SCHEMA_PD,
        )
        op.create_index(
            "ix_gs_pd_regional_energy_system_demand_params_pvc",
            TABLE,
            ["perimeter_variant_code"],
            unique=False,
            schema=SCHEMA_PD,
        )

    for ix in (
        "uq_gs_res_demand_params_hist",
        "uq_gs_res_demand_params_year",
        "uq_regional_energy_system_demand_params_hist",
        "uq_regional_energy_system_demand_params_year",
    ):
        conn.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA_PD}"."{ix}"'))

    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_pd_regional_energy_system_demand_params_hist
            ON "{SCHEMA_PD}"."{TABLE}" (
                {FK_COL},
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
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_pd_regional_energy_system_demand_params_year
            ON "{SCHEMA_PD}"."{TABLE}" (
                {FK_COL},
                year_number,
                COALESCE(database_version_id, 0),
                COALESCE(perimeter_variant_code, '')
            )
            WHERE is_historical_maximum = false
            """
        )
    )


def downgrade():
    conn = op.get_bind()
    if not _table_exists(conn):
        return

    for ix in (
        "uq_gs_pd_regional_energy_system_demand_params_hist",
        "uq_gs_pd_regional_energy_system_demand_params_year",
    ):
        conn.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA_PD}"."{ix}"'))

    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_res_demand_params_hist
            ON "{SCHEMA_PD}"."{TABLE}" (
                {FK_COL},
                COALESCE(database_version_id, 0)
            )
            WHERE is_historical_maximum = true
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_res_demand_params_year
            ON "{SCHEMA_PD}"."{TABLE}" (
                {FK_COL},
                year_number,
                COALESCE(database_version_id, 0)
            )
            WHERE is_historical_maximum = false
            """
        )
    )

    if _column_exists(conn, "perimeter_variant_code"):
        if column_utils.index_exists(
            conn, SCHEMA_PD, "ix_gs_pd_regional_energy_system_demand_params_pvc"
        ):
            op.drop_index(
                "ix_gs_pd_regional_energy_system_demand_params_pvc",
                table_name=TABLE,
                schema=SCHEMA_PD,
            )
        op.drop_column(TABLE, "perimeter_variant_code", schema=SCHEMA_PD)

# -*- coding: utf-8 -*-
"""gs_pd_centralized_zone_demand_params: perimeter_variant_code (ЦЗ России с/без НТ).

Revision ID: w2x3y4z5a6b7
Revises: v1w2x3y4z5a6
Create Date: 2026-06-25
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

revision = "w2x3y4z5a6b7"
down_revision = "v1w2x3y4z5a6"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
TABLE = "gs_pd_centralized_zone_demand_params"
CODE_WITHOUT_NT = "without_nt"


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
            "ix_gs_pd_centralized_zone_demand_params_pvc",
            TABLE,
            ["perimeter_variant_code"],
            unique=False,
            schema=SCHEMA_PD,
        )

    for ix in (
        "uq_centralized_zone_dp_hist",
        "uq_centralized_zone_dp_year",
        "uq_gs_pd_centralized_zone_demand_params_hist",
        "uq_gs_pd_centralized_zone_demand_params_year",
    ):
        conn.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA_PD}"."{ix}"'))

    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA_PD}.{TABLE}
            SET perimeter_variant_code = :code
            WHERE perimeter_variant_code IS NULL
            """
        ),
        {"code": CODE_WITHOUT_NT},
    )

    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_pd_centralized_zone_demand_params_hist
            ON "{SCHEMA_PD}"."{TABLE}" (
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
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_pd_centralized_zone_demand_params_year
            ON "{SCHEMA_PD}"."{TABLE}" (
                year_number,
                COALESCE(database_version_id, 0),
                COALESCE(perimeter_variant_code, '')
            )
            WHERE is_historical_maximum = false
            """
        )
    )


def downgrade():
    pass

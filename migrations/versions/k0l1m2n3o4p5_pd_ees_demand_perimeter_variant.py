# -*- coding: utf-8 -*-
"""gs_pd_ees_demand_params: perimeter_variant_code (ЭЭС России с/без НТ).

Revision ID: k0l1m2n3o4p5
Revises: j9k0l1m2n3o4
Create Date: 2026-06-16
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

revision = "k0l1m2n3o4p5"
down_revision = "j9k0l1m2n3o4"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
TABLE = "gs_pd_ees_demand_params"
CODE_WITHOUT_NT = "without_nt"


def _column_exists(conn, table: str, column: str) -> bool:
    r = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :col"
        ),
        {"schema": SCHEMA_PD, "table": table, "col": column},
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


def upgrade():
    conn = op.get_bind()
    if not _table_exists(conn, SCHEMA_PD, TABLE):
        return

    if not _column_exists(conn, TABLE, "perimeter_variant_code"):
        op.add_column(
            TABLE,
            sa.Column("perimeter_variant_code", sa.String(64), nullable=True),
            schema=SCHEMA_PD,
        )
        op.create_index(
            "ix_gs_pd_ees_demand_params_pvc",
            TABLE,
            ["perimeter_variant_code"],
            unique=False,
            schema=SCHEMA_PD,
        )

    for ix in ("uq_ees_dp_hist", "uq_ees_dp_year"):
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
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_pd_ees_demand_params_hist
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
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_pd_ees_demand_params_year
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

# -*- coding: utf-8 -*-
"""gs_pd_synchronous_area_demand_params: perimeter_variant_code; привязки with_nt/without_nt для Первой СЗ.

Revision ID: l1m2n3o4p5q6
Revises: k0l1m2n3o4p5
Create Date: 2026-06-16
"""
import os
import sys
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "l1m2n3o4p5q6"
down_revision = "k0l1m2n3o4p5"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
SCHEMA_REF = "gs_sys"
TABLE = "gs_pd_synchronous_area_demand_params"
TABLE_VARIANTS = "gs_sys_perimeter_variants"
TABLE_BINDINGS = "gs_sys_entity_perimeter_bindings"

CODE_WITH_NT = "with_nt"
CODE_WITHOUT_NT = "without_nt"
ENTITY_KIND = "synchronous_area"
ENTITY_NAME = "Первая синхронная зона"
LABEL_PREFIX = "Первая синхронная зона"


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


def _variant_id(conn, code: str) -> int | None:
    row = conn.execute(
        text(
            f"SELECT id FROM {SCHEMA_REF}.{TABLE_VARIANTS} "
            "WHERE code = :code ORDER BY id LIMIT 1"
        ),
        {"code": code},
    ).fetchone()
    return int(row[0]) if row else None


def _ensure_binding(conn, *, vcode: str, sort_order: int) -> None:
    pvid = _variant_id(conn, vcode)
    if pvid is None:
        return
    dup = conn.execute(
        text(
            f"""
            SELECT 1 FROM {SCHEMA_REF}.{TABLE_BINDINGS}
            WHERE entity_kind = :ek AND entity_name = :en
              AND id_perimeter_variant = :pvid
            LIMIT 1
            """
        ),
        {"ek": ENTITY_KIND, "en": ENTITY_NAME, "pvid": pvid},
    ).fetchone()
    if dup:
        return
    conn.execute(
        text(
            f"""
            INSERT INTO {SCHEMA_REF}.{TABLE_BINDINGS}
            (entity_kind, entity_name, label_prefix, sort_order, id_perimeter_variant,
             ref_uuid, version, database_version_id, created_by, modified_by)
            VALUES (:ek, :en, :prefix, :sort, :pvid, :ruuid, 1, NULL, 'migration', 'migration')
            """
        ),
        {
            "ek": ENTITY_KIND,
            "en": ENTITY_NAME,
            "prefix": LABEL_PREFIX,
            "sort": sort_order,
            "pvid": pvid,
            "ruuid": str(uuid.uuid4()),
        },
    )


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
            "ix_gs_pd_synchronous_area_demand_params_pvc",
            TABLE,
            ["perimeter_variant_code"],
            unique=False,
            schema=SCHEMA_PD,
        )

    for ix in (
        "uq_gs_synchronous_area_demand_params_hist",
        "uq_gs_synchronous_area_demand_params_year",
        "uq_sa_dp_hist",
        "uq_sa_dp_year",
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
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_pd_synchronous_area_demand_params_hist
            ON "{SCHEMA_PD}"."{TABLE}" (
                id_synchronous_area,
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
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_pd_synchronous_area_demand_params_year
            ON "{SCHEMA_PD}"."{TABLE}" (
                id_synchronous_area,
                year_number,
                COALESCE(database_version_id, 0),
                COALESCE(perimeter_variant_code, '')
            )
            WHERE is_historical_maximum = false
            """
        )
    )

    if _table_exists(conn, SCHEMA_REF, TABLE_VARIANTS):
        _ensure_binding(conn, vcode=CODE_WITH_NT, sort_order=10)
        _ensure_binding(conn, vcode=CODE_WITHOUT_NT, sort_order=11)


def downgrade():
    pass

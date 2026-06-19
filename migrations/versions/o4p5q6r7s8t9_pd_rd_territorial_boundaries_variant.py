# -*- coding: utf-8 -*-
"""gs_pd_regional_district_demand_params: perimeter_variant_code; вариант territorial_boundaries для Чукотского АО.

Revision ID: o4p5q6r7s8t9
Revises: n3o4p5q6r7s8
Create Date: 2026-06-17
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

revision = "o4p5q6r7s8t9"
down_revision = "n3o4p5q6r7s8"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
SCHEMA_REF = "gs_sys"
TABLE = "gs_pd_regional_district_demand_params"
TABLE_VARIANTS = "gs_sys_perimeter_variants"
TABLE_BINDINGS = "gs_sys_entity_perimeter_bindings"

CODE_TERRITORIAL_BOUNDARIES = "territorial_boundaries"
ENTITY_KIND = "regional_district"
ENTITY_NAME = "Чукотский АО"
LABEL_PREFIX = "Чукотский АО"
VARIANT_LABEL = "(в территориальных границах)"


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


def _ensure_variant(conn) -> int | None:
    existing = _variant_id(conn, CODE_TERRITORIAL_BOUNDARIES)
    if existing is not None:
        return existing
    if not _table_exists(conn, SCHEMA_REF, TABLE_VARIANTS):
        return None
    rid = conn.execute(
        text(
            f"""
            INSERT INTO {SCHEMA_REF}.{TABLE_VARIANTS}
            (code, label_suffix, effective_from_year, effective_to_year,
             is_territorial_base, display_order, ref_uuid, version, database_version_id,
             created_by, modified_by)
            VALUES (:code, :lbl, NULL, NULL, false, 60, :ruuid, 1, NULL,
                    'migration', 'migration')
            RETURNING id
            """
        ),
        {
            "code": CODE_TERRITORIAL_BOUNDARIES,
            "lbl": VARIANT_LABEL,
            "ruuid": str(uuid.uuid4()),
        },
    ).scalar()
    return int(rid) if rid is not None else None


def _ensure_binding(conn, variant_id: int) -> None:
    if not _table_exists(conn, SCHEMA_REF, TABLE_BINDINGS):
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
        {"ek": ENTITY_KIND, "en": ENTITY_NAME, "pvid": variant_id},
    ).fetchone()
    if dup:
        return
    conn.execute(
        text(
            f"""
            INSERT INTO {SCHEMA_REF}.{TABLE_BINDINGS}
            (entity_kind, entity_name, label_prefix, sort_order, id_perimeter_variant,
             ref_uuid, version, database_version_id, created_by, modified_by)
            VALUES (:ek, :en, :prefix, 0, :pvid, :ruuid, 1, NULL, 'migration', 'migration')
            """
        ),
        {
            "ek": ENTITY_KIND,
            "en": ENTITY_NAME,
            "prefix": LABEL_PREFIX,
            "pvid": variant_id,
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
            "ix_gs_pd_regional_district_demand_params_pvc",
            TABLE,
            ["perimeter_variant_code"],
            unique=False,
            schema=SCHEMA_PD,
        )

    for ix in ("uq_rd_demand_params_hist", "uq_rd_demand_params_year"):
        conn.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA_PD}"."{ix}"'))

    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_rd_demand_params_hist
            ON "{SCHEMA_PD}"."{TABLE}" (
                id_regional_district,
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
            CREATE UNIQUE INDEX IF NOT EXISTS uq_rd_demand_params_year
            ON "{SCHEMA_PD}"."{TABLE}" (
                id_regional_district,
                year_number,
                COALESCE(database_version_id, 0),
                COALESCE(perimeter_variant_code, '')
            )
            WHERE is_historical_maximum = false
            """
        )
    )

    variant_id = _ensure_variant(conn)
    if variant_id is not None:
        _ensure_binding(conn, variant_id)


def downgrade():
    pass

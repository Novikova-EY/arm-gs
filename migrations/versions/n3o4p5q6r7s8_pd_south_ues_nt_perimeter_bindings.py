# -*- coding: utf-8 -*-
"""Привязки with_nt / without_nt для «ОЭС Юга»; убрать варианты ГАЭС из дерева сводки.

Revision ID: n3o4p5q6r7s8
Revises: m2n3o4p5q6r7
Create Date: 2026-06-16
"""
import uuid

from alembic import op
from sqlalchemy import text

revision = "n3o4p5q6r7s8"
down_revision = "m2n3o4p5q6r7"
branch_labels = None
depends_on = None

SCHEMA_REF = "gs_sys"
TABLE_VARIANTS = "gs_sys_perimeter_variants"
TABLE_BINDINGS = "gs_sys_entity_perimeter_bindings"

CODE_WITH_NT = "with_nt"
CODE_WITHOUT_NT = "without_nt"
ENTITY_KIND = "union_energy_system"
ENTITY_NAME = "ОЭС Юга"
LABEL_PREFIX = "ОЭС Юга"

GAES_TREE_VARIANT_CODES = (
    "with_nt_with_gaes",
    "with_nt_without_gaes",
    "without_nt_with_gaes",
    "without_nt_without_gaes",
)


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


def _remove_gaes_bindings(conn) -> None:
    codes_sql = ", ".join(f"'{c}'" for c in GAES_TREE_VARIANT_CODES)
    conn.execute(
        text(
            f"""
            DELETE FROM {SCHEMA_REF}.{TABLE_BINDINGS} b
            USING {SCHEMA_REF}.{TABLE_VARIANTS} v
            WHERE b.id_perimeter_variant = v.id
              AND b.entity_kind = :ek
              AND b.entity_name = :en
              AND v.code IN ({codes_sql})
            """
        ),
        {"ek": ENTITY_KIND, "en": ENTITY_NAME},
    )


def upgrade():
    conn = op.get_bind()
    if not _table_exists(conn, SCHEMA_REF, TABLE_BINDINGS):
        return
    _remove_gaes_bindings(conn)
    _ensure_binding(conn, vcode=CODE_WITH_NT, sort_order=0)
    _ensure_binding(conn, vcode=CODE_WITHOUT_NT, sort_order=1)


def downgrade():
    pass

# -*- coding: utf-8 -*-
"""Привязки with_nt / without_nt для «ЕЭС России» (energy_system_type) в каталоге периметра.

Revision ID: m2n3o4p5q6r7
Revises: l1m2n3o4p5q6
Create Date: 2026-06-16
"""
import uuid

from alembic import op
from sqlalchemy import text

revision = "m2n3o4p5q6r7"
down_revision = "l1m2n3o4p5q6"
branch_labels = None
depends_on = None

SCHEMA_REF = "gs_sys"
TABLE_VARIANTS = "gs_sys_perimeter_variants"
TABLE_BINDINGS = "gs_sys_entity_perimeter_bindings"

CODE_WITH_NT = "with_nt"
CODE_WITHOUT_NT = "without_nt"
ENTITY_KIND = "energy_system_type"
ENTITY_NAME = "ЕЭС России"
LABEL_PREFIX = "ЕЭС России"


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
    if not _table_exists(conn, SCHEMA_REF, TABLE_VARIANTS):
        return
    _ensure_binding(conn, vcode=CODE_WITH_NT, sort_order=0)
    _ensure_binding(conn, vcode=CODE_WITHOUT_NT, sort_order=1)


def downgrade():
    pass

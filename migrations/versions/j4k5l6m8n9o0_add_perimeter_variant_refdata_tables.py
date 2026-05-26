# -*- coding: utf-8 -*-
"""Справочник вариантов периметра и привязок; seed; снятие жёсткого CHECK на UES demand.

Revision ID: j4k5l6m8n9o0
Revises: i3j4k5l6m7n8
Create Date: 2026-05-20
"""
import os
import sys

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils

revision = "j4k5l6m8n9o0"
down_revision = "i3j4k5l6m7n8"
branch_labels = None
depends_on = None

SCHEMA_REF = "gs_sys"
SCHEMA_PD = "gs_pd"
TABLE_VARIANTS = "gs_sys_perimeter_variants"
TABLE_BINDINGS = "gs_sys_entity_perimeter_bindings"
TABLE_UES = "gs_pd_union_energy_system_demand_params"

SEED_VARIANTS = (
    ("with_nt", "с НТ", 2024, None, False, 10),
    ("without_nt", "без НТ", None, None, True, 20),
    ("without_crimea_sev", "без ЭС РК и г.С", None, None, False, 30),
    ("without_nt_with_kaliningrad_es", "без НТ (с ЭС Калининградской области)", None, 2024, True, 40),
    ("without_nt_without_kaliningrad_es", "без НТ (без ЭС Калининградской области)", 2025, None, True, 50),
)

SEED_BINDINGS = (
    ("union_energy_system", "ОЭС Юга", "ОЭС Юга", "with_nt", 0),
    ("union_energy_system", "ОЭС Юга", "ОЭС Юга", "without_nt", 1),
    ("synchronous_area", "Первая синхронная зона", "Первая синхронная зона", "without_nt_with_kaliningrad_es", 0),
    ("synchronous_area", "Первая синхронная зона", "Первая синхронная зона", "without_nt_without_kaliningrad_es", 1),
)


def _table_exists(conn, schema: str, table: str) -> bool:
    r = conn.execute(
        text(
            "SELECT 1 FROM pg_tables "
            "WHERE schemaname = :schema AND tablename = :table"
        ),
        {"schema": schema, "table": table},
    )
    return r.fetchone() is not None


def upgrade():
    conn = op.get_bind()
    ref_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REF)
    if ref_versions is None:
        raise RuntimeError(
            f"Не найдена таблица версий БД в {SCHEMA_REF} "
            "(gs_sys_database_versions или gs_database_versions как BASE TABLE)"
        )

    if not _table_exists(conn, SCHEMA_REF, TABLE_VARIANTS):
        op.create_table(
            TABLE_VARIANTS,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("label_suffix", sa.String(255), nullable=False),
            sa.Column("effective_from_year", sa.Integer(), nullable=True),
            sa.Column("effective_to_year", sa.Integer(), nullable=True),
            sa.Column("is_territorial_base", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("display_order", sa.Integer(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("ref_uuid", sa.String(36), nullable=False),
            sa.Column("version", sa.Integer(), server_default="1", nullable=False),
            sa.Column("database_version_id", sa.Integer(), nullable=True),
            sa.Column("created_by", sa.String(255), nullable=True),
            sa.Column("modified_by", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("database_version_id", "code", name="uq_gs_sys_perimeter_variants_ver_code"),
            schema=SCHEMA_REF,
        )
        op.create_index(
            "ix_gs_sys_perimeter_variants_code",
            TABLE_VARIANTS,
            ["code"],
            unique=False,
            schema=SCHEMA_REF,
        )
        op.create_foreign_key(
            "fk_gs_sys_perimeter_variants_database_version",
            TABLE_VARIANTS,
            ref_versions,
            ["database_version_id"],
            ["id"],
            source_schema=SCHEMA_REF,
            referent_schema=SCHEMA_REF,
            ondelete="SET NULL",
        )

    if not _table_exists(conn, SCHEMA_REF, TABLE_BINDINGS):
        op.create_table(
            TABLE_BINDINGS,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("entity_kind", sa.String(64), nullable=False),
            sa.Column("entity_name", sa.String(255), nullable=False),
            sa.Column("label_prefix", sa.String(255), nullable=True),
            sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
            sa.Column("id_perimeter_variant", sa.Integer(), nullable=False),
            sa.Column("ref_uuid", sa.String(36), nullable=False),
            sa.Column("version", sa.Integer(), server_default="1", nullable=False),
            sa.Column("database_version_id", sa.Integer(), nullable=True),
            sa.Column("created_by", sa.String(255), nullable=True),
            sa.Column("modified_by", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["id_perimeter_variant"], [f"{SCHEMA_REF}.{TABLE_VARIANTS}.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "database_version_id",
                "entity_kind",
                "entity_name",
                "id_perimeter_variant",
                name="uq_gs_sys_entity_perimeter_bindings_ver_entity_variant",
            ),
            schema=SCHEMA_REF,
        )
        op.create_foreign_key(
            "fk_gs_sys_entity_perimeter_bindings_database_version",
            TABLE_BINDINGS,
            ref_versions,
            ["database_version_id"],
            ["id"],
            source_schema=SCHEMA_REF,
            referent_schema=SCHEMA_REF,
            ondelete="SET NULL",
        )

    # Seed для каждой версии БД (только если ещё нет вариантов)
    versions = conn.execute(text(f"SELECT id FROM {SCHEMA_REF}.gs_database_versions")).fetchall()
    import uuid

    for (vid_row,) in versions:
        vid = int(vid_row)
        exists = conn.execute(
            text(
                f"SELECT 1 FROM {SCHEMA_REF}.{TABLE_VARIANTS} "
                "WHERE database_version_id = :vid LIMIT 1"
            ),
            {"vid": vid},
        ).fetchone()
        if exists:
            continue
        code_to_id: dict[str, int] = {}
        for code, lbl, yf, yt, base, ord_ in SEED_VARIANTS:
            rid = conn.execute(
                text(
                    f"""
                    INSERT INTO {SCHEMA_REF}.{TABLE_VARIANTS}
                    (code, label_suffix, effective_from_year, effective_to_year,
                     is_territorial_base, display_order, ref_uuid, version, database_version_id,
                     created_by, modified_by)
                    VALUES (:code, :lbl, :yf, :yt, :base, :ord, :ruuid, 1, :vid, 'migration', 'migration')
                    RETURNING id
                    """
                ),
                {
                    "code": code,
                    "lbl": lbl,
                    "yf": yf,
                    "yt": yt,
                    "base": base,
                    "ord": ord_,
                    "ruuid": str(uuid.uuid4()),
                    "vid": vid,
                },
            ).scalar()
            code_to_id[code] = int(rid)

        for ek, en, prefix, vcode, sort_o in SEED_BINDINGS:
            vid_var = code_to_id.get(vcode)
            if vid_var is None:
                continue
            conn.execute(
                text(
                    f"""
                    INSERT INTO {SCHEMA_REF}.{TABLE_BINDINGS}
                    (entity_kind, entity_name, label_prefix, sort_order, id_perimeter_variant,
                     ref_uuid, version, database_version_id, created_by, modified_by)
                    VALUES (:ek, :en, :prefix, :sort, :pvid, :ruuid, 1, :dbvid, 'migration', 'migration')
                    """
                ),
                {
                    "ek": ek,
                    "en": en,
                    "prefix": prefix,
                    "sort": sort_o,
                    "pvid": vid_var,
                    "ruuid": str(uuid.uuid4()),
                    "dbvid": vid,
                },
            )

    # Снять жёсткий CHECK — коды расширяются через справочник
    conn.execute(
        text(
            f"ALTER TABLE {SCHEMA_PD}.{TABLE_UES} "
            "DROP CONSTRAINT IF EXISTS ck_gs_ues_demand_params_perimeter_variant_code"
        )
    )


def downgrade():
    op.drop_table(TABLE_BINDINGS, schema=SCHEMA_REF)
    op.drop_table(TABLE_VARIANTS, schema=SCHEMA_REF)

# -*- coding: utf-8 -*-
"""Удалить ошибочные привязки вариантов «с/без заряда ГАЭС» к дереву сводки.

Revision ID: p0q1r2s3t4u6
Revises: o9p0q1r2s3t4
Create Date: 2026-05-22
"""
from alembic import op
from sqlalchemy import text

revision = "p0q1r2s3t4u6"
down_revision = "o9p0q1r2s3t4"
branch_labels = None
depends_on = None

SCHEMA_REF = "gs_sys"
TABLE_BINDINGS = "gs_sys_entity_perimeter_bindings"
TABLE_VARIANTS = "gs_sys_perimeter_variants"

TREE_ENTITY_KINDS = (
    "energy_system_type",
    "union_energy_system",
    "russia",
    "federal_district",
)

GAES_TREE_VARIANT_CODES = (
    "with_nt_with_gaes",
    "with_nt_without_gaes",
    "without_nt_with_gaes",
    "without_nt_without_gaes",
)


def upgrade():
    conn = op.get_bind()
    kinds_sql = ", ".join(f"'{k}'" for k in TREE_ENTITY_KINDS)
    codes_sql = ", ".join(f"'{c}'" for c in GAES_TREE_VARIANT_CODES)
    conn.execute(
        text(
            f"""
            DELETE FROM {SCHEMA_REF}.{TABLE_BINDINGS} b
            USING {SCHEMA_REF}.{TABLE_VARIANTS} v
            WHERE b.id_perimeter_variant = v.id
              AND b.entity_kind IN ({kinds_sql})
              AND v.code IN ({codes_sql})
            """
        )
    )


def downgrade():
    pass

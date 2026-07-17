# -*- coding: utf-8 -*-
"""Снять «Год по» у GAES-вариантов первой СЗ с ЭС Калининградской области.

Revision ID: s4t5u6v7w8x9
Revises: q2r3s4t5u6v7
Create Date: 2026-07-02
"""
from alembic import op
from sqlalchemy import text

revision = "s4t5u6v7w8x9"
down_revision = "q2r3s4t5u6v7"
branch_labels = None
depends_on = None

SCHEMA_REF = "gs_sys"
TABLE_VARIANTS = "gs_sys_perimeter_variants"
VARIANT_CODES = (
    "without_nt_with_gaes_with_kaliningrad_es",
    "without_nt_without_gaes_with_kaliningrad_es",
)


def upgrade():
    conn = op.get_bind()
    for code in VARIANT_CODES:
        conn.execute(
            text(
                f"""
                UPDATE {SCHEMA_REF}.{TABLE_VARIANTS}
                SET effective_to_year = NULL,
                    modified_by = 'migration'
                WHERE code = :code
                  AND effective_to_year IS NOT NULL
                """
            ),
            {"code": code},
        )


def downgrade():
    conn = op.get_bind()
    for code in VARIANT_CODES:
        conn.execute(
            text(
                f"""
                UPDATE {SCHEMA_REF}.{TABLE_VARIANTS}
                SET effective_to_year = 2024,
                    modified_by = 'migration'
                WHERE code = :code
                """
            ),
            {"code": code},
        )

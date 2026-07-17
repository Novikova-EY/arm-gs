# -*- coding: utf-8 -*-
"""Снять «Год по» у варианта without_nt_with_kaliningrad_es (первая СЗ с ЭС КО).

Revision ID: q2r3s4t5u6v7
Revises: ep3c4d5e6f7
Create Date: 2026-07-02
"""
from alembic import op
from sqlalchemy import text

revision = "q2r3s4t5u6v7"
down_revision = "ep3c4d5e6f7"
branch_labels = None
depends_on = None

SCHEMA_REF = "gs_sys"
TABLE_VARIANTS = "gs_sys_perimeter_variants"
# На сводке нагрузок (без ГАЭС) используется without_nt_without_gaes_with_kaliningrad_es;
# в справочнике также есть legacy/GAES-коды «с ЭС Калининградской области».
VARIANT_CODES_WITH_KALININGRAD_ES = (
    "without_nt_with_kaliningrad_es",
    "without_nt_with_gaes_with_kaliningrad_es",
    "without_nt_without_gaes_with_kaliningrad_es",
)


def upgrade():
    conn = op.get_bind()
    for code in VARIANT_CODES_WITH_KALININGRAD_ES:
        conn.execute(
            text(
                f"""
                UPDATE {SCHEMA_REF}.{TABLE_VARIANTS}
                SET effective_to_year = NULL,
                    modified_by = 'migration'
                WHERE code = :code
                """
            ),
            {"code": code},
        )


def downgrade():
    conn = op.get_bind()
    for code in VARIANT_CODES_WITH_KALININGRAD_ES:
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

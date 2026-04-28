# -*- coding: utf-8 -*-
"""Перенос gs_gen_tep_price_conversion_coefficients -> gs_sys.gs_sys_tep_price_conversion_coefficients

Revision ID: m9n0o1p2q3r4
Revises: e0f1a2b3c4d5
Create Date: 2026-04-24
"""
from alembic import op

revision = "m9n0o1p2q3r4"
down_revision = "e0f1a2b3c4d5"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REF = "gs_sys"
OLD = "gs_gen_tep_price_conversion_coefficients"
NEW = "gs_sys_tep_price_conversion_coefficients"


def upgrade():
    op.execute(
        f'ALTER TABLE "{SCHEMA_GEN}"."{OLD}" SET SCHEMA "{SCHEMA_REF}"',
    )
    op.rename_table(OLD, NEW, schema=SCHEMA_REF)


def downgrade():
    op.rename_table(NEW, OLD, schema=SCHEMA_REF)
    op.execute(
        f'ALTER TABLE "{SCHEMA_REF}"."{OLD}" SET SCHEMA "{SCHEMA_GEN}"',
    )

# -*- coding: utf-8 -*-
"""Переименование ges_tep_price_conversion_coefficients -> tep_price_conversion_coefficients
(общие коэффициенты ТЭП для всех типов станций).

Revision ID: z2b3c4d5e6f8
Revises: z1a2b3c4d5e6
Create Date: 2026-04-13
"""
from alembic import op

revision = "z2b3c4d5e6f8"
down_revision = "z1a2b3c4d5e6"
branch_labels = None
depends_on = None

SCHEMA = "gs_gen"
OLD_TABLE = "ges_tep_price_conversion_coefficients"
NEW_TABLE = "tep_price_conversion_coefficients"


def upgrade():
    op.rename_table(OLD_TABLE, NEW_TABLE, schema=SCHEMA)
    op.execute(
        f'ALTER INDEX "{SCHEMA}".ix_ges_tep_price_conv_coeff_id_year '
        "RENAME TO ix_tep_price_conv_coeff_id_year"
    )
    op.execute(
        f'ALTER INDEX "{SCHEMA}".ix_ges_tep_price_conv_coeff_database_version_id '
        "RENAME TO ix_tep_price_conv_coeff_database_version_id"
    )
    op.execute(
        f'ALTER TABLE "{SCHEMA}"."{NEW_TABLE}" RENAME CONSTRAINT '
        "uq_ges_tep_price_conv_coeff_version_year TO uq_tep_price_conv_coeff_version_year"
    )


def downgrade():
    op.execute(
        f'ALTER TABLE "{SCHEMA}"."{NEW_TABLE}" RENAME CONSTRAINT '
        "uq_tep_price_conv_coeff_version_year TO uq_ges_tep_price_conv_coeff_version_year"
    )
    op.execute(
        f'ALTER INDEX "{SCHEMA}".ix_tep_price_conv_coeff_database_version_id '
        "RENAME TO ix_ges_tep_price_conv_coeff_database_version_id"
    )
    op.execute(
        f'ALTER INDEX "{SCHEMA}".ix_tep_price_conv_coeff_id_year '
        "RENAME TO ix_ges_tep_price_conv_coeff_id_year"
    )
    op.rename_table(NEW_TABLE, OLD_TABLE, schema=SCHEMA)

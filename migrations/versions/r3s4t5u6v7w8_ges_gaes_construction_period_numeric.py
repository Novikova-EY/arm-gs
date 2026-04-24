# -*- coding: utf-8 -*-
"""ГЭС/ГАЭС: срок строительства — numeric(12,1) вместо integer.

Revision ID: r3s4t5u6v7w8
Revises: p1q2r3s4t5u6
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa

revision = "r3s4t5u6v7w8"
down_revision = "p1q2r3s4t5u6"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"


def upgrade():
    for table, col in (
        ("station_prospective_place_ges", "construction_period_years"),
        ("station_prospective_place_gaes", "construction_period_years"),
        ("ges_tep_source_project_indicators", "construction_period_years"),
        ("gaes_tep_source_project_indicators", "construction_period_years"),
    ):
        op.alter_column(
            table,
            col,
            type_=sa.Numeric(12, 1),
            schema=SCHEMA_GEN,
            postgresql_using=f"{col}::numeric(12,1)",
        )


def downgrade():
    for table, col in (
        ("station_prospective_place_ges", "construction_period_years"),
        ("station_prospective_place_gaes", "construction_period_years"),
        ("ges_tep_source_project_indicators", "construction_period_years"),
        ("gaes_tep_source_project_indicators", "construction_period_years"),
    ):
        op.alter_column(
            table,
            col,
            type_=sa.Integer(),
            schema=SCHEMA_GEN,
            postgresql_using=f"round({col})::integer",
        )

# -*- coding: utf-8 -*-
"""station_prospective_place_ges/gaes: порядок отображения (display_order).

Revision ID: p1q2r3s4t5u6
Revises: c6d7e8f9a0b1
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa

revision = "p1q2r3s4t5u6"
down_revision = "c6d7e8f9a0b1"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE_GES = "station_prospective_place_ges"
TABLE_GAES = "station_prospective_place_gaes"


def upgrade():
    op.add_column(
        TABLE_GES,
        sa.Column("display_order", sa.Integer(), nullable=True),
        schema=SCHEMA_GEN,
    )
    op.add_column(
        TABLE_GAES,
        sa.Column("display_order", sa.Integer(), nullable=True),
        schema=SCHEMA_GEN,
    )


def downgrade():
    op.drop_column(TABLE_GAES, "display_order", schema=SCHEMA_GEN)
    op.drop_column(TABLE_GES, "display_order", schema=SCHEMA_GEN)

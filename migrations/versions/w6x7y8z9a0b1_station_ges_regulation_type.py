# -*- coding: utf-8 -*-
"""station_prospective_place_ges: поле regulation_type (вид регулирования).

Revision ID: w6x7y8z9a0b1
Revises: v5w6x7y8z9a0
Create Date: 2026-04-13
"""
from alembic import op
import sqlalchemy as sa


revision = "w6x7y8z9a0b1"
down_revision = "v5w6x7y8z9a0"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE = "station_prospective_place_ges"


def upgrade():
    op.add_column(
        TABLE,
        sa.Column("regulation_type", sa.String(length=500), nullable=True),
        schema=SCHEMA_GEN,
    )


def downgrade():
    op.drop_column(TABLE, "regulation_type", schema=SCHEMA_GEN)

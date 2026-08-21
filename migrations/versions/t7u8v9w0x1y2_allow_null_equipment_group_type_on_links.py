# -*- coding: utf-8 -*-
"""Allow NULL equipment_group_type_id for composite-station shell links.

Revision ID: t7u8v9w0x1y2
Revises: sn1ee2te3f4a5
Create Date: 2026-08-14
"""
from alembic import op
import sqlalchemy as sa


revision = "t7u8v9w0x1y2"
down_revision = "sn1ee2te3f4a5"
branch_labels = None
depends_on = None

SCHEMA_FUEL = "gs_fue"
TABLE = "gs_fue_equipment_group_type_stations"
COLUMN = "equipment_group_type_id"


def upgrade():
    op.alter_column(
        TABLE,
        COLUMN,
        existing_type=sa.Integer(),
        nullable=True,
        schema=SCHEMA_FUEL,
    )


def downgrade():
    op.alter_column(
        TABLE,
        COLUMN,
        existing_type=sa.Integer(),
        nullable=False,
        schema=SCHEMA_FUEL,
    )

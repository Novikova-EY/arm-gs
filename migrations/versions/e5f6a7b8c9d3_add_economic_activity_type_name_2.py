# -*- coding: utf-8 -*-
"""ВЭД: добавить поле name_2 (Вид экономической деятельности_2).

Revision ID: e5f6a7b8c9d3
Revises: d4e5f6a7b8c2
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d3"
down_revision = "d4e5f6a7b8c2"
branch_labels = None
depends_on = None

SCHEMA_REF = "gs_sys"
TABLE = "gs_sys_economic_activity_types"
COLUMN = "name_2"


def upgrade():
    op.add_column(
        TABLE,
        sa.Column(COLUMN, sa.String(length=255), nullable=True),
        schema=SCHEMA_REF,
    )


def downgrade():
    op.drop_column(TABLE, COLUMN, schema=SCHEMA_REF)

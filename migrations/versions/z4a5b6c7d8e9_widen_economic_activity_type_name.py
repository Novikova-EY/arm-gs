# -*- coding: utf-8 -*-
"""ВЭД: расширить поле name до 255 символов (как в формах).

Revision ID: z4a5b6c7d8e9
Revises: y3z4a5b6c7d8
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "z4a5b6c7d8e9"
down_revision = "y3z4a5b6c7d8"
branch_labels = None
depends_on = None

SCHEMA_REF = "gs_sys"
TABLE = "gs_sys_economic_activity_types"
COLUMN = "name"


def upgrade():
    op.alter_column(
        TABLE,
        COLUMN,
        existing_type=sa.String(length=80),
        type_=sa.String(length=255),
        existing_nullable=True,
        schema=SCHEMA_REF,
    )


def downgrade():
    op.alter_column(
        TABLE,
        COLUMN,
        existing_type=sa.String(length=255),
        type_=sa.String(length=80),
        existing_nullable=True,
        schema=SCHEMA_REF,
    )

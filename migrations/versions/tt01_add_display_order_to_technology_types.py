"""add display_order to gs_technology_types

Revision ID: tt01dispord
Revises: z2a3b4c5d6e7
Create Date: 2026-02-27

Поле порядок отображения для типов технологий (TechnologyType).
"""
from alembic import op
import sqlalchemy as sa
from config import SCHEMA_REFDATA

revision = "tt01dispord"
down_revision = "z2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "gs_technology_types",
        sa.Column("display_order", sa.Integer(), nullable=True),
        schema=SCHEMA_REFDATA,
    )


def downgrade():
    op.drop_column("gs_technology_types", "display_order", schema=SCHEMA_REFDATA)

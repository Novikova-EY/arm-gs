"""add_service_life_construction_period_to_machine_prospective_place_aes

Revision ID: z8a9b0c1d2e3
Revises: y7z8a9b0c1d2
Create Date: 2026-03-20

Добавляет поля service_life_years (срок эксплуатации АЭС, лет)
и construction_period_years (срок строительства АЭС, лет) в machine_prospective_place_aes.
"""
from alembic import op
import sqlalchemy as sa


revision = "z8a9b0c1d2e3"
down_revision = "y7z8a9b0c1d2"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE = "machine_prospective_place_aes"


def upgrade():
    op.add_column(
        TABLE,
        sa.Column("service_life_years", sa.Integer(), nullable=True),
        schema=SCHEMA_GEN,
    )
    op.add_column(
        TABLE,
        sa.Column("construction_period_years", sa.Integer(), nullable=True),
        schema=SCHEMA_GEN,
    )


def downgrade():
    op.drop_column(TABLE, "service_life_years", schema=SCHEMA_GEN)
    op.drop_column(TABLE, "construction_period_years", schema=SCHEMA_GEN)

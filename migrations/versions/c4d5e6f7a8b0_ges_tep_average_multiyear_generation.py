"""ges_tep_average_multiyear_generation

Revision ID: c4d5e6f7a8b0
Revises: b3c4d5e6f7a9
Create Date: 2026-03-30

Среднемноголетняя выработка электроэнергии, млрд кВт·ч в ges_tep_source_project_indicators.
"""
from alembic import op
import sqlalchemy as sa


revision = "c4d5e6f7a8b0"
down_revision = "b3c4d5e6f7a9"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE_TEP = "ges_tep_source_project_indicators"


def upgrade():
    op.add_column(
        TABLE_TEP,
        sa.Column(
            "generation_average_multiyear_billion_kwh",
            sa.String(length=100),
            nullable=True,
        ),
        schema=SCHEMA_GEN,
    )


def downgrade():
    op.drop_column(
        TABLE_TEP,
        "generation_average_multiyear_billion_kwh",
        schema=SCHEMA_GEN,
    )

"""add ues external name/abbr

Revision ID: a1b2c3d4e5f6
Revises: f4a5b6c7d8e9
Create Date: 2026-01-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "gs_fue_em_union_energy_system",
        sa.Column("external_nameoes", sa.String(length=255), nullable=True),
        schema=SCHEMA_FUEL,
    )
    op.add_column(
        "gs_fue_em_union_energy_system",
        sa.Column("external_abbr", sa.String(length=255), nullable=True),
        schema=SCHEMA_FUEL,
    )


def downgrade():
    op.drop_column(
        "gs_fue_em_union_energy_system",
        "external_abbr",
        schema=SCHEMA_FUEL,
    )
    op.drop_column(
        "gs_fue_em_union_energy_system",
        "external_nameoes",
        schema=SCHEMA_FUEL,
    )

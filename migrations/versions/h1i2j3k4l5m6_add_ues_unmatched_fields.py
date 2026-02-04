"""add ues unmatched fields

Revision ID: h1i2j3k4l5m6
Revises: g1h2i3j4k5l6
Create Date: 2026-01-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "h1i2j3k4l5m6"
down_revision = "g1h2i3j4k5l6"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "gs_fue_em_union_energy_system",
        "union_energy_system_ref_uuid",
        existing_type=sa.String(length=36),
        nullable=True,
        schema=SCHEMA_FUEL,
    )
    op.add_column(
        "gs_fue_em_union_energy_system",
        sa.Column("local_name", sa.String(length=255), nullable=True),
        schema=SCHEMA_FUEL,
    )


def downgrade():
    op.drop_column(
        "gs_fue_em_union_energy_system",
        "local_name",
        schema=SCHEMA_FUEL,
    )
    op.alter_column(
        "gs_fue_em_union_energy_system",
        "union_energy_system_ref_uuid",
        existing_type=sa.String(length=36),
        nullable=False,
        schema=SCHEMA_FUEL,
    )

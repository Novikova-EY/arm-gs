"""add short names to fuel types

Revision ID: 1d2e3f4a5b6c
Revises: 6a7b8c9d0e11
Create Date: 2026-01-26 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "1d2e3f4a5b6c"
down_revision = "6a7b8c9d0e11"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "gs_fuel_types",
        sa.Column("topl_nazvl", sa.String(length=80), nullable=True),
        schema=SCHEMA_REFDATA,
    )
    op.add_column(
        "gs_fuel_types",
        sa.Column("topl_kmbur", sa.String(length=80), nullable=True),
        schema=SCHEMA_REFDATA,
    )


def downgrade():
    op.drop_column("gs_fuel_types", "topl_kmbur", schema=SCHEMA_REFDATA)
    op.drop_column("gs_fuel_types", "topl_nazvl", schema=SCHEMA_REFDATA)

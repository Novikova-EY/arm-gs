"""add topl_kmbur to fuel types

Revision ID: 5b6c7d8e9f0a
Revises: 4a5b6c7d8e9f
Create Date: 2026-01-26 11:10:00.000000
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "5b6c7d8e9f0a"
down_revision = "4a5b6c7d8e9f"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "gs_fuel_types",
        sa.Column("topl_kmbur", sa.String(length=80), nullable=True),
        schema=SCHEMA_REFDATA,
    )


def downgrade():
    op.drop_column("gs_fuel_types", "topl_kmbur", schema=SCHEMA_REFDATA)

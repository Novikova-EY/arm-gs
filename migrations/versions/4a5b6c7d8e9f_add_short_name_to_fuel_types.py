"""add short name to fuel types

Revision ID: 4a5b6c7d8e9f
Revises: 3f4a5b6c7d8e
Create Date: 2026-01-26 10:25:00.000000
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "4a5b6c7d8e9f"
down_revision = "3f4a5b6c7d8e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "gs_fuel_types",
        sa.Column("topl_nazvl", sa.String(length=80), nullable=True),
        schema=SCHEMA_REFDATA,
    )


def downgrade():
    op.drop_column("gs_fuel_types", "topl_nazvl", schema=SCHEMA_REFDATA)

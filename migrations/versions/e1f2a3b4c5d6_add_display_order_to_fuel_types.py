"""add display_order to fuel types

Revision ID: e1f2a3b4c5d6
Revises: a4b5c6d7e8f9
Create Date: 2026-02-03 14:05:00.000000
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "e1f2a3b4c5d6"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "gs_fuel_types",
        sa.Column("display_order", sa.Integer(), nullable=True),
        schema=SCHEMA_REFDATA,
    )


def downgrade():
    op.drop_column("gs_fuel_types", "display_order", schema=SCHEMA_REFDATA)


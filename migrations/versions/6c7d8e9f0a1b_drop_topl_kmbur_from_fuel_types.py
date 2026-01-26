"""drop topl_kmbur from fuel types

Revision ID: 6c7d8e9f0a1b
Revises: 5b6c7d8e9f0a
Create Date: 2026-01-26 13:10:00.000000
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "6c7d8e9f0a1b"
down_revision = "5b6c7d8e9f0a"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("gs_fuel_types", "topl_kmbur", schema=SCHEMA_REFDATA)


def downgrade():
    op.add_column(
        "gs_fuel_types",
        sa.Column("topl_kmbur", sa.String(length=80), nullable=True),
        schema=SCHEMA_REFDATA,
    )

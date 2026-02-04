"""allow null federal district uuid

Revision ID: j1k2l3m4n5o6
Revises: i1j2k3l4m5n6
Create Date: 2026-01-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "j1k2l3m4n5o6"
down_revision = "i1j2k3l4m5n6"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "gs_fue_em_federal_district",
        "federal_district_ref_uuid",
        existing_type=sa.String(length=36),
        nullable=True,
        schema=SCHEMA_FUEL,
    )


def downgrade():
    op.alter_column(
        "gs_fue_em_federal_district",
        "federal_district_ref_uuid",
        existing_type=sa.String(length=36),
        nullable=False,
        schema=SCHEMA_FUEL,
    )

"""drop ues local_name

Revision ID: i1j2k3l4m5n6
Revises: h1i2j3k4l5m6
Create Date: 2026-01-29 00:00:00.000000
"""

from alembic import op

from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "i1j2k3l4m5n6"
down_revision = "h1i2j3k4l5m6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_fue_em_union_energy_system "
        "DROP COLUMN IF EXISTS local_name"
    )


def downgrade():
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_fue_em_union_energy_system "
        "ADD COLUMN IF NOT EXISTS local_name varchar(255)"
    )

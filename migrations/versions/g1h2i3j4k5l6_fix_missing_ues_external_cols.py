"""ensure ues external columns exist

Revision ID: g1h2i3j4k5l6
Revises: a1b2c3d4e5f6
Create Date: 2026-01-29 00:00:00.000000
"""

from alembic import op
from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "g1h2i3j4k5l6"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_fue_em_union_energy_system "
        "ADD COLUMN IF NOT EXISTS external_nameoes varchar(255)"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_fue_em_union_energy_system "
        "ADD COLUMN IF NOT EXISTS external_abbr varchar(255)"
    )


def downgrade():
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_fue_em_union_energy_system "
        "DROP COLUMN IF EXISTS external_abbr"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_fue_em_union_energy_system "
        "DROP COLUMN IF EXISTS external_nameoes"
    )

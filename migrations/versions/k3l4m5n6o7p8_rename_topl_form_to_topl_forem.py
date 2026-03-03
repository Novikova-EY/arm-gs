"""rename topl_form to topl_forem

Revision ID: k3l4m5n6o7p8
Revises: j2k3l4m5n6o7
Create Date: 2026-02-19 15:00:00.000000
"""

from alembic import op
from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "k3l4m5n6o7p8"
down_revision = "j2k3l4m5n6o7"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "gs_fue_equipment_group_sets",
        "topl_form",
        new_column_name="topl_forem",
        schema=SCHEMA_FUEL,
    )


def downgrade():
    op.alter_column(
        "gs_fue_equipment_group_sets",
        "topl_forem",
        new_column_name="topl_form",
        schema=SCHEMA_FUEL,
    )

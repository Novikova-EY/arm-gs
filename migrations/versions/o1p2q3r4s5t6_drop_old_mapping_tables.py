"""drop old regional mapping tables

Revision ID: o1p2q3r4s5t6
Revises: n1o2p3q4r5s6
Create Date: 2026-01-29 00:00:00.000000
"""

from alembic import op
from sqlalchemy import inspect
from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "o1p2q3r4s5t6"
down_revision = "n1o2p3q4r5s6"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    for table_name in [
        "gs_fue_em_regional_district",
        "gs_fue_em_regional_energy_system",
        "gs_fue_em_energy_zone",
    ]:
        if inspector.has_table(table_name, schema=SCHEMA_FUEL):
            op.drop_table(table_name, schema=SCHEMA_FUEL)


def downgrade():
    # Tables were removed; no automatic restore.
    pass

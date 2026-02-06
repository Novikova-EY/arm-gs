"""add display_order to several refdata types

Revision ID: 0123abcd4567
Revises: e1f2a3b4c5d6
Create Date: 2026-02-05 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "0123abcd4567"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade():
    tables = [
        "gs_synchronous_areas",
        "gs_station_types",
        "gs_tes_types",
        "gs_tes_machine_types",
    ]

    for table in tables:
        op.add_column(
            table,
            sa.Column("display_order", sa.Integer(), nullable=True),
            schema=SCHEMA_REFDATA,
        )


def downgrade():
    tables = [
        "gs_synchronous_areas",
        "gs_station_types",
        "gs_tes_types",
        "gs_tes_machine_types",
    ]

    for table in tables:
        op.drop_column(table, "display_order", schema=SCHEMA_REFDATA)


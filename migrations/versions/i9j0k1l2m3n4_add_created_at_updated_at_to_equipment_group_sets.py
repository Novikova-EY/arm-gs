"""add created_at, updated_at to equipment group sets

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-02-19 13:00:00.000000

Добавляет поля created_at и updated_at (UTC, server-side) в таблицы
gs_fue_equipment_group_sets и gs_fue_equipment_group_set_stations.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func
from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "i9j0k1l2m3n4"
down_revision = "h8i9j0k1l2m3"
branch_labels = None
depends_on = None


def upgrade():
    """Добавляет created_at и updated_at в таблицы equipment group sets."""
    for table_name in ("gs_fue_equipment_group_sets", "gs_fue_equipment_group_set_stations"):
        op.add_column(
            table_name,
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=func.now(),
                nullable=False,
            ),
            schema=SCHEMA_FUEL,
        )
        op.add_column(
            table_name,
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=func.now(),
                nullable=False,
            ),
            schema=SCHEMA_FUEL,
        )


def downgrade():
    """Удаляет created_at и updated_at из таблиц equipment group sets."""
    for table_name in ("gs_fue_equipment_group_sets", "gs_fue_equipment_group_set_stations"):
        op.drop_column(table_name, "updated_at", schema=SCHEMA_FUEL)
        op.drop_column(table_name, "created_at", schema=SCHEMA_FUEL)

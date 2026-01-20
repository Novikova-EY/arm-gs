"""remove equipment_group external_code

Revision ID: a9d1c2b3e4f5
Revises: f6a1b2c3d4e6
Create Date: 2026-01-16 13:15:00.000000

Убирает external_code из refdata.gs_equipment_groups (не требуется для интеграции).
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "a9d1c2b3e4f5"
down_revision = "f6a1b2c3d4e6"
branch_labels = None
depends_on = None


def upgrade():
    # Индекс мог быть создан в предыдущей миграции
    op.drop_index(
        "ix_equipment_group_external_code",
        table_name="gs_equipment_groups",
        schema=SCHEMA_REFDATA,
    )

    op.drop_column("gs_equipment_groups", "external_code", schema=SCHEMA_REFDATA)


def downgrade():
    op.add_column(
        "gs_equipment_groups",
        sa.Column("external_code", sa.String(36), nullable=True),
        schema=SCHEMA_REFDATA,
    )
    op.create_index(
        "ix_equipment_group_external_code",
        "gs_equipment_groups",
        ["external_code"],
        unique=False,
        schema=SCHEMA_REFDATA,
    )

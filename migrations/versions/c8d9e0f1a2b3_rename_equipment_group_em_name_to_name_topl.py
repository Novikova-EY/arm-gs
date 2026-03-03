"""rename equipment_group external mapping name to name_topl

Revision ID: c8d9e0f1a2b3
Revises: b2c3d4e5f6g7
Create Date: 2026-02-26

Возвращает колонку name в name_topl в gs_fue_em_equipment_group
(соответствие наименованию в Excel и другим mapping-таблицам).
"""

from alembic import op
from config import SCHEMA_FUE_EM


revision = "c8d9e0f1a2b3"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None

TABLE = "gs_fue_em_equipment_group"


def upgrade():
    op.alter_column(
        TABLE,
        "name",
        new_column_name="name_topl",
        schema=SCHEMA_FUE_EM,
    )


def downgrade():
    op.alter_column(
        TABLE,
        "name_topl",
        new_column_name="name",
        schema=SCHEMA_FUE_EM,
    )

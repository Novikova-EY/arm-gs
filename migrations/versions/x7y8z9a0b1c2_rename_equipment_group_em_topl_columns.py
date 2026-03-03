"""rename equipment_group external mapping _topl columns

Revision ID: x7y8z9a0b1c2
Revises: z2a3b4c5d6e7, v0w1x2y3z4a5b6
Create Date: 2026-02-26

Удаляет суффикс _topl из наименований колонок в gs_fue_em_equipment_group.
"""

from alembic import op
from config import SCHEMA_FUE_EM


revision = "x7y8z9a0b1c2"
down_revision = ("z2a3b4c5d6e7", "v0w1x2y3z4a5b6")
branch_labels = None
depends_on = None

TABLE = "gs_fue_em_equipment_group"


def upgrade():
    # Переименование колонок: убираем суффикс _topl
    op.alter_column(
        TABLE,
        "name_topl",
        new_column_name="name",
        schema=SCHEMA_FUE_EM,
    )
    op.alter_column(
        TABLE,
        "code_topl",
        new_column_name="code",
        schema=SCHEMA_FUE_EM,
    )
    op.alter_column(
        TABLE,
        "type_topl",
        new_column_name="type",
        schema=SCHEMA_FUE_EM,
    )
    op.alter_column(
        TABLE,
        "tm_topl",
        new_column_name="tm",
        schema=SCHEMA_FUE_EM,
    )
    op.alter_column(
        TABLE,
        "n1_topl",
        new_column_name="n1",
        schema=SCHEMA_FUE_EM,
    )
    op.alter_column(
        TABLE,
        "n2_topl",
        new_column_name="n2",
        schema=SCHEMA_FUE_EM,
    )
    op.alter_column(
        TABLE,
        "p1_topl",
        new_column_name="p1",
        schema=SCHEMA_FUE_EM,
    )
    op.alter_column(
        TABLE,
        "p2_topl",
        new_column_name="p2",
        schema=SCHEMA_FUE_EM,
    )
    op.alter_column(
        TABLE,
        "gruppa_oborud_topl",
        new_column_name="gruppa_oborud",
        schema=SCHEMA_FUE_EM,
    )
    # Переименовать индекс с code_topl на code
    op.execute(
        f"ALTER INDEX IF EXISTS {SCHEMA_FUE_EM}.ix_fue_em_eq_group_code_topl "
        f"RENAME TO ix_fue_em_eq_group_code"
    )


def downgrade():
    op.execute(
        f"ALTER INDEX IF EXISTS {SCHEMA_FUE_EM}.ix_fue_em_eq_group_code "
        f"RENAME TO ix_fue_em_eq_group_code_topl"
    )
    op.alter_column(
        TABLE,
        "name",
        new_column_name="name_topl",
        schema=SCHEMA_FUE_EM,
    )
    op.alter_column(
        TABLE,
        "code",
        new_column_name="code_topl",
        schema=SCHEMA_FUE_EM,
    )
    op.alter_column(
        TABLE,
        "type",
        new_column_name="type_topl",
        schema=SCHEMA_FUE_EM,
    )
    op.alter_column(
        TABLE,
        "tm",
        new_column_name="tm_topl",
        schema=SCHEMA_FUE_EM,
    )
    op.alter_column(
        TABLE,
        "n1",
        new_column_name="n1_topl",
        schema=SCHEMA_FUE_EM,
    )
    op.alter_column(
        TABLE,
        "n2",
        new_column_name="n2_topl",
        schema=SCHEMA_FUE_EM,
    )
    op.alter_column(
        TABLE,
        "p1",
        new_column_name="p1_topl",
        schema=SCHEMA_FUE_EM,
    )
    op.alter_column(
        TABLE,
        "p2",
        new_column_name="p2_topl",
        schema=SCHEMA_FUE_EM,
    )
    op.alter_column(
        TABLE,
        "gruppa_oborud",
        new_column_name="gruppa_oborud_topl",
        schema=SCHEMA_FUE_EM,
    )

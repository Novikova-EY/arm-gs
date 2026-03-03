"""add topl_agr_grcode FK to EquipmentGroupExternalMapping

Revision ID: z2a3b4c5d6e7
Revises: e55f58bb4b49
Create Date: 2026-02-26

Связывает поле topl_agr_grcode в gs_fue_machine_toplivo_param
с gs_fue_em_equipment_group.id (EquipmentGroupExternalMapping).

Конвертация данных: если topl_agr_grcode хранит code_topl из БД Топливо,
заменяем на id соответствующей записи EquipmentGroupExternalMapping.
Несовпадающие значения обнуляем.
"""

from alembic import op
from config import SCHEMA_FUEL, SCHEMA_FUE_EM


# revision identifiers, used by Alembic.
revision = "z2a3b4c5d6e7"
down_revision = "e55f58bb4b49"
branch_labels = None
depends_on = None

TABLE = "gs_fue_machine_toplivo_param"
SCHEMA = SCHEMA_FUEL
EM_TABLE = "gs_fue_em_equipment_group"
EM_SCHEMA = SCHEMA_FUE_EM


def upgrade():
    # 1. Конвертация: topl_agr_grcode (code_topl) -> id из EquipmentGroupExternalMapping
    op.execute(
        f"""
        UPDATE {SCHEMA}.{TABLE} mtp
        SET topl_agr_grcode = (
            SELECT eg.id FROM {EM_SCHEMA}.{EM_TABLE} eg
            WHERE eg.code_topl = mtp.topl_agr_grcode
            LIMIT 1
        )
        WHERE mtp.topl_agr_grcode IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM {EM_SCHEMA}.{EM_TABLE} eg
              WHERE eg.code_topl = mtp.topl_agr_grcode
          )
        """
    )

    # 2. Обнулить значения, для которых нет соответствующей записи в mapping
    op.execute(
        f"""
        UPDATE {SCHEMA}.{TABLE} mtp
        SET topl_agr_grcode = NULL
        WHERE mtp.topl_agr_grcode IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM {EM_SCHEMA}.{EM_TABLE} eg
              WHERE eg.id = mtp.topl_agr_grcode
          )
        """
    )

    # 3. Добавить FK и индекс
    op.create_foreign_key(
        "fk_machine_toplivo_param_topl_agr_grcode",
        TABLE,
        EM_TABLE,
        ["topl_agr_grcode"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=EM_SCHEMA,
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_gs_fue_machine_toplivo_param_topl_agr_grcode",
        TABLE,
        ["topl_agr_grcode"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade():
    op.drop_constraint(
        "fk_machine_toplivo_param_topl_agr_grcode",
        TABLE,
        type_="foreignkey",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_gs_fue_machine_toplivo_param_topl_agr_grcode",
        table_name=TABLE,
        schema=SCHEMA,
    )

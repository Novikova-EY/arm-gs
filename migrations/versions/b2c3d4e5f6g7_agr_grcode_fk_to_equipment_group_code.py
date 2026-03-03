"""change agr_grcode FK from EquipmentGroupExternalMapping.id to .code

Revision ID: b2c3d4e5f6g7
Revises: e4f5a6b7c8d9
Create Date: 2026-02-26

Связывает MachineFuelParam.agr_grcode с EquipmentGroupExternalMapping.code
вместо id. Конвертирует существующие данные (agr_grcode хранит id -> заменяем на code).
"""

from alembic import op
from config import SCHEMA_FUEL, SCHEMA_FUE_EM


revision = "b2c3d4e5f6g7"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None

TABLE = "gs_fue_machine_fuel_param"
EM_TABLE = "gs_fue_em_equipment_group"


def upgrade():
    # UNIQUE на code уже создан в e4f5a6b7c8d9

    # 1. Конвертация: agr_grcode (id) -> code
    op.execute(
        f"""
        UPDATE {SCHEMA_FUEL}.{TABLE} mfp
        SET agr_grcode = (
            SELECT eg.code FROM {SCHEMA_FUE_EM}.{EM_TABLE} eg
            WHERE eg.id = mfp.agr_grcode
            LIMIT 1
        )
        WHERE mfp.agr_grcode IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM {SCHEMA_FUE_EM}.{EM_TABLE} eg
              WHERE eg.id = mfp.agr_grcode
          )
        """
    )

    # 3. Обнулить значения, для которых нет соответствующей записи
    op.execute(
        f"""
        UPDATE {SCHEMA_FUEL}.{TABLE} mfp
        SET agr_grcode = NULL
        WHERE mfp.agr_grcode IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM {SCHEMA_FUE_EM}.{EM_TABLE} eg
              WHERE eg.code = mfp.agr_grcode
          )
        """
    )

    # 4. Удалить старый FK и создать новый (agr_grcode -> code)
    op.drop_constraint(
        "fk_machine_fuel_param_agr_grcode",
        TABLE,
        type_="foreignkey",
        schema=SCHEMA_FUEL,
    )
    op.create_foreign_key(
        "fk_machine_fuel_param_agr_grcode",
        TABLE,
        EM_TABLE,
        ["agr_grcode"],
        ["code"],
        source_schema=SCHEMA_FUEL,
        referent_schema=SCHEMA_FUE_EM,
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint(
        "fk_machine_fuel_param_agr_grcode",
        TABLE,
        type_="foreignkey",
        schema=SCHEMA_FUEL,
    )

    # Конвертация: agr_grcode (code) -> id
    op.execute(
        f"""
        UPDATE {SCHEMA_FUEL}.{TABLE} mfp
        SET agr_grcode = (
            SELECT eg.id FROM {SCHEMA_FUE_EM}.{EM_TABLE} eg
            WHERE eg.code = mfp.agr_grcode
            LIMIT 1
        )
        WHERE mfp.agr_grcode IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM {SCHEMA_FUE_EM}.{EM_TABLE} eg
              WHERE eg.code = mfp.agr_grcode
          )
        """
    )

    op.execute(
        f"""
        UPDATE {SCHEMA_FUEL}.{TABLE} mfp
        SET agr_grcode = NULL
        WHERE mfp.agr_grcode IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM {SCHEMA_FUE_EM}.{EM_TABLE} eg
              WHERE eg.id = mfp.agr_grcode
          )
        """
    )

    op.create_foreign_key(
        "fk_machine_fuel_param_agr_grcode",
        TABLE,
        EM_TABLE,
        ["agr_grcode"],
        ["id"],
        source_schema=SCHEMA_FUEL,
        referent_schema=SCHEMA_FUE_EM,
        ondelete="SET NULL",
    )

"""grcode FK: EquipmentGroupExternalMapping.code -> EquipmentGroupSet.numb

Revision ID: q8r9s0t1u2v3
Revises: p7q8r9s0t1u2
Create Date: 2026-02-26

Меняет привязку MachineFuelParam.grcode с EquipmentGroupExternalMapping.code
на EquipmentGroupSet.numb. Колонка grcode: Integer -> String(255).
Без FK в БД (numb может быть неуникальным), только связь в модели.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUEL, SCHEMA_FUE_EM


revision = "q8r9s0t1u2v3"
down_revision = "p7q8r9s0t1u2"
branch_labels = None
depends_on = None

TABLE = "gs_fue_machine_fuel_param"
EM_TABLE = "gs_fue_em_equipment_group"


def upgrade():
    # 1. Удалить FK и индекс на grcode
    op.drop_constraint(
        "fk_machine_fuel_param_grcode",
        TABLE,
        type_="foreignkey",
        schema=SCHEMA_FUEL,
    )
    op.drop_index(
        "ix_gs_fue_machine_fuel_param_grcode",
        table_name=TABLE,
        schema=SCHEMA_FUEL,
    )

    # 2. Изменить тип колонки Integer -> String(255)
    op.alter_column(
        TABLE,
        "grcode",
        existing_type=sa.Integer(),
        type_=sa.String(255),
        schema=SCHEMA_FUEL,
        postgresql_using="grcode::varchar(255)",
    )

    # 3. Создать индекс (без FK — numb может быть неуникальным)
    op.create_index(
        "ix_gs_fue_machine_fuel_param_grcode",
        TABLE,
        ["grcode"],
        unique=False,
        schema=SCHEMA_FUEL,
    )


def downgrade():
    # 1. Удалить индекс
    op.drop_index(
        "ix_gs_fue_machine_fuel_param_grcode",
        table_name=TABLE,
        schema=SCHEMA_FUEL,
    )

    # 2. Изменить тип String -> Integer (нечисловые значения станут NULL)
    op.alter_column(
        TABLE,
        "grcode",
        existing_type=sa.String(255),
        type_=sa.Integer(),
        schema=SCHEMA_FUEL,
        postgresql_using="NULLIF(REGEXP_REPLACE(TRIM(grcode), '[^0-9]', '', 'g'), '')::integer",
    )

    # 3. Обнулить grcode, не существующие в EquipmentGroupExternalMapping.code
    op.execute(
        f"""
        UPDATE {SCHEMA_FUEL}.{TABLE} mfp
        SET grcode = NULL
        WHERE mfp.grcode IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM {SCHEMA_FUE_EM}.{EM_TABLE} eg
              WHERE eg.code = mfp.grcode
          )
        """
    )

    # 4. Создать FK и индекс
    op.create_foreign_key(
        "fk_machine_fuel_param_grcode",
        TABLE,
        EM_TABLE,
        ["grcode"],
        ["code"],
        source_schema=SCHEMA_FUEL,
        referent_schema=SCHEMA_FUE_EM,
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_gs_fue_machine_fuel_param_grcode",
        TABLE,
        ["grcode"],
        unique=False,
        schema=SCHEMA_FUEL,
    )

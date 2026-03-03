"""add EquipmentGroupFuelParam FKs to external mapping tables

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-02-26

Добавляет FK-связи полей gs_fue_equipment_group_fuel_param с таблицами external mapping:
- obor -> gs_fue_em_equipment_group.code (Integer)
- obl, dep, oes, er, gk, be: конвертация Integer->String(80) и FK на external_id
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUEL, SCHEMA_FUE_EM


revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None

TABLE = "gs_fue_equipment_group_fuel_param"
SCHEMA = SCHEMA_FUEL

# obor -> equipment_group (оба Integer)
EQ_GROUP_TABLE = "gs_fue_em_equipment_group"
EQ_GROUP_SCHEMA = SCHEMA_FUE_EM

# obl, dep, oes, er, gk, be -> external_id (String)
MAPPINGS = [
    ("obl", "gs_fue_em_territories_energy", "external_id"),
    ("dep", "gs_fue_em_department", "external_id"),
    ("oes", "gs_fue_em_union_energy_system", "external_id"),
    ("er", "gs_fue_em_economic_region", "external_id"),
    ("gk", "gs_fue_em_gen_company", "external_id"),
    ("be", "gs_fue_em_business_unit", "external_id"),
]


def upgrade():
    # 0. UNIQUE на целевых колонках (нужны для FK)
    op.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_fue_em_equipment_group_code "
        f"ON {EQ_GROUP_SCHEMA}.{EQ_GROUP_TABLE} (code)"
    )
    op.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_fue_em_business_unit_external_id "
        f"ON {SCHEMA_FUE_EM}.gs_fue_em_business_unit (external_id)"
    )

    # 1. obor -> EquipmentGroupExternalMapping.code (оба Integer)
    op.execute(
        f"""
        UPDATE {SCHEMA}.{TABLE} p
        SET obor = NULL
        WHERE p.obor IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM {EQ_GROUP_SCHEMA}.{EQ_GROUP_TABLE} eg
              WHERE eg.code = p.obor
          )
        """
    )
    op.create_foreign_key(
        "fk_equipment_group_fuel_param_obor",
        TABLE,
        EQ_GROUP_TABLE,
        ["obor"],
        ["code"],
        source_schema=SCHEMA,
        referent_schema=EQ_GROUP_SCHEMA,
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_gs_fue_equipment_group_fuel_param_obor",
        TABLE,
        ["obor"],
        unique=False,
        schema=SCHEMA,
    )

    # 2. obl, dep, oes, er, gk, be: Integer -> String(80), обнулить невалидные, добавить FK
    for col, ref_table, ref_col in MAPPINGS:
        # Обнулить значения, которых нет в ref_table
        op.execute(
            f"""
            UPDATE {SCHEMA}.{TABLE} p
            SET {col} = NULL
            WHERE p.{col} IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM {SCHEMA_FUE_EM}.{ref_table} r
                  WHERE r.{ref_col} = p.{col}::text
              )
            """
        )
        # Конвертировать Integer -> String(80)
        op.execute(
            f"""
            ALTER TABLE {SCHEMA}.{TABLE}
            ALTER COLUMN {col} TYPE VARCHAR(80) USING {col}::text
            """
        )
        op.create_foreign_key(
            f"fk_equipment_group_fuel_param_{col}",
            TABLE,
            ref_table,
            [col],
            [ref_col],
            source_schema=SCHEMA,
            referent_schema=SCHEMA_FUE_EM,
            ondelete="SET NULL",
        )
        op.create_index(
            f"ix_gs_fue_equipment_group_fuel_param_{col}",
            TABLE,
            [col],
            unique=False,
            schema=SCHEMA,
        )


def downgrade():
    # Удалить FK и индексы для obl, dep, oes, er, gk, be; вернуть Integer
    for col, ref_table, ref_col in reversed(MAPPINGS):
        op.drop_constraint(
            f"fk_equipment_group_fuel_param_{col}",
            TABLE,
            type_="foreignkey",
            schema=SCHEMA,
        )
        op.drop_index(
            f"ix_gs_fue_equipment_group_fuel_param_{col}",
            table_name=TABLE,
            schema=SCHEMA,
        )
        op.execute(
            f"""
            ALTER TABLE {SCHEMA}.{TABLE}
            ALTER COLUMN {col} TYPE INTEGER USING NULLIF(TRIM({col}), '')::integer
            """
        )

    op.drop_index(
        "ix_gs_fue_equipment_group_fuel_param_obor",
        table_name=TABLE,
        schema=SCHEMA,
    )
    op.drop_constraint(
        "fk_equipment_group_fuel_param_obor",
        TABLE,
        type_="foreignkey",
        schema=SCHEMA,
    )

    op.execute(
        f"DROP INDEX IF EXISTS {EQ_GROUP_SCHEMA}.uq_gs_fue_em_equipment_group_code"
    )
    op.execute(
        f"DROP INDEX IF EXISTS {SCHEMA_FUE_EM}.uq_gs_fue_em_business_unit_external_id"
    )

"""remove agr_ prefix from MachineFuelParam columns

Revision ID: p7q8r9s0t1u2
Revises: 9f6aa0aab622
Create Date: 2026-02-26

Переименовывает колонки agr_* в MachineFuelParam в колонки без префикса agr_.
"""

from alembic import op
from config import SCHEMA_FUEL, SCHEMA_FUE_EM


revision = "p7q8r9s0t1u2"
down_revision = "9f6aa0aab622"
branch_labels = None
depends_on = None

TABLE = "gs_fue_machine_fuel_param"
EM_TABLE = "gs_fue_em_equipment_group"

COLUMN_RENAMES = [
    ("agr_numb", "numb"),
    ("agr_stnumb", "stnumb"),
    ("agr_yearin", "yearin"),
    ("agr_dem", "dem"),
    ("agr_nt", "nt"),
    ("agr_numb1120", "numb1120"),
    ("agr_grcode", "grcode"),
    ("agr_stname", "stname"),
    ("agr_opesname", "opesname"),
    ("agr_note", "note"),
]


def upgrade():
    # 1. Удалить FK и индекс на agr_grcode
    op.drop_constraint(
        "fk_machine_fuel_param_agr_grcode",
        TABLE,
        type_="foreignkey",
        schema=SCHEMA_FUEL,
    )
    op.drop_index(
        "ix_gs_fue_machine_fuel_param_agr_grcode",
        table_name=TABLE,
        schema=SCHEMA_FUEL,
    )

    # 2. Переименовать колонки
    for old_name, new_name in COLUMN_RENAMES:
        op.alter_column(
            TABLE,
            old_name,
            new_column_name=new_name,
            schema=SCHEMA_FUEL,
        )

    # 3. Создать FK и индекс на grcode
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


def downgrade():
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

    # 2. Вернуть префикс agr_ к колонкам (обратный порядок, чтобы grcode последним)
    for old_name, new_name in COLUMN_RENAMES:
        op.alter_column(
            TABLE,
            new_name,
            new_column_name=old_name,
            schema=SCHEMA_FUEL,
        )

    # 3. Создать FK и индекс на agr_grcode
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
    op.create_index(
        "ix_gs_fue_machine_fuel_param_agr_grcode",
        TABLE,
        ["agr_grcode"],
        unique=False,
        schema=SCHEMA_FUEL,
    )

"""rename machine_toplivo_param to machine_fuel_param, topl_agr_* to agr_*

Revision ID: y8z9a0b1c2d3
Revises: x7y8z9a0b1c2
Create Date: 2026-02-26

Переименовывает таблицу gs_fue_machine_toplivo_param в gs_fue_machine_fuel_param
и все колонки topl_agr_* в agr_*.
"""

from alembic import op
from config import SCHEMA_FUEL, SCHEMA_FUE_EM


revision = "y8z9a0b1c2d3"
down_revision = "x7y8z9a0b1c2"
branch_labels = None
depends_on = None

OLD_TABLE = "gs_fue_machine_toplivo_param"
NEW_TABLE = "gs_fue_machine_fuel_param"
EM_TABLE = "gs_fue_em_equipment_group"
EM_SCHEMA = SCHEMA_FUE_EM
SCHEMA = SCHEMA_FUEL

COLUMN_RENAMES = [
    ("topl_agr_numb", "agr_numb"),
    ("topl_agr_stnumb", "agr_stnumb"),
    ("topl_agr_yearin", "agr_yearin"),
    ("topl_agr_dem", "agr_dem"),
    ("topl_agr_nt", "agr_nt"),
    ("topl_agr_numb1120", "agr_numb1120"),
    ("topl_agr_grcode", "agr_grcode"),
    ("topl_agr_stname", "agr_stname"),
    ("topl_agr_opesname", "agr_opesname"),
    ("topl_agr_note", "agr_note"),
]


def upgrade():
    # 1. Удалить FK и индекс на topl_agr_grcode
    op.drop_constraint(
        "fk_machine_toplivo_param_topl_agr_grcode",
        OLD_TABLE,
        type_="foreignkey",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_gs_fue_machine_toplivo_param_topl_agr_grcode",
        table_name=OLD_TABLE,
        schema=SCHEMA,
    )

    # 2. Переименовать колонки
    for old_name, new_name in COLUMN_RENAMES:
        op.alter_column(
            OLD_TABLE,
            old_name,
            new_column_name=new_name,
            schema=SCHEMA,
        )

    # 3. Переименовать unique constraint (через переименование таблицы)
    op.execute(
        f"ALTER TABLE {SCHEMA}.{OLD_TABLE} "
        f"RENAME CONSTRAINT uq_machine_toplivo_param_machine_id TO uq_machine_fuel_param_machine_id"
    )

    # 4. Переименовать таблицу
    op.rename_table(OLD_TABLE, NEW_TABLE, schema=SCHEMA)

    # 5. Переименовать индексы database_version_id, machine_id если нужно
    op.execute(
        f"ALTER INDEX IF EXISTS {SCHEMA}.ix_gs_fue_machine_toplivo_param_database_version_id "
        f"RENAME TO ix_gs_fue_machine_fuel_param_database_version_id"
    )
    op.execute(
        f"ALTER INDEX IF EXISTS {SCHEMA}.ix_gs_fue_machine_toplivo_param_machine_id "
        f"RENAME TO ix_gs_fue_machine_fuel_param_machine_id"
    )

    # 6. Создать FK и индекс на agr_grcode
    op.create_foreign_key(
        "fk_machine_fuel_param_agr_grcode",
        NEW_TABLE,
        EM_TABLE,
        ["agr_grcode"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=EM_SCHEMA,
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_gs_fue_machine_fuel_param_agr_grcode",
        NEW_TABLE,
        ["agr_grcode"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade():
    op.drop_constraint(
        "fk_machine_fuel_param_agr_grcode",
        NEW_TABLE,
        type_="foreignkey",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_gs_fue_machine_fuel_param_agr_grcode",
        table_name=NEW_TABLE,
        schema=SCHEMA,
    )

    op.execute(
        f"ALTER INDEX IF EXISTS {SCHEMA}.ix_gs_fue_machine_fuel_param_machine_id "
        f"RENAME TO ix_gs_fue_machine_toplivo_param_machine_id"
    )
    op.execute(
        f"ALTER INDEX IF EXISTS {SCHEMA}.ix_gs_fue_machine_fuel_param_database_version_id "
        f"RENAME TO ix_gs_fue_machine_toplivo_param_database_version_id"
    )

    op.rename_table(NEW_TABLE, OLD_TABLE, schema=SCHEMA)

    op.execute(
        f"ALTER TABLE {SCHEMA}.{OLD_TABLE} "
        f"RENAME CONSTRAINT uq_machine_fuel_param_machine_id TO uq_machine_toplivo_param_machine_id"
    )

    for new_name, old_name in reversed(COLUMN_RENAMES):
        op.alter_column(
            OLD_TABLE,
            new_name,
            new_column_name=old_name,
            schema=SCHEMA,
        )

    op.create_foreign_key(
        "fk_machine_toplivo_param_topl_agr_grcode",
        OLD_TABLE,
        EM_TABLE,
        ["topl_agr_grcode"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=EM_SCHEMA,
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_gs_fue_machine_toplivo_param_topl_agr_grcode",
        OLD_TABLE,
        ["topl_agr_grcode"],
        unique=False,
        schema=SCHEMA,
    )

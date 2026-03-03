"""add topl_oes FK to UnionEnergySystemExternalMapping

Revision ID: s6t7u8v9w0x1
Revises: r4s5t6u7v8w9
Create Date: 2026-02-24 15:00:00.000000

Связывает поле topl_oes в gs_fue_equipment_group_sets
с gs_fue_em_union_energy_system.external_id.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUEL, SCHEMA_FUE_EM


# revision identifiers, used by Alembic.
revision = "s6t7u8v9w0x1"
down_revision = "r4s5t6u7v8w9"
branch_labels = None
depends_on = None

TABLE = "gs_fue_equipment_group_sets"
SCHEMA = SCHEMA_FUEL
UES_TABLE = "gs_fue_em_union_energy_system"
UES_SCHEMA = SCHEMA_FUE_EM


def upgrade():
    # 1. Обнулить topl_oes, где значение не существует в union_energy_system.external_id
    op.execute(
        f"""
        UPDATE {SCHEMA}.{TABLE} egs
        SET topl_oes = NULL
        WHERE egs.topl_oes IS NOT NULL
          AND egs.topl_oes NOT IN ('', '0')
          AND NOT EXISTS (
              SELECT 1 FROM {UES_SCHEMA}.{UES_TABLE} u
              WHERE u.external_id = egs.topl_oes
          )
        """
    )

    # 2. Обнулить пустые/невалидные значения
    op.execute(
        f"""
        UPDATE {SCHEMA}.{TABLE}
        SET topl_oes = NULL
        WHERE topl_oes = '' OR topl_oes = '0' OR (topl_oes IS NOT NULL AND TRIM(topl_oes) = '')
        """
    )

    # 3. Изменить тип колонки String(255) -> String(80) и добавить FK
    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
        batch_op.alter_column(
            "topl_oes",
            existing_type=sa.String(length=255),
            type_=sa.String(length=80),
            nullable=True,
        )
        batch_op.create_foreign_key(
            "fk_equipment_group_sets_topl_oes",
            UES_TABLE,
            ["topl_oes"],
            ["external_id"],
            referent_schema=UES_SCHEMA,
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_gs_fue_equipment_group_sets_topl_oes",
            ["topl_oes"],
            unique=False,
        )


def downgrade():
    op.drop_constraint(
        "fk_equipment_group_sets_topl_oes",
        TABLE,
        type_="foreignkey",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_gs_fue_equipment_group_sets_topl_oes",
        table_name=TABLE,
        schema=SCHEMA,
    )
    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
        batch_op.alter_column(
            "topl_oes",
            existing_type=sa.String(length=80),
            type_=sa.String(length=255),
            nullable=True,
        )

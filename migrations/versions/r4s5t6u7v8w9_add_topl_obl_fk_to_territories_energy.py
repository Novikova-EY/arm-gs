"""add topl_obl FK to TerritoriesEnergyExternalMapping

Revision ID: r4s5t6u7v8w9
Revises: q3r4s5t6u7v8
Create Date: 2026-02-24 14:30:00.000000

Связывает поле topl_obl в gs_fue_equipment_group_sets
с gs_fue_em_territories_energy.external_id.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUEL, SCHEMA_FUE_EM


# revision identifiers, used by Alembic.
revision = "r4s5t6u7v8w9"
down_revision = "q3r4s5t6u7v8"
branch_labels = None
depends_on = None

TABLE = "gs_fue_equipment_group_sets"
SCHEMA = SCHEMA_FUEL
TERR_TABLE = "gs_fue_em_territories_energy"
TERR_SCHEMA = SCHEMA_FUE_EM


def upgrade():
    # 1. Обнулить topl_obl, где значение не существует в territories_energy.external_id
    op.execute(
        f"""
        UPDATE {SCHEMA}.{TABLE} egs
        SET topl_obl = NULL
        WHERE egs.topl_obl IS NOT NULL
          AND egs.topl_obl NOT IN ('', '0')
          AND NOT EXISTS (
              SELECT 1 FROM {TERR_SCHEMA}.{TERR_TABLE} t
              WHERE t.external_id = egs.topl_obl
          )
        """
    )

    # 2. Обнулить пустые/невалидные значения
    op.execute(
        f"""
        UPDATE {SCHEMA}.{TABLE}
        SET topl_obl = NULL
        WHERE topl_obl = '' OR topl_obl = '0' OR (topl_obl IS NOT NULL AND TRIM(topl_obl) = '')
        """
    )

    # 3. Изменить тип колонки String(255) -> String(80) и добавить FK
    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
        batch_op.alter_column(
            "topl_obl",
            existing_type=sa.String(length=255),
            type_=sa.String(length=80),
            nullable=True,
        )
        batch_op.create_foreign_key(
            "fk_equipment_group_sets_topl_obl",
            TERR_TABLE,
            ["topl_obl"],
            ["external_id"],
            referent_schema=TERR_SCHEMA,
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_gs_fue_equipment_group_sets_topl_obl",
            ["topl_obl"],
            unique=False,
        )


def downgrade():
    op.drop_constraint(
        "fk_equipment_group_sets_topl_obl",
        TABLE,
        type_="foreignkey",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_gs_fue_equipment_group_sets_topl_obl",
        table_name=TABLE,
        schema=SCHEMA,
    )
    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
        batch_op.alter_column(
            "topl_obl",
            existing_type=sa.String(length=80),
            type_=sa.String(length=255),
            nullable=True,
        )

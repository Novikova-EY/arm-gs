"""add be FK to BusinessUnitExternalMapping

Revision ID: b5c6d7e8f9a0
Revises: 8952176a152a
Create Date: 2026-02-26 16:00:00.000000

Связывает поле be в gs_fue_equipment_group_sets
с gs_fue_em_business_unit.external_id.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUEL, SCHEMA_FUE_EM


# revision identifiers, used by Alembic.
revision = "b5c6d7e8f9a0"
down_revision = "8952176a152a"
branch_labels = None
depends_on = None

TABLE = "gs_fue_equipment_group_sets"
SCHEMA = SCHEMA_FUEL
BU_TABLE = "gs_fue_em_business_unit"
BU_SCHEMA = SCHEMA_FUE_EM


def upgrade():
    # 1. Обнулить be, где значение не существует в business_unit.external_id
    op.execute(
        f"""
        UPDATE {SCHEMA}.{TABLE} egs
        SET be = NULL
        WHERE egs.be IS NOT NULL
          AND egs.be NOT IN ('', '0')
          AND TRIM(egs.be) != ''
          AND NOT EXISTS (
              SELECT 1 FROM {BU_SCHEMA}.{BU_TABLE} bu
              WHERE bu.external_id = egs.be
          )
        """
    )

    # 2. Обнулить пустые/невалидные значения
    op.execute(
        f"""
        UPDATE {SCHEMA}.{TABLE}
        SET be = NULL
        WHERE be = '' OR be = '0' OR (be IS NOT NULL AND TRIM(be) = '')
        """
    )

    # 3. Изменить тип колонки String(255) -> String(80) и добавить FK
    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
        batch_op.alter_column(
            "be",
            existing_type=sa.String(length=255),
            type_=sa.String(length=80),
            nullable=True,
        )
        batch_op.create_foreign_key(
            "fk_equipment_group_sets_be",
            BU_TABLE,
            ["be"],
            ["external_id"],
            referent_schema=BU_SCHEMA,
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_gs_fue_equipment_group_sets_be",
            ["be"],
            unique=False,
        )


def downgrade():
    op.drop_constraint(
        "fk_equipment_group_sets_be",
        TABLE,
        type_="foreignkey",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_gs_fue_equipment_group_sets_be",
        table_name=TABLE,
        schema=SCHEMA,
    )
    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
        batch_op.alter_column(
            "be",
            existing_type=sa.String(length=80),
            type_=sa.String(length=255),
            nullable=True,
        )

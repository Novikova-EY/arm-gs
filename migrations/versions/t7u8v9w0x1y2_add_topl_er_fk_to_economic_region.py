"""add topl_er FK to EconomicRegionExternalMapping

Revision ID: t7u8v9w0x1y2
Revises: s6t7u8v9w0x1
Create Date: 2026-02-24 16:00:00.000000

Связывает поле topl_er в gs_fue_equipment_group_sets
с gs_fue_em_economic_region.external_id.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUEL, SCHEMA_FUE_EM


# revision identifiers, used by Alembic.
revision = "t7u8v9w0x1y2"
down_revision = "s6t7u8v9w0x1"
branch_labels = None
depends_on = None

TABLE = "gs_fue_equipment_group_sets"
SCHEMA = SCHEMA_FUEL
ER_TABLE = "gs_fue_em_economic_region"
ER_SCHEMA = SCHEMA_FUE_EM


def upgrade():
    # 1. Обнулить topl_er, где значение не существует в economic_region.external_id
    op.execute(
        f"""
        UPDATE {SCHEMA}.{TABLE} egs
        SET topl_er = NULL
        WHERE egs.topl_er IS NOT NULL
          AND egs.topl_er NOT IN ('', '0')
          AND NOT EXISTS (
              SELECT 1 FROM {ER_SCHEMA}.{ER_TABLE} er
              WHERE er.external_id = egs.topl_er
          )
        """
    )

    # 2. Обнулить пустые/невалидные значения
    op.execute(
        f"""
        UPDATE {SCHEMA}.{TABLE}
        SET topl_er = NULL
        WHERE topl_er = '' OR topl_er = '0' OR (topl_er IS NOT NULL AND TRIM(topl_er) = '')
        """
    )

    # 3. Изменить тип колонки String(255) -> String(80) и добавить FK
    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
        batch_op.alter_column(
            "topl_er",
            existing_type=sa.String(length=255),
            type_=sa.String(length=80),
            nullable=True,
        )
        batch_op.create_foreign_key(
            "fk_equipment_group_sets_topl_er",
            ER_TABLE,
            ["topl_er"],
            ["external_id"],
            referent_schema=ER_SCHEMA,
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_gs_fue_equipment_group_sets_topl_er",
            ["topl_er"],
            unique=False,
        )


def downgrade():
    op.drop_constraint(
        "fk_equipment_group_sets_topl_er",
        TABLE,
        type_="foreignkey",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_gs_fue_equipment_group_sets_topl_er",
        table_name=TABLE,
        schema=SCHEMA,
    )
    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
        batch_op.alter_column(
            "topl_er",
            existing_type=sa.String(length=80),
            type_=sa.String(length=255),
            nullable=True,
        )

"""add topl_fo FK to FederalDistrictExternalMapping

Revision ID: u8v9w0x1y2z3
Revises: t7u8v9w0x1y2
Create Date: 2026-02-24 17:00:00.000000

Связывает поле topl_fo в gs_fue_equipment_group_sets
с gs_fue_em_federal_district.external_id.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUEL, SCHEMA_FUE_EM


# revision identifiers, used by Alembic.
revision = "u8v9w0x1y2z3"
down_revision = "t7u8v9w0x1y2"
branch_labels = None
depends_on = None

TABLE = "gs_fue_equipment_group_sets"
SCHEMA = SCHEMA_FUEL
FD_TABLE = "gs_fue_em_federal_district"
FD_SCHEMA = SCHEMA_FUE_EM


def upgrade():
    # 1. Обнулить topl_fo, где значение не существует в federal_district.external_id
    op.execute(
        f"""
        UPDATE {SCHEMA}.{TABLE} egs
        SET topl_fo = NULL
        WHERE egs.topl_fo IS NOT NULL
          AND egs.topl_fo NOT IN ('', '0')
          AND NOT EXISTS (
              SELECT 1 FROM {FD_SCHEMA}.{FD_TABLE} fd
              WHERE fd.external_id = egs.topl_fo
          )
        """
    )

    # 2. Обнулить пустые/невалидные значения
    op.execute(
        f"""
        UPDATE {SCHEMA}.{TABLE}
        SET topl_fo = NULL
        WHERE topl_fo = '' OR topl_fo = '0' OR (topl_fo IS NOT NULL AND TRIM(topl_fo) = '')
        """
    )

    # 3. Изменить тип колонки String(255) -> String(80) и добавить FK
    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
        batch_op.alter_column(
            "topl_fo",
            existing_type=sa.String(length=255),
            type_=sa.String(length=80),
            nullable=True,
        )
        batch_op.create_foreign_key(
            "fk_equipment_group_sets_topl_fo",
            FD_TABLE,
            ["topl_fo"],
            ["external_id"],
            referent_schema=FD_SCHEMA,
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_gs_fue_equipment_group_sets_topl_fo",
            ["topl_fo"],
            unique=False,
        )


def downgrade():
    op.drop_constraint(
        "fk_equipment_group_sets_topl_fo",
        TABLE,
        type_="foreignkey",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_gs_fue_equipment_group_sets_topl_fo",
        table_name=TABLE,
        schema=SCHEMA,
    )
    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
        batch_op.alter_column(
            "topl_fo",
            existing_type=sa.String(length=80),
            type_=sa.String(length=255),
            nullable=True,
        )

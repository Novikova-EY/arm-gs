"""add topl_gk FK to GenCompanyExternalMapping

Revision ID: v9w0x1y2z3a4b5
Revises: u8v9w0x1y2z3
Create Date: 2026-02-24 18:00:00.000000

Связывает поле topl_gk в gs_fue_equipment_group_sets
с gs_fue_em_gen_company.external_id.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUEL, SCHEMA_FUE_EM


# revision identifiers, used by Alembic.
revision = "v9w0x1y2z3a4b5"
down_revision = "u8v9w0x1y2z3"
branch_labels = None
depends_on = None

TABLE = "gs_fue_equipment_group_sets"
SCHEMA = SCHEMA_FUEL
GC_TABLE = "gs_fue_em_gen_company"
GC_SCHEMA = SCHEMA_FUE_EM


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(TABLE, schema=SCHEMA):
        return
    # 1. Обнулить topl_gk, где значение не существует в gen_company.external_id
    op.execute(
        f"""
        UPDATE {SCHEMA}.{TABLE} egs
        SET topl_gk = NULL
        WHERE egs.topl_gk IS NOT NULL
          AND egs.topl_gk NOT IN ('', '0')
          AND NOT EXISTS (
              SELECT 1 FROM {GC_SCHEMA}.{GC_TABLE} gc
              WHERE gc.external_id = egs.topl_gk
          )
        """
    )

    # 2. Обнулить пустые/невалидные значения
    op.execute(
        f"""
        UPDATE {SCHEMA}.{TABLE}
        SET topl_gk = NULL
        WHERE topl_gk = '' OR topl_gk = '0' OR (topl_gk IS NOT NULL AND TRIM(topl_gk) = '')
        """
    )

    # 3. Изменить тип колонки String(255) -> String(80) и добавить FK
    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
        batch_op.alter_column(
            "topl_gk",
            existing_type=sa.String(length=255),
            type_=sa.String(length=80),
            nullable=True,
        )
        batch_op.create_foreign_key(
            "fk_equipment_group_sets_topl_gk",
            GC_TABLE,
            ["topl_gk"],
            ["external_id"],
            referent_schema=GC_SCHEMA,
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_gs_fue_equipment_group_sets_topl_gk",
            ["topl_gk"],
            unique=False,
        )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(TABLE, schema=SCHEMA):
        return
    op.drop_constraint(
        "fk_equipment_group_sets_topl_gk",
        TABLE,
        type_="foreignkey",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_gs_fue_equipment_group_sets_topl_gk",
        table_name=TABLE,
        schema=SCHEMA,
    )
    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
        batch_op.alter_column(
            "topl_gk",
            existing_type=sa.String(length=80),
            type_=sa.String(length=255),
            nullable=True,
        )

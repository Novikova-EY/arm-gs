"""add topl_dep FK to DepartmentExternalMapping

Revision ID: p2q3r4s5t6u7
Revises: o2p3q4r5s6t7
Create Date: 2026-02-24 12:00:00.000000

Связывает поле topl_dep в gs_fue_equipment_group_sets с gs_fue_em_department.external_id.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUEL, SCHEMA_FUE_EM


# revision identifiers, used by Alembic.
revision = "p2q3r4s5t6u7"
down_revision = "o2p3q4r5s6t7"
branch_labels = None
depends_on = None

TABLE = "gs_fue_equipment_group_sets"
SCHEMA = SCHEMA_FUEL
DEPT_TABLE = "gs_fue_em_department"
DEPT_SCHEMA = SCHEMA_FUE_EM


def upgrade():
    # 1. Обнулить topl_dep, где значение не существует в gs_fue_em_department
    op.execute(
        f"""
        UPDATE {SCHEMA}.{TABLE} egs
        SET topl_dep = NULL
        WHERE egs.topl_dep IS NOT NULL
          AND egs.topl_dep NOT IN ('', '0')
          AND NOT EXISTS (
              SELECT 1 FROM {DEPT_SCHEMA}.{DEPT_TABLE} d
              WHERE d.external_id = egs.topl_dep
          )
        """
    )

    # 2. Обнулить пустые/невалидные значения
    op.execute(
        f"""
        UPDATE {SCHEMA}.{TABLE}
        SET topl_dep = NULL
        WHERE topl_dep = '' OR topl_dep = '0' OR (topl_dep IS NOT NULL AND TRIM(topl_dep) = '')
        """
    )

    # 3. Изменить тип колонки String(255) -> String(80) и добавить FK
    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
        batch_op.alter_column(
            "topl_dep",
            existing_type=sa.String(length=255),
            type_=sa.String(length=80),
            nullable=True,
        )
        batch_op.create_foreign_key(
            "fk_equipment_group_sets_topl_dep",
            DEPT_TABLE,
            ["topl_dep"],
            ["external_id"],
            referent_schema=DEPT_SCHEMA,
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_gs_fue_equipment_group_sets_topl_dep",
            ["topl_dep"],
            unique=False,
        )


def downgrade():
    op.drop_constraint(
        "fk_equipment_group_sets_topl_dep",
        TABLE,
        type_="foreignkey",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_gs_fue_equipment_group_sets_topl_dep",
        table_name=TABLE,
        schema=SCHEMA,
    )
    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
        batch_op.alter_column(
            "topl_dep",
            existing_type=sa.String(length=80),
            type_=sa.String(length=255),
            nullable=True,
        )


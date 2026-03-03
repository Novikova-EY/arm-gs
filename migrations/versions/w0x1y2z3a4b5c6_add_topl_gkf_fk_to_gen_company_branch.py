"""add topl_gkf link to GenCompanyBranchExternalMapping

Revision ID: w0x1y2z3a4b5c6
Revises: v9w0x1y2z3a4b5
Create Date: 2026-02-24 19:00:00.000000

Подготавливает поле topl_gkf для связи с GenCompanyBranchExternalMapping:
- ограничивает длину до 80 (как external_id)
- добавляет индекс для быстрого join
Связь через relationship (primaryjoin) без FK в БД.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "w0x1y2z3a4b5c6"
down_revision = "v9w0x1y2z3a4b5"
branch_labels = None
depends_on = None

TABLE = "gs_fue_equipment_group_sets"
SCHEMA = SCHEMA_FUEL


def upgrade():
    # 1. Обнулить значения длиннее 80 символов (external_id имеет length=80)
    op.execute(
        f"""
        UPDATE {SCHEMA}.{TABLE}
        SET topl_gkf = NULL
        WHERE topl_gkf IS NOT NULL AND LENGTH(topl_gkf) > 80
        """
    )

    # 2. Изменить тип колонки String(255) -> String(80), добавить индекс
    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
        batch_op.alter_column(
            "topl_gkf",
            existing_type=sa.String(length=255),
            type_=sa.String(length=80),
            nullable=True,
        )
        batch_op.create_index(
            "ix_gs_fue_equipment_group_sets_topl_gkf",
            ["topl_gkf"],
            unique=False,
        )


def downgrade():
    op.drop_index(
        "ix_gs_fue_equipment_group_sets_topl_gkf",
        table_name=TABLE,
        schema=SCHEMA,
    )
    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
        batch_op.alter_column(
            "topl_gkf",
            existing_type=sa.String(length=80),
            type_=sa.String(length=255),
            nullable=True,
        )

"""rename topl_agr_number->topl_agr_stnumb, topl_agr_station_name->topl_agr_stname

Revision ID: v0w1x2y3z4a5b6
Revises: e55f58bb4b49
Create Date: 2026-02-26 10:00:00.000000

- Удаляет колонку topl_agr_stnumb (добавленную в u9v0w1x2y3z4, дублирует topl_agr_number).
- Переименовывает topl_agr_number в topl_agr_stnumb.
- Переименовывает topl_agr_station_name в topl_agr_stname.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUEL


revision = "v0w1x2y3z4a5b6"
down_revision = "u9v0w1x2y3z4"
branch_labels = None
depends_on = None

TABLE = "gs_fue_machine_toplivo_param"
SCHEMA = SCHEMA_FUEL


def upgrade():
    # 1. Удалить дублирующую колонку topl_agr_stnumb (добавленную в u9v0w1x2y3z4)
    op.drop_column(TABLE, "topl_agr_stnumb", schema=SCHEMA)
    # 2. Переименовать topl_agr_number -> topl_agr_stnumb
    op.alter_column(
        TABLE,
        "topl_agr_number",
        new_column_name="topl_agr_stnumb",
        existing_type=sa.Integer(),
        existing_nullable=True,
        schema=SCHEMA,
    )
    # 3. Переименовать topl_agr_station_name -> topl_agr_stname
    op.alter_column(
        TABLE,
        "topl_agr_station_name",
        new_column_name="topl_agr_stname",
        existing_type=sa.String(80),
        existing_nullable=True,
        schema=SCHEMA,
    )


def downgrade():
    # 3. Вернуть topl_agr_stname -> topl_agr_station_name
    op.alter_column(
        TABLE,
        "topl_agr_stname",
        new_column_name="topl_agr_station_name",
        existing_type=sa.String(80),
        existing_nullable=True,
        schema=SCHEMA,
    )
    # 2. Вернуть topl_agr_stnumb -> topl_agr_number
    op.alter_column(
        TABLE,
        "topl_agr_stnumb",
        new_column_name="topl_agr_number",
        existing_type=sa.Integer(),
        existing_nullable=True,
        schema=SCHEMA,
    )
    # 1. Добавить обратно колонку topl_agr_stnumb
    op.add_column(
        TABLE,
        sa.Column("topl_agr_stnumb", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )

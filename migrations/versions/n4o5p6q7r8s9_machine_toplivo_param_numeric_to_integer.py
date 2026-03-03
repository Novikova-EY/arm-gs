"""machine_toplivo_param numeric to integer, string length to 80

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-02-21 14:00:00.000000

Изменяет числовые поля MachineToplivoParam с NUMERIC(20,6) на INTEGER.
Переименовывает topl_agr_station_number в topl_agr_number.
Изменяет строковые поля topl_agr_station_name, topl_agr_opesname с VARCHAR(1024) на VARCHAR(80).
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "n4o5p6q7r8s9"
down_revision = "m3n4o5p6q7r8"
branch_labels = None
depends_on = None

TABLE = "gs_fue_machine_toplivo_param"
SCHEMA = SCHEMA_FUEL

NUMERIC_COLUMNS = [
    "topl_agr_numb1120",
    "topl_agr_numb",
    "topl_agr_yearin",
    "topl_agr_dem",
    "topl_agr_nt",
    "topl_agr_grcode",
    "topl_agr_note",
]
# Переименовать и изменить тип
RENAME_AND_ALTER = ("topl_agr_station_number", "topl_agr_number")

STRING_COLUMNS = [
    "topl_agr_station_name",
    "topl_agr_opesname",
]


def upgrade():
    # Переименовать topl_agr_station_number -> topl_agr_number и изменить тип
    old_name, new_name = RENAME_AND_ALTER
    op.alter_column(
        TABLE,
        old_name,
        new_column_name=new_name,
        existing_type=sa.Numeric(20, 6),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using=f'"{old_name}"::integer',
        schema=SCHEMA,
    )
    for col in NUMERIC_COLUMNS:
        op.alter_column(
            TABLE,
            col,
            existing_type=sa.Numeric(20, 6),
            type_=sa.Integer(),
            existing_nullable=True,
            postgresql_using=f"{col}::integer",
            schema=SCHEMA,
        )
    for col in STRING_COLUMNS:
        op.alter_column(
            TABLE,
            col,
            existing_type=sa.String(1024),
            type_=sa.String(80),
            existing_nullable=True,
            postgresql_using=f"left(\"{col}\", 80)",
            schema=SCHEMA,
        )


def downgrade():
    # Вернуть topl_agr_number -> topl_agr_station_number
    old_name, new_name = RENAME_AND_ALTER
    op.alter_column(
        TABLE,
        new_name,
        new_column_name=old_name,
        existing_type=sa.Integer(),
        type_=sa.Numeric(20, 6),
        existing_nullable=True,
        schema=SCHEMA,
    )
    for col in reversed(STRING_COLUMNS):
        op.alter_column(
            TABLE,
            col,
            existing_type=sa.String(80),
            type_=sa.String(1024),
            existing_nullable=True,
            schema=SCHEMA,
        )
    for col in reversed(NUMERIC_COLUMNS):
        op.alter_column(
            TABLE,
            col,
            existing_type=sa.Integer(),
            type_=sa.Numeric(20, 6),
            existing_nullable=True,
            schema=SCHEMA,
        )

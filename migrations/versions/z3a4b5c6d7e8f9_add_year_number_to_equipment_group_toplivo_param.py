"""add year_number to equipment_group_toplivo_param

Revision ID: z3a4b5c6d7e8f9
Revises: y2z3a4b5c6d7e8
Create Date: 2026-02-24 22:00:00.000000

Добавляет привязку параметров EquipmentGroupToplivoParam к году (year_number -> gs_years.number).
Меняет уникальность: (equipment_group_set_station_id, year_number).
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUEL, SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "z3a4b5c6d7e8f9"
down_revision = "y2z3a4b5c6d7e8"
branch_labels = None
depends_on = None

TABLE = "gs_fue_equipment_group_toplivo_param"
SCHEMA = SCHEMA_FUEL
YEARS_TABLE = "gs_years"


def upgrade():
    # 1) Добавить year_number (nullable, без FK: gs_years.number не уникален — дубли по версиям)
    op.add_column(
        TABLE,
        sa.Column("year_number", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_fue_equipment_group_toplivo_param_year_number",
        TABLE,
        ["year_number"],
        unique=False,
        schema=SCHEMA,
    )

    # 2) Перенести данные year -> year_number (если year есть в gs_years)
    conn = op.get_bind()
    conn.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA}.{TABLE} t
            SET year_number = t.year
            FROM {SCHEMA_REFDATA}.{YEARS_TABLE} y
            WHERE t.year IS NOT NULL AND y.number = t.year
            """
        )
    )

    # 3) Удалить старый столбец year
    op.drop_column(TABLE, "year", schema=SCHEMA)

    # 4) Удалить старый unique constraint
    op.drop_constraint(
        "uq_equipment_group_toplivo_param_station_link",
        TABLE,
        schema=SCHEMA,
        type_="unique",
    )

    # 5) Добавить partial unique indexes (PostgreSQL: NULL в unique трактуются как разные значения)
    op.create_index(
        "uq_equipment_group_toplivo_param_station_year",
        TABLE,
        ["equipment_group_set_station_id", "year_number"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("year_number IS NOT NULL"),
    )
    op.create_index(
        "uq_equipment_group_toplivo_param_station_null_year",
        TABLE,
        ["equipment_group_set_station_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("year_number IS NULL"),
    )


def downgrade():
    # 1) Удалить partial unique indexes
    op.drop_index(
        "uq_equipment_group_toplivo_param_station_year",
        table_name=TABLE,
        schema=SCHEMA,
    )
    op.drop_index(
        "uq_equipment_group_toplivo_param_station_null_year",
        table_name=TABLE,
        schema=SCHEMA,
    )

    # 2) Восстановить старый unique constraint
    op.create_unique_constraint(
        "uq_equipment_group_toplivo_param_station_link",
        TABLE,
        ["equipment_group_set_station_id"],
        schema=SCHEMA,
    )

    # 3) Добавить обратно столбец year, удалить year_number
    op.add_column(
        TABLE,
        sa.Column("year", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    conn = op.get_bind()
    conn.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA}.{TABLE} SET year = year_number WHERE year_number IS NOT NULL
            """
        )
    )
    op.drop_index(
        "ix_gs_fue_equipment_group_toplivo_param_year_number",
        table_name=TABLE,
        schema=SCHEMA,
    )
    op.drop_column(TABLE, "year_number", schema=SCHEMA)

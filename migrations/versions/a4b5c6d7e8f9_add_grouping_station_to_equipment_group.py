# -*- coding: utf-8 -*-
"""Добавляет ручную привязку электростанции для группировки standalone-групп оборудования.

Revision ID: a4b5c6d7e8f9
Revises: z2b3c4d5e6f8
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa


revision = "a4b5c6d7e8f9"
down_revision = "z2b3c4d5e6f8"
branch_labels = None
depends_on = None

SCHEMA_FUEL = "gs_fue"
SCHEMA_GEN = "gs_gen"
TABLE = "gs_fue_equipment_groups"


def upgrade():
    op.add_column(
        TABLE,
        sa.Column("grouping_station_id", sa.Integer(), nullable=True),
        schema=SCHEMA_FUEL,
    )
    op.create_index(
        "ix_equipment_group_grouping_station_id",
        TABLE,
        ["grouping_station_id"],
        schema=SCHEMA_FUEL,
    )
    op.create_foreign_key(
        "fk_equipment_group_grouping_station",
        TABLE,
        "stations",
        ["grouping_station_id"],
        ["id"],
        source_schema=SCHEMA_FUEL,
        referent_schema=SCHEMA_GEN,
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint(
        "fk_equipment_group_grouping_station",
        TABLE,
        schema=SCHEMA_FUEL,
        type_="foreignkey",
    )
    op.drop_index(
        "ix_equipment_group_grouping_station_id",
        table_name=TABLE,
        schema=SCHEMA_FUEL,
    )
    op.drop_column(TABLE, "grouping_station_id", schema=SCHEMA_FUEL)

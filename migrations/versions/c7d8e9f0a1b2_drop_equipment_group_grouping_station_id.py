# -*- coding: utf-8 -*-
"""Удаляет grouping_station_id у gs_fue_equipment_groups (станция только через type_stations).

Revision ID: c7d8e9f0a1b2
Revises: 9b06a85659da
Create Date: 2026-04-23
"""
from alembic import op

revision = "c7d8e9f0a1b2"
down_revision = "9b06a85659da"
branch_labels = None
depends_on = None

SCHEMA_FUEL = "gs_fue"
SCHEMA_GEN = "gs_gen"
TABLE = "gs_fue_equipment_groups"


def upgrade():
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


def downgrade():
    import sqlalchemy as sa

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

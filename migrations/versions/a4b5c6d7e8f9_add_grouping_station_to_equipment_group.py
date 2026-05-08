# -*- coding: utf-8 -*-
"""Добавляет ручную привязку электростанции для группировки standalone-групп оборудования.

Revision ID: a4b5c6d7e8f9
Revises: z2b3c4d5e6f8
Create Date: 2026-04-23
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "a4b5c6d7e8f9"
down_revision = "z2b3c4d5e6f8"
branch_labels = None
depends_on = None

SCHEMA_FUEL = "gs_fue"
SCHEMA_GEN = "gs_gen"
TABLE = "gs_fue_equipment_groups"


def upgrade():
    conn = op.get_bind()
    stations_tbl = column_utils.gs_gen_stations_table_name(conn, SCHEMA_GEN)
    if stations_tbl is None:
        return
    if not column_utils.table_has_column(conn, SCHEMA_FUEL, TABLE, "grouping_station_id"):
        op.add_column(
            TABLE,
            sa.Column("grouping_station_id", sa.Integer(), nullable=True),
            schema=SCHEMA_FUEL,
        )
    if not column_utils.index_exists(conn, SCHEMA_FUEL, "ix_equipment_group_grouping_station_id"):
        op.create_index(
            "ix_equipment_group_grouping_station_id",
            TABLE,
            ["grouping_station_id"],
            schema=SCHEMA_FUEL,
        )
    if not column_utils.constraint_exists(conn, SCHEMA_FUEL, "fk_equipment_group_grouping_station"):
        op.create_foreign_key(
            "fk_equipment_group_grouping_station",
            TABLE,
            stations_tbl,
            ["grouping_station_id"],
            ["id"],
            source_schema=SCHEMA_FUEL,
            referent_schema=SCHEMA_GEN,
            ondelete="SET NULL",
        )


def downgrade():
    conn = op.get_bind()
    if column_utils.constraint_exists(conn, SCHEMA_FUEL, "fk_equipment_group_grouping_station"):
        op.drop_constraint(
            "fk_equipment_group_grouping_station",
            TABLE,
            schema=SCHEMA_FUEL,
            type_="foreignkey",
        )
    if column_utils.index_exists(conn, SCHEMA_FUEL, "ix_equipment_group_grouping_station_id"):
        op.drop_index(
            "ix_equipment_group_grouping_station_id",
            table_name=TABLE,
            schema=SCHEMA_FUEL,
        )
    if column_utils.table_has_column(conn, SCHEMA_FUEL, TABLE, "grouping_station_id"):
        op.drop_column(TABLE, "grouping_station_id", schema=SCHEMA_FUEL)

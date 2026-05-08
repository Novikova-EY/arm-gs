"""add_regional_energy_system_to_prospective_place_aes

Revision ID: s1t2u3v4w5x6
Revises: r0s1t2u3v4w5
Create Date: 2026-03-19

Добавляет FK id_regional_energy_system -> gs_regional_energy_systems в station_prospective_place_aes.
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402


revision = "s1t2u3v4w5x6"
down_revision = "r0s1t2u3v4w5"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REF = "gs_sys"
TABLE = "station_prospective_place_aes"
TABLE_RES = "gs_regional_energy_systems"


def upgrade():
    conn = op.get_bind()
    table = column_utils.station_prospective_place_aes_table_name(conn, SCHEMA_GEN)
    table_res = column_utils.refdata_table_name(conn, SCHEMA_REF, TABLE_RES)
    if table is None or table_res is None:
        return
    if not column_utils.table_has_column(conn, SCHEMA_GEN, table, "id_regional_energy_system"):
        op.add_column(
            table,
            sa.Column("id_regional_energy_system", sa.Integer(), nullable=True),
            schema=SCHEMA_GEN,
        )
    if not column_utils.index_exists(conn, SCHEMA_GEN, "ix_station_prospective_place_aes_id_regional_energy_system"):
        op.create_index(
            "ix_station_prospective_place_aes_id_regional_energy_system",
            table,
            ["id_regional_energy_system"],
            schema=SCHEMA_GEN,
        )
    if not column_utils.constraint_exists(conn, SCHEMA_GEN, "fk_station_prospective_place_aes_regional_energy_system"):
        op.create_foreign_key(
            "fk_station_prospective_place_aes_regional_energy_system",
            table,
            table_res,
            ["id_regional_energy_system"],
            ["id"],
            source_schema=SCHEMA_GEN,
            referent_schema=SCHEMA_REF,
            ondelete="SET NULL",
        )


def downgrade():
    conn = op.get_bind()
    table = column_utils.station_prospective_place_aes_table_name(conn, SCHEMA_GEN)
    if table is None:
        return
    if column_utils.constraint_exists(conn, SCHEMA_GEN, "fk_station_prospective_place_aes_regional_energy_system"):
        op.drop_constraint(
            "fk_station_prospective_place_aes_regional_energy_system",
            table,
            schema=SCHEMA_GEN,
            type_="foreignkey",
        )
    if column_utils.index_exists(conn, SCHEMA_GEN, "ix_station_prospective_place_aes_id_regional_energy_system"):
        op.drop_index(
            "ix_station_prospective_place_aes_id_regional_energy_system",
            table_name=table,
            schema=SCHEMA_GEN,
        )
    if column_utils.table_has_column(conn, SCHEMA_GEN, table, "id_regional_energy_system"):
        op.drop_column(table, "id_regional_energy_system", schema=SCHEMA_GEN)

"""Выбранный энергорайон группы оборудования.

Revision ID: eg26102201
Revises: ef26102102
"""
from alembic import op
import sqlalchemy as sa

from migrations import column_utils

from config import SCHEMA_FUEL, SCHEMA_REFDATA

revision = "eg26102201"
down_revision = "ef26102102"
branch_labels = None
depends_on = None

TABLE = "gs_fue_equipment_groups"
INDEX = "ix_gs_fue_equipment_groups_energy_unit_id"
FK = "fk_equipment_group_energy_unit"


def upgrade():
    conn = op.get_bind()
    if not column_utils.table_has_column(conn, SCHEMA_FUEL, TABLE, "energy_unit_id"):
        op.add_column(TABLE, sa.Column("energy_unit_id", sa.Integer(), nullable=True), schema=SCHEMA_FUEL)
    if not column_utils.constraint_exists(conn, SCHEMA_FUEL, FK):
        op.create_foreign_key(
            FK, TABLE, "gs_sys_energy_units", ["energy_unit_id"], ["id"],
            source_schema=SCHEMA_FUEL, referent_schema=SCHEMA_REFDATA, ondelete="SET NULL",
        )
    if not column_utils.index_exists(conn, SCHEMA_FUEL, INDEX):
        op.create_index(INDEX, TABLE, ["energy_unit_id"], schema=SCHEMA_FUEL)


def downgrade():
    conn = op.get_bind()
    if column_utils.index_exists(conn, SCHEMA_FUEL, INDEX):
        op.drop_index(INDEX, table_name=TABLE, schema=SCHEMA_FUEL)
    if column_utils.constraint_exists(conn, SCHEMA_FUEL, FK):
        op.drop_constraint(FK, TABLE, schema=SCHEMA_FUEL, type_="foreignkey")
    if column_utils.table_has_column(conn, SCHEMA_FUEL, TABLE, "energy_unit_id"):
        op.drop_column(TABLE, "energy_unit_id", schema=SCHEMA_FUEL)

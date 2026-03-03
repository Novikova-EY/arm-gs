"""rename gs_fue_equipment_group_toplivo_param to gs_fue_equipment_group_fuel_param

Revision ID: i8j9k0l1m2n3
Revises: h7i8j9k0l1m2
Create Date: 2026-02-27

Переименовывает таблицу gs_fue_equipment_group_toplivo_param
в gs_fue_equipment_group_fuel_param.
Модель EquipmentGroupFuelParam ожидает gs_fue_equipment_group_fuel_param.
Идемпотентно: выполняется только если старая таблица существует.
"""

from alembic import op
from sqlalchemy import inspect
from config import SCHEMA_FUEL


revision = "i8j9k0l1m2n3"
down_revision = "h7i8j9k0l1m2"
branch_labels = None
depends_on = None

OLD_TABLE = "gs_fue_equipment_group_toplivo_param"
NEW_TABLE = "gs_fue_equipment_group_fuel_param"
SCHEMA = SCHEMA_FUEL


def _table_exists(conn, table):
    inspector = inspect(conn)
    return inspector.has_table(table, schema=SCHEMA)


def upgrade():
    conn = op.get_bind()
    if not _table_exists(conn, OLD_TABLE):
        return
    if _table_exists(conn, NEW_TABLE):
        return
    op.rename_table(OLD_TABLE, NEW_TABLE, schema=SCHEMA)


def downgrade():
    conn = op.get_bind()
    if not _table_exists(conn, NEW_TABLE):
        return
    op.rename_table(NEW_TABLE, OLD_TABLE, schema=SCHEMA)

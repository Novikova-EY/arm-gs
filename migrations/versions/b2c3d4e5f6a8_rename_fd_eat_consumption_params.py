# -*- coding: utf-8 -*-
"""ФО: переименование таблицы потребления по ВЭД — eat в имени.

Revision ID: b2c3d4e5f6a8
Revises: a0b1c2d3e4f6
Create Date: 2026-06-04
"""
import os
import sys

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "b2c3d4e5f6a8"
down_revision = "a0b1c2d3e4f6"
branch_labels = None
depends_on = None

SCHEMA = "gs_ekp"
NEW_TABLE = "gs_ekp_federal_district_eat_consumption_params"
_OLD_TABLES = (
    "gs_ekp_federal_district_consumption_params",
    "gs_ekp_federal_district_economic_activity_consumption_params",
)

_OLD_FK = "fk_ekp_fd_ved_cons_year_ver"
_NEW_FK = "fk_ekp_fd_eat_cons_year_ver"
_OLD_FK_EA = "fk_ec_fd_ea_cons_year_ver"
_NEW_FK_EA = "fk_ekp_fd_eat_cons_year_ver"


def _rename_fk(conn, table: str, old_fk: str, new_fk: str) -> None:
    if not column_utils.table_exists(conn, SCHEMA, table):
        return
    if column_utils.constraint_exists(conn, SCHEMA, old_fk) and not column_utils.constraint_exists(
        conn, SCHEMA, new_fk
    ):
        op.execute(
            sa.text(
                f'ALTER TABLE "{SCHEMA}"."{table}" RENAME CONSTRAINT '
                f'"{old_fk}" TO "{new_fk}"'
            )
        )


def upgrade():
    conn = op.get_bind()
    if column_utils.table_exists(conn, SCHEMA, NEW_TABLE):
        _rename_fk(conn, NEW_TABLE, _OLD_FK, _NEW_FK)
        _rename_fk(conn, NEW_TABLE, _OLD_FK_EA, _NEW_FK)
        return

    for old_table in _OLD_TABLES:
        if not column_utils.table_exists(conn, SCHEMA, old_table):
            continue
        op.rename_table(old_table, NEW_TABLE, schema=SCHEMA)
        _rename_fk(conn, NEW_TABLE, _OLD_FK, _NEW_FK)
        _rename_fk(conn, NEW_TABLE, _OLD_FK_EA, _NEW_FK)
        return


def downgrade():
    conn = op.get_bind()
    old_table = _OLD_TABLES[1]
    if not column_utils.table_exists(conn, SCHEMA, NEW_TABLE):
        return
    if column_utils.table_exists(conn, SCHEMA, old_table):
        return
    _rename_fk(conn, NEW_TABLE, _NEW_FK, _OLD_FK_EA)
    op.rename_table(NEW_TABLE, old_table, schema=SCHEMA)

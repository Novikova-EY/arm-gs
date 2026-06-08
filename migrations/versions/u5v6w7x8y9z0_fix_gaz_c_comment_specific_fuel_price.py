# -*- coding: utf-8 -*-
"""Исправить комментарий gaz_c в gs_fue_equipment_group_specific_fuel_price.

Revision ID: u5v6w7x8y9z0
Revises: t4u5v6w7x8y9
Create Date: 2026-06-08
"""
import os
import sys

from alembic import op
from sqlalchemy import text

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "u5v6w7x8y9z0"
down_revision = "t4u5v6w7x8y9"
branch_labels = None
depends_on = None

SCHEMA = "gs_fue"
TABLE = "gs_fue_equipment_group_specific_fuel_price"
COLUMN = "gaz_c"
COMMENT = "Цена, газ (всего)"


def _comment_on_column(conn, comment: str | None) -> None:
    if not column_utils.table_has_column(conn, SCHEMA, TABLE, COLUMN):
        return
    conn.execute(
        text(f'COMMENT ON COLUMN "{SCHEMA}"."{TABLE}"."{COLUMN}" IS :comment'),
        {"comment": comment},
    )


def upgrade():
    _comment_on_column(op.get_bind(), COMMENT)


def downgrade():
    _comment_on_column(
        op.get_bind(),
        "quantity из EquipmentGroupFuelParam (FROM_EQUIPMENT_GROUP) "
        "или EquipmentGroupExtraFuelParam (FROM_EXTRA_FUEL).",
    )

# -*- coding: utf-8 -*-
"""Затраты на производство ЭЭ: уникальность name в пределах версии БД.

Revision ID: ep2c3d4e5f6
Revises: ep1c2d3e4f5
Create Date: 2026-06-29
"""
import os
import sys

from alembic import op

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "ep2c3d4e5f6"
down_revision = "ep1c2d3e4f5"
branch_labels = None
depends_on = None

SCHEMA_REF = "gs_sys"
TABLE = "gs_sys_electricity_production_cost_types"
OLD_UQ = "uq_gs_sys_electricity_production_cost_types_name"
NEW_UQ = "uq_gs_sys_electricity_production_cost_types_ver_name"


def upgrade():
    conn = op.get_bind()
    if column_utils.constraint_exists(conn, SCHEMA_REF, OLD_UQ):
        op.drop_constraint(OLD_UQ, TABLE, schema=SCHEMA_REF, type_="unique")
    if not column_utils.constraint_exists(conn, SCHEMA_REF, NEW_UQ):
        op.create_unique_constraint(
            NEW_UQ,
            TABLE,
            ["database_version_id", "name"],
            schema=SCHEMA_REF,
        )


def downgrade():
    conn = op.get_bind()
    if column_utils.constraint_exists(conn, SCHEMA_REF, NEW_UQ):
        op.drop_constraint(NEW_UQ, TABLE, schema=SCHEMA_REF, type_="unique")
    if not column_utils.constraint_exists(conn, SCHEMA_REF, OLD_UQ):
        op.create_unique_constraint(
            OLD_UQ,
            TABLE,
            ["name"],
            schema=SCHEMA_REF,
        )

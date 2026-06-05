# -*- coding: utf-8 -*-
"""ВЭД: уникальность name в пределах версии БД (не глобально).

Revision ID: y3z4a5b6c7d8
Revises: x2y3z4a5b6c7
Create Date: 2026-06-03
"""
import os
import sys

from alembic import op

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "y3z4a5b6c7d8"
down_revision = "x2y3z4a5b6c7"
branch_labels = None
depends_on = None

SCHEMA_REF = "gs_sys"
TABLE = "gs_sys_economic_activity_types"
OLD_UQ = "uq_gs_sys_economic_activity_types_name"
NEW_UQ = "uq_gs_sys_economic_activity_types_ver_name"


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

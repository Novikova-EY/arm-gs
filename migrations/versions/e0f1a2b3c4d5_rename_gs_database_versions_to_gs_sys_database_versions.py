# -*- coding: utf-8 -*-
"""rename gs_sys.gs_database_versions -> gs_sys.gs_sys_database_versions

Revision ID: e0f1a2b3c4d5
Revises: d0e1f2a3b4c5
Create Date: 2026-04-24
"""
import os
import sys

from alembic import op

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "e0f1a2b3c4d5"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None

SCHEMA = "gs_sys"
OLD_NAME = "gs_database_versions"
NEW_NAME = "gs_sys_database_versions"


def upgrade():
    conn = op.get_bind()
    if column_utils.table_exists(conn, SCHEMA, OLD_NAME) and not column_utils.table_exists(conn, SCHEMA, NEW_NAME):
        op.rename_table(OLD_NAME, NEW_NAME, schema=SCHEMA)


def downgrade():
    conn = op.get_bind()
    if column_utils.table_exists(conn, SCHEMA, NEW_NAME) and not column_utils.table_exists(conn, SCHEMA, OLD_NAME):
        op.rename_table(NEW_NAME, OLD_NAME, schema=SCHEMA)

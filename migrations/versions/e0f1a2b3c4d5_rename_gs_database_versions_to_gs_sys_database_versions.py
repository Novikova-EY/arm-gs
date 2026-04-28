# -*- coding: utf-8 -*-
"""rename gs_sys.gs_database_versions -> gs_sys.gs_sys_database_versions

Revision ID: e0f1a2b3c4d5
Revises: d0e1f2a3b4c5
Create Date: 2026-04-24
"""
from alembic import op

revision = "e0f1a2b3c4d5"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None

SCHEMA = "gs_sys"
OLD_NAME = "gs_database_versions"
NEW_NAME = "gs_sys_database_versions"


def upgrade():
    op.rename_table(OLD_NAME, NEW_NAME, schema=SCHEMA)


def downgrade():
    op.rename_table(NEW_NAME, OLD_NAME, schema=SCHEMA)

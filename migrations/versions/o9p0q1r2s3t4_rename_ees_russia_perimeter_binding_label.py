# -*- coding: utf-8 -*-
"""Привязки ees_russia: подпись «ЕЭС России» → «ЭЭС России» на странице вариантов периметра.

Revision ID: o9p0q1r2s3t4
Revises: n8o9p0q1r2s3
Create Date: 2026-05-22
"""
from alembic import op
from sqlalchemy import text

revision = "o9p0q1r2s3t4"
down_revision = "n8o9p0q1r2s3"
branch_labels = None
depends_on = None

SCHEMA_REF = "gs_sys"
TABLE_BINDINGS = "gs_sys_entity_perimeter_bindings"

OLD_NAME = "ЕЭС России"
NEW_NAME = "ЭЭС России"


def upgrade():
    conn = op.get_bind()
    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA_REF}.{TABLE_BINDINGS}
            SET entity_name = :new_name,
                label_prefix = :new_name,
                modified_by = 'migration'
            WHERE entity_kind = 'ees_russia'
              AND entity_name = :old_name
            """
        ),
        {"old_name": OLD_NAME, "new_name": NEW_NAME},
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA_REF}.{TABLE_BINDINGS}
            SET entity_name = :old_name,
                label_prefix = :old_name,
                modified_by = 'migration'
            WHERE entity_kind = 'ees_russia'
              AND entity_name = :new_name
            """
        ),
        {"old_name": OLD_NAME, "new_name": NEW_NAME},
    )

# -*- coding: utf-8 -*-
"""add_machine_relabing_outcome

Revision ID: a6b7c8d9e0f1
Revises: r1s2t3u4v5w6
Create Date: 2026-04-24

Добавляет в machines поле relabing_outcome (тип перемаркировки: окончательный вывод / замена / новый ввод).
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "a6b7c8d9e0f1"
down_revision = "r1s2t3u4v5w6"
branch_labels = None
depends_on = None

SCHEMA = "gs_gen"
TABLE = "machines"


def upgrade():
    conn = op.get_bind()
    if not column_utils.table_has_column(conn, SCHEMA, TABLE, "relabing_outcome"):
        op.add_column(
            TABLE,
            sa.Column("relabing_outcome", sa.String(64), nullable=True),
            schema=SCHEMA,
        )


def downgrade():
    op.drop_column(TABLE, "relabing_outcome", schema=SCHEMA)

"""add_change_document_to_pgu_machines

Revision ID: m5n6o7p8q9r0
Revises: l4m5n6o7p8q9
Create Date: 2026-03-18

Добавляет в pgu_machines поле change_document (документ-основание для изменения параметров агрегата).
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils


revision = "m5n6o7p8q9r0"
down_revision = "l4m5n6o7p8q9"
branch_labels = None
depends_on = None

SCHEMA = "gs_gen"
TABLE = "pgu_machines"


def upgrade():
    conn = op.get_bind()
    if not column_utils.table_has_column(conn, SCHEMA, TABLE, "change_document"):
        op.add_column(
            TABLE,
            sa.Column("change_document", sa.Text(), nullable=True),
            schema=SCHEMA,
        )


def downgrade():
    op.drop_column(TABLE, "change_document", schema=SCHEMA)

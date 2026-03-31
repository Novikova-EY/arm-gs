"""add_change_document_to_pgu_machines

Revision ID: m5n6o7p8q9r0
Revises: l4m5n6o7p8q9
Create Date: 2026-03-18

Добавляет в pgu_machines поле change_document (документ-основание для изменения параметров агрегата).
"""
from alembic import op
import sqlalchemy as sa


revision = "m5n6o7p8q9r0"
down_revision = "l4m5n6o7p8q9"
branch_labels = None
depends_on = None

SCHEMA = "gs_gen"
TABLE = "pgu_machines"


def upgrade():
    op.add_column(
        TABLE,
        sa.Column("change_document", sa.Text(), nullable=True),
        schema=SCHEMA,
    )


def downgrade():
    op.drop_column(TABLE, "change_document", schema=SCHEMA)

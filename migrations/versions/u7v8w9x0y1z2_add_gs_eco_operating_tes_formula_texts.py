# -*- coding: utf-8 -*-
"""Таблица переопределений текстов формул расчёта по действующим ТЭС.

Revision ID: u7v8w9x0y1z2
Revises: t6u7v8w9x0y1
Create Date: 2026-08-31
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "u7v8w9x0y1z2"
down_revision = "t6u7v8w9x0y1"
branch_labels = None
depends_on = None

SCHEMA = "gs_eco"
TABLE = "gs_eco_operating_tes_formula_texts"
IX_FORMULA_KEY = f"ix_{TABLE}_formula_key"


def upgrade():
    conn = op.get_bind()
    if column_utils.table_exists(conn, SCHEMA, TABLE):
        if not column_utils.index_exists(conn, SCHEMA, IX_FORMULA_KEY):
            op.create_index(
                IX_FORMULA_KEY,
                TABLE,
                ["formula_key"],
                unique=False,
                schema=SCHEMA,
            )
        return

    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("formula_key", sa.String(length=128), nullable=False),
        sa.Column("formula_text", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("formula_key", name="uq_gs_eco_operating_tes_formula_texts_key"),
        schema=SCHEMA,
    )
    op.create_index(
        IX_FORMULA_KEY,
        TABLE,
        ["formula_key"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade():
    conn = op.get_bind()
    if column_utils.index_exists(conn, SCHEMA, IX_FORMULA_KEY):
        op.drop_index(IX_FORMULA_KEY, table_name=TABLE, schema=SCHEMA)
    if column_utils.table_exists(conn, SCHEMA, TABLE):
        op.drop_table(TABLE, schema=SCHEMA)

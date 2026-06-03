# -*- coding: utf-8 -*-
"""Таблица переопределений текстов формул сводок потребления ЭЭ.

Revision ID: v0w1x2y3z4a5
Revises: u9v0w1x2y3z4
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa

revision = "v0w1x2y3z4a5"
down_revision = "u9v0w1x2y3z4"
branch_labels = None
depends_on = None

SCHEMA = "gs_ec"
TABLE = "gs_ec_summary_formula_texts"


def upgrade():
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
        sa.UniqueConstraint("formula_key", name="uq_gs_ec_summary_formula_texts_key"),
        schema=SCHEMA,
    )
    op.create_index(
        f"ix_{TABLE}_formula_key",
        TABLE,
        ["formula_key"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade():
    op.drop_index(f"ix_{TABLE}_formula_key", table_name=TABLE, schema=SCHEMA)
    op.drop_table(TABLE, schema=SCHEMA)

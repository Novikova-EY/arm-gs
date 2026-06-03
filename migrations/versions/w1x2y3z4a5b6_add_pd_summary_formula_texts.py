# -*- coding: utf-8 -*-
"""Таблица переопределений текстов формул сводок модуля «Нагрузки».

Revision ID: w1x2y3z4a5b6
Revises: v0w1x2y3z4a5
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa

revision = "w1x2y3z4a5b6"
down_revision = "v0w1x2y3z4a5"
branch_labels = None
depends_on = None

SCHEMA = "gs_pd"
TABLE = "gs_pd_summary_formula_texts"


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
        sa.UniqueConstraint("formula_key", name="uq_gs_pd_summary_formula_texts_key"),
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

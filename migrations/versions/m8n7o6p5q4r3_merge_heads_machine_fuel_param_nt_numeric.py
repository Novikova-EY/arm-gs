# -*- coding: utf-8 -*-
"""Поле nt в gs_fue_machine_fuel_param: Integer -> Numeric(12,6) (тепловая мощность с дробью).

Revision ID: m8n7o6p5q4r3
Revises: a4b5c6d7e8f9, r3s4t5u6v7w8
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa

revision = "m8n7o6p5q4r3"
down_revision = ("a4b5c6d7e8f9", "r3s4t5u6v7w8")
branch_labels = None
depends_on = None

SCHEMA = "gs_fue"
TABLE = "gs_fue_machine_fuel_param"
COL = "nt"


def upgrade():
    op.alter_column(
        TABLE,
        COL,
        existing_type=sa.Integer(),
        type_=sa.Numeric(precision=12, scale=6),
        existing_nullable=True,
        schema=SCHEMA,
        postgresql_using="nt::numeric(12,6)",
    )


def downgrade():
    op.alter_column(
        TABLE,
        COL,
        existing_type=sa.Numeric(precision=12, scale=6),
        type_=sa.Integer(),
        existing_nullable=True,
        schema=SCHEMA,
        postgresql_using="ROUND(nt)::integer",
    )

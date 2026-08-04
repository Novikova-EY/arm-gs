# -*- coding: utf-8 -*-
"""HFIX/H на fuel_param + bbas/snbas/ksn/kh на удельных (порт Access).

Revision ID: j3k4l5m6n7o8
Revises: i2j3k4l5m6n7
Create Date: 2026-07-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "j3k4l5m6n7o8"
down_revision = "i2j3k4l5m6n7"
branch_labels = None
depends_on = None

SCHEMA = "gs_fue"
FUEL_PARAM = "gs_fue_equipment_group_fuel_param"
SPECIFIC = "gs_fue_equipment_group_specific_fuel_consumption"

FUEL_PARAM_COLS = (
    ("h", sa.Numeric(precision=36, scale=16)),
    ("hfix", sa.Integer()),
)
SPECIFIC_COLS = (
    ("bbas", sa.Numeric(precision=36, scale=16)),
    ("snbas", sa.Numeric(precision=36, scale=16)),
    ("ksn", sa.Numeric(precision=36, scale=16)),
    ("kh", sa.Numeric(precision=36, scale=16)),
)


def _column_exists(connection, schema, table, column) -> bool:
    row = connection.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :column"
        ),
        {"schema": schema, "table": table, "column": column},
    ).fetchone()
    return row is not None


def upgrade():
    conn = op.get_bind()
    for name, col_type in FUEL_PARAM_COLS:
        if not _column_exists(conn, SCHEMA, FUEL_PARAM, name):
            op.add_column(FUEL_PARAM, sa.Column(name, col_type, nullable=True), schema=SCHEMA)
    for name, col_type in SPECIFIC_COLS:
        if not _column_exists(conn, SCHEMA, SPECIFIC, name):
            op.add_column(SPECIFIC, sa.Column(name, col_type, nullable=True), schema=SCHEMA)


def downgrade():
    conn = op.get_bind()
    for name, _ in reversed(SPECIFIC_COLS):
        if _column_exists(conn, SCHEMA, SPECIFIC, name):
            op.drop_column(SPECIFIC, name, schema=SCHEMA)
    for name, _ in reversed(FUEL_PARAM_COLS):
        if _column_exists(conn, SCHEMA, FUEL_PARAM, name):
            op.drop_column(FUEL_PARAM, name, schema=SCHEMA)

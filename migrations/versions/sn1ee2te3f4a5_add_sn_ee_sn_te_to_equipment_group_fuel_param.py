# -*- coding: utf-8 -*-
"""Add sn_ee / sn_te absolute СН fields to equipment_group_fuel_param.

Revision ID: sn1ee2te3f4a5
Revises: c3d4e5f6a7b8
Create Date: 2026-08-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "sn1ee2te3f4a5"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None

SCHEMA = "gs_fue"
TABLE = "gs_fue_equipment_group_fuel_param"

COLS = (
    ("sn_ee", "СН на производство электроэнергии, тыс. кВт·ч (числитель snk)"),
    ("sn_te", "СН на отпуск тепловой энергии, тыс. кВт·ч (числитель sn_t / SNT)"),
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
    for name, comment in COLS:
        if not _column_exists(conn, SCHEMA, TABLE, name):
            op.add_column(
                TABLE,
                sa.Column(name, sa.Numeric(precision=36, scale=16), nullable=True),
                schema=SCHEMA,
            )
        conn.execute(
            text(f'COMMENT ON COLUMN "{SCHEMA}"."{TABLE}"."{name}" IS :c'),
            {"c": comment},
        )


def downgrade():
    conn = op.get_bind()
    for name, _ in reversed(COLS):
        if _column_exists(conn, SCHEMA, TABLE, name):
            op.drop_column(TABLE, name, schema=SCHEMA)

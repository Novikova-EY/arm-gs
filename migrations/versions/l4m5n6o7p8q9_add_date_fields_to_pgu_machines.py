"""add_date_commission_year_date_exploitation_expected_to_pgu_machines

Revision ID: l4m5n6o7p8q9
Revises: k3l4m5n6o7p8
Create Date: 2026-03-18

Добавляет в pgu_machines поля date_commission_year и date_exploitation_expected
для соответствия machine_model (фактический год ввода в работу, ожидаемый год ввода в эксплуатацию).
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils


revision = "l4m5n6o7p8q9"
down_revision = "k3l4m5n6o7p8"
branch_labels = None
depends_on = None

SCHEMA = "gs_gen"


def upgrade():
    conn = op.get_bind()
    table = column_utils.pgu_machines_table_name(conn, SCHEMA)
    if table is None:
        return
    if not column_utils.table_has_column(conn, SCHEMA, table, "date_commission_year"):
        op.add_column(
            table,
            sa.Column("date_commission_year", sa.Integer(), nullable=True),
            schema=SCHEMA,
        )
    if not column_utils.table_has_column(conn, SCHEMA, table, "date_exploitation_expected"):
        op.add_column(
            table,
            sa.Column("date_exploitation_expected", sa.Integer(), nullable=True),
            schema=SCHEMA,
        )


def downgrade():
    conn = op.get_bind()
    table = column_utils.pgu_machines_table_name(conn, SCHEMA)
    if table is None:
        return
    if column_utils.table_has_column(conn, SCHEMA, table, "date_commission_year"):
        op.drop_column(table, "date_commission_year", schema=SCHEMA)
    if column_utils.table_has_column(conn, SCHEMA, table, "date_exploitation_expected"):
        op.drop_column(table, "date_exploitation_expected", schema=SCHEMA)

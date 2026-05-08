# -*- coding: utf-8 -*-
"""gaes_tep_source: единичная мощность агрегата — генераторный и насосный режим.

Revision ID: n5o6p7q8r9s0
Revises: l9m0n1o2p3q4
Create Date: 2026-04-13
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "n5o6p7q8r9s0"
down_revision = "l9m0n1o2p3q4"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"


def upgrade():
    conn = op.get_bind()
    table = column_utils.gaes_tep_source_project_indicators_table_name(conn, SCHEMA_GEN)
    if table is None:
        return
    gen_col = "unit_capacity_mw_generator_mode"
    pump_col = "unit_capacity_mw_pump_mode"
    merged_col = "unit_capacity_mw"

    if not column_utils.table_has_column(conn, SCHEMA_GEN, table, gen_col):
        op.add_column(
            table,
            sa.Column(gen_col, sa.String(length=100), nullable=True),
            schema=SCHEMA_GEN,
        )
    if not column_utils.table_has_column(conn, SCHEMA_GEN, table, pump_col):
        op.add_column(
            table,
            sa.Column(pump_col, sa.String(length=100), nullable=True),
            schema=SCHEMA_GEN,
        )

    if column_utils.table_has_column(conn, SCHEMA_GEN, table, merged_col):
        op.execute(
            sa.text(
                f"""
                UPDATE {SCHEMA_GEN}.{table}
                SET {gen_col} = {merged_col},
                    {pump_col} = {merged_col}
                WHERE {merged_col} IS NOT NULL
                """
            )
        )
        op.drop_column(table, merged_col, schema=SCHEMA_GEN)


def downgrade():
    conn = op.get_bind()
    table = column_utils.gaes_tep_source_project_indicators_table_name(conn, SCHEMA_GEN)
    if table is None:
        return
    gen_col = "unit_capacity_mw_generator_mode"
    pump_col = "unit_capacity_mw_pump_mode"
    merged_col = "unit_capacity_mw"

    if not column_utils.table_has_column(conn, SCHEMA_GEN, table, merged_col):
        op.add_column(
            table,
            sa.Column(merged_col, sa.String(length=100), nullable=True),
            schema=SCHEMA_GEN,
        )

    op.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA_GEN}.{table}
            SET {merged_col} = COALESCE({gen_col}, {pump_col})
            """
        )
    )
    if column_utils.table_has_column(conn, SCHEMA_GEN, table, gen_col):
        op.drop_column(table, gen_col, schema=SCHEMA_GEN)
    if column_utils.table_has_column(conn, SCHEMA_GEN, table, pump_col):
        op.drop_column(table, pump_col, schema=SCHEMA_GEN)

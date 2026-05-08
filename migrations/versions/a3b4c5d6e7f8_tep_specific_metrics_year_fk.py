# -*- coding: utf-8 -*-
"""ges/gaes_tep_source: годы (Year) для удельных эксплуатационных затрат и удельных капвложений.

Revision ID: a3b4c5d6e7f8
Revises: p2q3r4s5t6u7
Create Date: 2026-04-14
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "a3b4c5d6e7f8"
down_revision = "p2q3r4s5t6u7"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REFDATA = "gs_sys"

TABLE_GES = "ges_tep_source_project_indicators"
TABLE_GAES = "gaes_tep_source_project_indicators"


def upgrade():
    conn = op.get_bind()
    table_years = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_years")
    if table_years is None:
        return
    for table, pfx in (
        (column_utils.ges_tep_source_project_indicators_table_name(conn, SCHEMA_GEN), "ges_tep"),
        (column_utils.gaes_tep_source_project_indicators_table_name(conn, SCHEMA_GEN), "gaes_tep"),
    ):
        if table is None:
            continue
        for col in (
            "id_year_specific_semifixed_operating_costs",
            "id_year_specific_capital_investment",
        ):
            if not column_utils.table_has_column(conn, SCHEMA_GEN, table, col):
                op.add_column(
                    table,
                    sa.Column(col, sa.Integer(), nullable=True),
                    schema=SCHEMA_GEN,
                )
        if not column_utils.constraint_exists(conn, SCHEMA_GEN, f"fk_{pfx}_src_year_spec_semifixed"):
            op.create_foreign_key(
                f"fk_{pfx}_src_year_spec_semifixed",
                table,
                table_years,
                ["id_year_specific_semifixed_operating_costs"],
                ["id"],
                source_schema=SCHEMA_GEN,
                referent_schema=SCHEMA_REFDATA,
                ondelete="SET NULL",
            )
        if not column_utils.constraint_exists(conn, SCHEMA_GEN, f"fk_{pfx}_src_year_spec_capital"):
            op.create_foreign_key(
                f"fk_{pfx}_src_year_spec_capital",
                table,
                table_years,
                ["id_year_specific_capital_investment"],
                ["id"],
                source_schema=SCHEMA_GEN,
                referent_schema=SCHEMA_REFDATA,
                ondelete="SET NULL",
            )
        if not column_utils.index_exists(conn, SCHEMA_GEN, f"ix_{pfx}_src_id_year_spec_semifixed"):
            op.create_index(
                f"ix_{pfx}_src_id_year_spec_semifixed",
                table,
                ["id_year_specific_semifixed_operating_costs"],
                unique=False,
                schema=SCHEMA_GEN,
            )
        if not column_utils.index_exists(conn, SCHEMA_GEN, f"ix_{pfx}_src_id_year_spec_capital"):
            op.create_index(
                f"ix_{pfx}_src_id_year_spec_capital",
                table,
                ["id_year_specific_capital_investment"],
                unique=False,
                schema=SCHEMA_GEN,
            )


def downgrade():
    for table, pfx in (
        (TABLE_GAES, "gaes_tep"),
        (TABLE_GES, "ges_tep"),
    ):
        op.drop_index(
            f"ix_{pfx}_src_id_year_spec_capital",
            table_name=table,
            schema=SCHEMA_GEN,
        )
        op.drop_index(
            f"ix_{pfx}_src_id_year_spec_semifixed",
            table_name=table,
            schema=SCHEMA_GEN,
        )
        op.drop_constraint(
            f"fk_{pfx}_src_year_spec_capital",
            table,
            type_="foreignkey",
            schema=SCHEMA_GEN,
        )
        op.drop_constraint(
            f"fk_{pfx}_src_year_spec_semifixed",
            table,
            type_="foreignkey",
            schema=SCHEMA_GEN,
        )
        op.drop_column(table, "id_year_specific_capital_investment", schema=SCHEMA_GEN)
        op.drop_column(table, "id_year_specific_semifixed_operating_costs", schema=SCHEMA_GEN)

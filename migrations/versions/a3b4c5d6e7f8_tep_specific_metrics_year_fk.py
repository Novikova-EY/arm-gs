# -*- coding: utf-8 -*-
"""ges/gaes_tep_source: годы (Year) для удельных эксплуатационных затрат и удельных капвложений.

Revision ID: a3b4c5d6e7f8
Revises: p2q3r4s5t6u7
Create Date: 2026-04-14
"""
from alembic import op
import sqlalchemy as sa

revision = "a3b4c5d6e7f8"
down_revision = "p2q3r4s5t6u7"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REFDATA = "gs_sys"

TABLE_GES = "ges_tep_source_project_indicators"
TABLE_GAES = "gaes_tep_source_project_indicators"


def upgrade():
    for table, pfx in (
        (TABLE_GES, "ges_tep"),
        (TABLE_GAES, "gaes_tep"),
    ):
        op.add_column(
            table,
            sa.Column("id_year_specific_semifixed_operating_costs", sa.Integer(), nullable=True),
            schema=SCHEMA_GEN,
        )
        op.add_column(
            table,
            sa.Column("id_year_specific_capital_investment", sa.Integer(), nullable=True),
            schema=SCHEMA_GEN,
        )
        op.create_foreign_key(
            f"fk_{pfx}_src_year_spec_semifixed",
            table,
            "gs_years",
            ["id_year_specific_semifixed_operating_costs"],
            ["id"],
            source_schema=SCHEMA_GEN,
            referent_schema=SCHEMA_REFDATA,
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            f"fk_{pfx}_src_year_spec_capital",
            table,
            "gs_years",
            ["id_year_specific_capital_investment"],
            ["id"],
            source_schema=SCHEMA_GEN,
            referent_schema=SCHEMA_REFDATA,
            ondelete="SET NULL",
        )
        op.create_index(
            f"ix_{pfx}_src_id_year_spec_semifixed",
            table,
            ["id_year_specific_semifixed_operating_costs"],
            unique=False,
            schema=SCHEMA_GEN,
        )
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

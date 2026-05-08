# -*- coding: utf-8 -*-
"""machine_prospective_place_aes: годы (Year) для удельных показателей ТЭП с пересчётом цен.

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-04-21
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "c6d7e8f9a0b1"
down_revision = "b5c6d7e8f9a0"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REFDATA = "gs_sys"
TABLE = "machine_prospective_place_aes"


def upgrade():
    conn = op.get_bind()
    table = column_utils.machine_prospective_place_aes_table_name(conn, SCHEMA_GEN)
    table_years = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_years")
    if table is None or table_years is None:
        return
    cols = (
        ("id_year_specific_fuel_cost", "fk_mpp_aes_year_spec_fuel", "ix_mpp_aes_id_year_spec_fuel"),
        (
            "id_year_specific_fixed_operating_costs",
            "fk_mpp_aes_year_spec_fixed_op",
            "ix_mpp_aes_id_year_spec_fixed_op",
        ),
        ("id_year_specific_capital_investment", "fk_mpp_aes_year_spec_cap", "ix_mpp_aes_id_year_spec_cap"),
        ("id_year_specific_decommissioning", "fk_mpp_aes_year_spec_decom", "ix_mpp_aes_id_year_spec_decom"),
    )
    for col_name, fk_name, ix_name in cols:
        if not column_utils.table_has_column(conn, SCHEMA_GEN, table, col_name):
            op.add_column(
                table,
                sa.Column(col_name, sa.Integer(), nullable=True),
                schema=SCHEMA_GEN,
            )
        if not column_utils.constraint_exists(conn, SCHEMA_GEN, fk_name):
            op.create_foreign_key(
                fk_name,
                table,
                table_years,
                [col_name],
                ["id"],
                source_schema=SCHEMA_GEN,
                referent_schema=SCHEMA_REFDATA,
                ondelete="SET NULL",
            )
        if not column_utils.index_exists(conn, SCHEMA_GEN, ix_name):
            op.create_index(ix_name, table, [col_name], unique=False, schema=SCHEMA_GEN)


def downgrade():
    conn = op.get_bind()
    table = column_utils.machine_prospective_place_aes_table_name(conn, SCHEMA_GEN)
    if table is None:
        return
    cols = (
        ("id_year_specific_decommissioning", "fk_mpp_aes_year_spec_decom", "ix_mpp_aes_id_year_spec_decom"),
        ("id_year_specific_capital_investment", "fk_mpp_aes_year_spec_cap", "ix_mpp_aes_id_year_spec_cap"),
        (
            "id_year_specific_fixed_operating_costs",
            "fk_mpp_aes_year_spec_fixed_op",
            "ix_mpp_aes_id_year_spec_fixed_op",
        ),
        ("id_year_specific_fuel_cost", "fk_mpp_aes_year_spec_fuel", "ix_mpp_aes_id_year_spec_fuel"),
    )
    for col_name, fk_name, ix_name in cols:
        if column_utils.index_exists(conn, SCHEMA_GEN, ix_name):
            op.drop_index(ix_name, table_name=table, schema=SCHEMA_GEN)
        if column_utils.constraint_exists(conn, SCHEMA_GEN, fk_name):
            op.drop_constraint(fk_name, table, schema=SCHEMA_GEN, type_="foreignkey")
        if column_utils.table_has_column(conn, SCHEMA_GEN, table, col_name):
            op.drop_column(table, col_name, schema=SCHEMA_GEN)

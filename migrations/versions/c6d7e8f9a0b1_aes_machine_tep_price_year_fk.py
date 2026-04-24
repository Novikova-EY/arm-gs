# -*- coding: utf-8 -*-
"""machine_prospective_place_aes: годы (Year) для удельных показателей ТЭП с пересчётом цен.

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-04-21
"""
from alembic import op
import sqlalchemy as sa

revision = "c6d7e8f9a0b1"
down_revision = "b5c6d7e8f9a0"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REFDATA = "gs_sys"
TABLE = "machine_prospective_place_aes"


def upgrade():
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
        op.add_column(
            TABLE,
            sa.Column(col_name, sa.Integer(), nullable=True),
            schema=SCHEMA_GEN,
        )
        op.create_foreign_key(
            fk_name,
            TABLE,
            "gs_years",
            [col_name],
            ["id"],
            source_schema=SCHEMA_GEN,
            referent_schema=SCHEMA_REFDATA,
            ondelete="SET NULL",
        )
        op.create_index(ix_name, TABLE, [col_name], unique=False, schema=SCHEMA_GEN)


def downgrade():
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
        op.drop_index(ix_name, table_name=TABLE, schema=SCHEMA_GEN)
        op.drop_constraint(fk_name, TABLE, schema=SCHEMA_GEN, type_="foreignkey")
        op.drop_column(TABLE, col_name, schema=SCHEMA_GEN)

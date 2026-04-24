"""add_machine_prospective_place_aes

Revision ID: p8q9r0s1t2u3
Revises: o7p8q9r0s1t2
Create Date: 2026-03-19

Создает таблицу machine_prospective_place_aes (энергоблоки перспективных площадок размещения АЭС).
"""
from alembic import op
import sqlalchemy as sa


revision = "p8q9r0s1t2u3"
down_revision = "o7p8q9r0s1t2"
branch_labels = None
depends_on = None

SCHEMA = "gs_gen"
SCHEMA_REF = "gs_sys"
TABLE = "machine_prospective_place_aes"


def upgrade():
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_station_prospective_place_aes", sa.Integer(), nullable=True),
        sa.Column("station_block_number", sa.Numeric(36, 15), nullable=True),
        sa.Column("unit_type", sa.String(length=255), nullable=True),
        sa.Column("unit_capacity_mw", sa.String(length=100), nullable=True),
        sa.Column("site_type", sa.String(length=255), nullable=True),
        sa.Column("max_annual_operating_hours", sa.String(length=100), nullable=True),
        sa.Column("specific_fuel_cost_rub_per_kwh", sa.String(length=100), nullable=True),
        sa.Column("specific_fixed_operating_costs_thous_rub_per_kw", sa.String(length=100), nullable=True),
        sa.Column("relative_auxiliary_power_consumption_pct", sa.String(length=100), nullable=True),
        sa.Column("specific_capital_investment_thous_rub_per_kw", sa.String(length=100), nullable=True),
        sa.Column("specific_decommissioning_cost_thous_rub_per_kw", sa.String(length=100), nullable=True),
        sa.Column("emergency_state_probability", sa.String(length=100), nullable=True),
        sa.Column("relative_planned_outage_duration", sa.String(length=100), nullable=True),
        sa.Column("ozp", sa.String(length=100), nullable=True),
        sa.Column("vlp", sa.String(length=100), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("selection_factor", sa.String(length=255), nullable=True),
        sa.Column("possible_implementation_period", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_machine_prospective_place_aes_id_station_prospective_place",
        TABLE,
        ["id_station_prospective_place_aes"],
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_machine_prospective_place_aes_station",
        TABLE,
        "station_prospective_place_aes",
        ["id_station_prospective_place_aes"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_machine_prospective_place_aes_database_version",
        TABLE,
        "gs_database_versions",
        ["database_version_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA_REF,
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint(
        "fk_machine_prospective_place_aes_database_version",
        TABLE,
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_machine_prospective_place_aes_station",
        TABLE,
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_index(
        "ix_machine_prospective_place_aes_id_station_prospective_place",
        table_name=TABLE,
        schema=SCHEMA,
    )
    op.drop_table(TABLE, schema=SCHEMA)

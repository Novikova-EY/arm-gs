"""add_machine_prospective_place_aes

Revision ID: p8q9r0s1t2u3
Revises: o7p8q9r0s1t2
Create Date: 2026-03-19

Создает таблицу machine_prospective_place_aes (энергоблоки перспективных площадок размещения АЭС).
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402


revision = "p8q9r0s1t2u3"
down_revision = "o7p8q9r0s1t2"
branch_labels = None
depends_on = None

SCHEMA = "gs_gen"
SCHEMA_REF = "gs_sys"
TABLE = "machine_prospective_place_aes"


def upgrade():
    conn = op.get_bind()
    # Уже есть под старым или новым именем (в т.ч. после c2d3e4f5a6b7).
    if column_utils.machine_prospective_place_aes_table_name(conn, SCHEMA) is not None:
        return
    ref_station = column_utils.station_prospective_place_aes_table_name(conn, SCHEMA)
    if ref_station is None:
        return
    ref_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REF)
    if ref_versions is None:
        raise RuntimeError(
            f"Не найдена таблица версий БД в {SCHEMA_REF} "
            "(gs_sys_database_versions или gs_database_versions как BASE TABLE)"
        )
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
        ref_station,
        ["id_station_prospective_place_aes"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_machine_prospective_place_aes_database_version",
        TABLE,
        ref_versions,
        ["database_version_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA_REF,
        ondelete="SET NULL",
    )


def downgrade():
    conn = op.get_bind()
    tbl = column_utils.machine_prospective_place_aes_table_name(conn, SCHEMA)
    if tbl is None:
        return
    op.drop_constraint(
        "fk_machine_prospective_place_aes_database_version",
        tbl,
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_machine_prospective_place_aes_station",
        tbl,
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_index(
        "ix_machine_prospective_place_aes_id_station_prospective_place",
        table_name=tbl,
        schema=SCHEMA,
    )
    op.drop_table(tbl, schema=SCHEMA)

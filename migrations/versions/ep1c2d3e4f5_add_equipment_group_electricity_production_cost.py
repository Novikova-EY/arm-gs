# -*- coding: utf-8 -*-
"""Затраты ТЭС на производство ЭЭ и ТЭ для групп оборудования.

Revision ID: ep1c2d3e4f5
Revises: f6a7b8c9d0e1
Create Date: 2026-06-29
"""
import os
import sys

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "ep1c2d3e4f5"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None

SCHEMA = "gs_fue"
TABLE = "gs_fue_equipment_group_electricity_production_cost"


def _table_exists(connection):
    result = connection.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :table"
        ),
        {"schema": SCHEMA, "table": TABLE},
    )
    return result.fetchone() is not None


def upgrade():
    conn = op.get_bind()
    if _table_exists(conn):
        return
    ref_versions = column_utils.database_versions_physical_table_name(conn, "gs_sys")
    if ref_versions is None:
        raise RuntimeError(
            "Не найдена таблица версий БД в gs_sys "
            "(gs_sys_database_versions или gs_database_versions как BASE TABLE)"
        )
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("equipment_group_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=512), nullable=True),
        sa.Column("year_number", sa.Integer(), nullable=True),
        sa.Column("cost_code", sa.Integer(), nullable=True),
        sa.Column("zatraty_sum", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("zatr_e", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("zatr_p", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("zatr_q", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("numb1120", sa.Integer(), nullable=True),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            [f"gs_sys.{ref_versions}.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["equipment_group_id"],
            ["gs_fue.gs_fue_equipment_groups.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "equipment_group_id",
            "year_number",
            "cost_code",
            name="uq_equipment_group_electricity_production_cost_group_year_code",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_fue_eg_electricity_production_cost_equipment_group_id",
        TABLE,
        ["equipment_group_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_fue_eg_electricity_production_cost_year_number",
        TABLE,
        ["year_number"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_fue_eg_electricity_production_cost_cost_code",
        TABLE,
        ["cost_code"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_fue_eg_electricity_production_cost_numb1120",
        TABLE,
        ["numb1120"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_fue_eg_electricity_production_cost_database_version_id",
        TABLE,
        ["database_version_id"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade():
    op.drop_table(TABLE, schema=SCHEMA)

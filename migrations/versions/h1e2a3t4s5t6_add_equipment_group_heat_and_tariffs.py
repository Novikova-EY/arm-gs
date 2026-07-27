# -*- coding: utf-8 -*-
"""Тепло и тарифы из схем теплоснабжения для групп оборудования.

Revision ID: h1e2a3t4s5t6
Revises: c2d3e4f5a6b8
Create Date: 2026-07-27
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

revision = "h1e2a3t4s5t6"
down_revision = "c2d3e4f5a6b8"
branch_labels = None
depends_on = None

SCHEMA = "gs_fue"
TABLE = "gs_fue_equipment_group_heat_and_tariffs"


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
        sa.Column("kod_goroda", sa.Integer(), nullable=True),
        sa.Column("name_goroda", sa.String(length=255), nullable=True),
        sa.Column("var_razv", sa.Integer(), nullable=True),
        sa.Column("name_eto", sa.Text(), nullable=True),
        sa.Column("numb1120", sa.Integer(), nullable=True),
        sa.Column("ndv_st", sa.Integer(), nullable=True),
        sa.Column("year_number", sa.Integer(), nullable=True),
        sa.Column("q", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("tarif", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
            "kod_goroda",
            "name_eto",
            "numb1120",
            "var_razv",
            "year_number",
            "database_version_id",
            name="uq_equipment_group_heat_and_tariffs_key",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_fue_eg_heat_and_tariffs_equipment_group_id",
        TABLE,
        ["equipment_group_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_fue_eg_heat_and_tariffs_kod_goroda",
        TABLE,
        ["kod_goroda"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_fue_eg_heat_and_tariffs_year_number",
        TABLE,
        ["year_number"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_fue_eg_heat_and_tariffs_numb1120",
        TABLE,
        ["numb1120"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_fue_eg_heat_and_tariffs_database_version_id",
        TABLE,
        ["database_version_id"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade():
    op.drop_table(TABLE, schema=SCHEMA)

# -*- coding: utf-8 -*-
"""Таблица gs_fue_equipment_group_coefficient_results (этап «Коэфф»).

Revision ID: c5d6e7f8a9b1
Revises: b4c5d6e7f8a0
Create Date: 2026-04-02
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


revision = "c5d6e7f8a9b1"
down_revision = "b4c5d6e7f8a0"
branch_labels = None
depends_on = None

SCHEMA = "gs_fue"
TABLE = "gs_fue_equipment_group_coefficient_results"


def _table_exists(connection, table: str) -> bool:
    result = connection.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :table"
        ),
        {"schema": SCHEMA, "table": table},
    )
    return result.fetchone() is not None


def upgrade():
    conn = op.get_bind()
    if _table_exists(conn, TABLE):
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
        sa.Column("equipment_group_id", sa.Integer(), nullable=False),
        sa.Column("distribution_parameter_id", sa.Integer(), nullable=False),
        sa.Column("year_number", sa.Integer(), nullable=False),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.Column("k", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("kplus", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("kmin", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("kn", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("knps", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("kngt", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("knpg", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("hnps", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("hngt", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("hnpg", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("doptim", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("lim", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("coeff_base", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("coeff_min", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("coeff_max", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("coeff_effective", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            [f"gs_sys.{ref_versions}.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["distribution_parameter_id"],
            ["gs_fue.gs_fue_distribution_parameters.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["equipment_group_id"],
            ["gs_fue.gs_fue_equipment_groups.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "equipment_group_id",
            "distribution_parameter_id",
            "year_number",
            "database_version_id",
            name="uq_eq_group_coeff_result_group_dist_year_version",
        ),
        schema=SCHEMA,
    )
    # Короткие имена: полное ix_<table>_database_version_id > 63 символов (PostgreSQL)
    op.create_index(
        "ix_fue_eg_coeff_res_eg_id",
        TABLE,
        ["equipment_group_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_fue_eg_coeff_res_dist_id",
        TABLE,
        ["distribution_parameter_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_fue_eg_coeff_res_year",
        TABLE,
        ["year_number"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_fue_eg_coeff_res_db_ver",
        TABLE,
        ["database_version_id"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade():
    conn = op.get_bind()
    if not _table_exists(conn, TABLE):
        return
    op.drop_table(TABLE, schema=SCHEMA)

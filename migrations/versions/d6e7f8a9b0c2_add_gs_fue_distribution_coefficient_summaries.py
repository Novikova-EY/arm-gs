# -*- coding: utf-8 -*-
"""Таблица gs_fue_distribution_coefficient_summaries (этап «Коэфф», агрегат по сценарию).

Revision ID: d6e7f8a9b0c2
Revises: c5d6e7f8a9b1
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


revision = "d6e7f8a9b0c2"
down_revision = "c5d6e7f8a9b1"
branch_labels = None
depends_on = None

SCHEMA = "gs_fue"
TABLE = "gs_fue_distribution_coefficient_summaries"


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
        sa.Column("distribution_parameter_id", sa.Integer(), nullable=False),
        sa.Column("year_number", sa.Integer(), nullable=False),
        sa.Column("base_year", sa.Integer(), nullable=True),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.Column("bnust", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("be", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("betp", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("bq", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("bqotr", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("cnust", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("cnustn", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("cnustngt", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("cnustnpg", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("cnustnps", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("cetp", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("cq", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("cqotr", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("bptp", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("cptp", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("bh", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("ch", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("ph1", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("pe", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("hd", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("kn", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("ph", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("pq", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("potr", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("e_target", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("k", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("kplus", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("kmin", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("knps", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("kngt", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("knpg", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("hnps", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("hngt", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("hnpg", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("doptim", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("lim", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            [f"gs_sys.{ref_versions}.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["distribution_parameter_id"],
            ["gs_fue.gs_fue_distribution_parameters.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "distribution_parameter_id",
            "year_number",
            "database_version_id",
            name="uq_fue_dist_coeff_summary_param_year_version",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_fue_dist_coeff_sum_param",
        TABLE,
        ["distribution_parameter_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_fue_dist_coeff_sum_year",
        TABLE,
        ["year_number"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_fue_dist_coeff_sum_db_ver",
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

# -*- coding: utf-8 -*-
"""Таблицы gs_ees_russia_demand_params и gs_ees_russia_with_nt_demand_params.

Revision ID: p0q1r2s3t4u5
Revises: n9o0p1q2r3s4
Create Date: 2026-04-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "p0q1r2s3t4u5"
down_revision = "n9o0p1q2r3s4"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
SCHEMA_REFDATA = "gs_sys"


def _schema_exists(connection, schema: str) -> bool:
    r = connection.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema"),
        {"schema": schema},
    )
    return r.fetchone() is not None


def _table_exists(connection, schema: str, table: str) -> bool:
    r = connection.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :table"
        ),
        {"schema": schema, "table": table},
    )
    return r.fetchone() is not None


def _create_ees_russia_table(
    table: str,
    ix_year: str,
    ix_dbver: str,
    uq_hist: str,
    uq_year: str,
) -> None:
    op.create_table(
        table,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("is_historical_maximum", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("year_number", sa.Integer(), nullable=True),
        sa.Column("max_power_consumption_mw", sa.Numeric(precision=25, scale=16), nullable=True),
        sa.Column("peak_datetime_msk", sa.DateTime(timezone=True), nullable=True),
        sa.Column("avg_daily_air_temp_c", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("combined_on_oes", sa.Numeric(precision=25, scale=16), nullable=True),
        sa.Column("combined_on_ees", sa.Numeric(precision=25, scale=16), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
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
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "(is_historical_maximum = true AND year_number IS NULL) OR "
            "(is_historical_maximum = false AND year_number IS NOT NULL)",
            name=f"ck_{table}_year_vs_hist",
        ),
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            [f"{SCHEMA_REFDATA}.gs_database_versions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA_PD,
    )
    op.create_index(ix_year, table, ["year_number"], unique=False, schema=SCHEMA_PD)
    op.create_index(ix_dbver, table, ["database_version_id"], unique=False, schema=SCHEMA_PD)
    op.execute(
        sa.text(
            f"""
            CREATE UNIQUE INDEX {uq_hist}
            ON "{SCHEMA_PD}"."{table}" (
                COALESCE(database_version_id, 0)
            )
            WHERE is_historical_maximum = true
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE UNIQUE INDEX {uq_year}
            ON "{SCHEMA_PD}"."{table}" (
                year_number,
                COALESCE(database_version_id, 0)
            )
            WHERE is_historical_maximum = false
            """
        )
    )


def upgrade():
    conn = op.get_bind()
    if not _schema_exists(conn, SCHEMA_PD):
        op.execute(sa.text(f'CREATE SCHEMA "{SCHEMA_PD}"'))

    t1 = "gs_ees_russia_demand_params"
    if not _table_exists(conn, SCHEMA_PD, t1):
        _create_ees_russia_table(
            t1,
            "ix_gs_ees_ru_dp_year",
            "ix_gs_ees_ru_dp_dbver",
            "uq_ees_russia_dp_hist",
            "uq_ees_russia_dp_year",
        )

    t2 = "gs_ees_russia_with_nt_demand_params"
    if not _table_exists(conn, SCHEMA_PD, t2):
        _create_ees_russia_table(
            t2,
            "ix_gs_ees_ru_nt_dp_year",
            "ix_gs_ees_ru_nt_dp_dbver",
            "uq_ees_russia_nt_dp_hist",
            "uq_ees_russia_nt_dp_year",
        )


def downgrade():
    conn = op.get_bind()
    for tbl in ("gs_ees_russia_with_nt_demand_params", "gs_ees_russia_demand_params"):
        if _table_exists(conn, SCHEMA_PD, tbl):
            op.execute(sa.text(f'DROP TABLE IF EXISTS "{SCHEMA_PD}"."{tbl}" CASCADE'))

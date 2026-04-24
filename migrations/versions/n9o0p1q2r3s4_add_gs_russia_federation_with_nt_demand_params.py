# -*- coding: utf-8 -*-
"""Таблица gs_russia_federation_with_nt_demand_params — РФ с новыми территориями (НТ).

Revision ID: n9o0p1q2r3s4
Revises: k1l2m3n4o5p6
Create Date: 2026-04-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "n9o0p1q2r3s4"
down_revision = "k1l2m3n4o5p6"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
SCHEMA_REFDATA = "gs_sys"
TABLE = "gs_russia_federation_with_nt_demand_params"


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


def upgrade():
    conn = op.get_bind()
    if not _schema_exists(conn, SCHEMA_PD):
        op.execute(sa.text(f'CREATE SCHEMA "{SCHEMA_PD}"'))

    if _table_exists(conn, SCHEMA_PD, TABLE):
        return

    op.create_table(
        TABLE,
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
            name=f"ck_{TABLE}_year_vs_hist",
        ),
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            [f"{SCHEMA_REFDATA}.gs_database_versions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA_PD,
    )
    # Имена короче 63 символов (лимит PostgreSQL на идентификатор)
    op.create_index(
        "ix_gs_rf_nt_dp_year",
        TABLE,
        ["year_number"],
        unique=False,
        schema=SCHEMA_PD,
    )
    op.create_index(
        "ix_gs_rf_nt_dp_dbver",
        TABLE,
        ["database_version_id"],
        unique=False,
        schema=SCHEMA_PD,
    )
    op.execute(
        sa.text(
            f"""
            CREATE UNIQUE INDEX uq_russia_federation_with_nt_demand_params_hist
            ON "{SCHEMA_PD}"."{TABLE}" (
                COALESCE(database_version_id, 0)
            )
            WHERE is_historical_maximum = true
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE UNIQUE INDEX uq_russia_federation_with_nt_demand_params_year
            ON "{SCHEMA_PD}"."{TABLE}" (
                year_number,
                COALESCE(database_version_id, 0)
            )
            WHERE is_historical_maximum = false
            """
        )
    )


def downgrade():
    conn = op.get_bind()
    if _table_exists(conn, SCHEMA_PD, TABLE):
        op.execute(sa.text(f'DROP TABLE IF EXISTS "{SCHEMA_PD}"."{TABLE}" CASCADE'))

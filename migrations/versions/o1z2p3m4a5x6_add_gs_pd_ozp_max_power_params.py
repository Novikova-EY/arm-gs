# -*- coding: utf-8 -*-
"""Таблица gs_pd_ozp_max_power_params — максимумы потребления мощности ОЗП.

Revision ID: o1z2p3m4a5x6
Revises: b0c1d2e3f4a6
Create Date: 2026-08-24
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

revision = "o1z2p3m4a5x6"
down_revision = "b0c1d2e3f4a6"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
SCHEMA_REFDATA = "gs_sys"
TABLE = "gs_pd_ozp_max_power_params"
UQ_INDEX = "uq_gs_pd_ozp_max_power_params_version_ozp"


def _schema_exists(connection, schema: str) -> bool:
    row = connection.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema"),
        {"schema": schema},
    ).fetchone()
    return row is not None


def upgrade():
    conn = op.get_bind()
    ref_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REFDATA)
    if ref_versions is None:
        raise RuntimeError(
            f"Не найдена таблица версий БД в {SCHEMA_REFDATA} "
            "(gs_sys_database_versions или gs_database_versions как BASE TABLE)"
        )
    if not _schema_exists(conn, SCHEMA_PD):
        op.execute(sa.text(f'CREATE SCHEMA "{SCHEMA_PD}"'))

    if not column_utils.table_exists(conn, SCHEMA_PD, TABLE):
        op.create_table(
            TABLE,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("ozp_end_year", sa.Integer(), nullable=False),
            sa.Column("max_power_mw", sa.Numeric(precision=25, scale=3), nullable=True),
            sa.Column("growth_pct", sa.Numeric(precision=12, scale=6), nullable=True),
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
            sa.ForeignKeyConstraint(
                ["database_version_id"],
                [f"{SCHEMA_REFDATA}.{ref_versions}.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA_PD,
        )
        op.create_index(
            "ix_gs_pd_ozp_max_power_params_ozp_end_year",
            TABLE,
            ["ozp_end_year"],
            unique=False,
            schema=SCHEMA_PD,
        )
        op.create_index(
            "ix_gs_pd_ozp_max_power_params_database_version_id",
            TABLE,
            ["database_version_id"],
            unique=False,
            schema=SCHEMA_PD,
        )

    if not column_utils.index_exists(conn, SCHEMA_PD, UQ_INDEX):
        op.execute(
            sa.text(
                f"""
                CREATE UNIQUE INDEX IF NOT EXISTS {UQ_INDEX}
                ON "{SCHEMA_PD}"."{TABLE}" (
                    ozp_end_year,
                    COALESCE(database_version_id, 0)
                )
                """
            )
        )


def downgrade():
    conn = op.get_bind()
    if column_utils.index_exists(conn, SCHEMA_PD, UQ_INDEX):
        op.execute(sa.text(f'DROP INDEX IF EXISTS "{SCHEMA_PD}"."{UQ_INDEX}"'))
    if column_utils.table_exists(conn, SCHEMA_PD, TABLE):
        op.drop_table(TABLE, schema=SCHEMA_PD)

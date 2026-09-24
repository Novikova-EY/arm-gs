# -*- coding: utf-8 -*-
"""Нормативы удельных выбросов расчёта по новым ТЭС.

Revision ID: z2a3b4c5d6e7
Revises: y1z2a3b4c5d6
Create Date: 2026-09-11
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

revision = "z2a3b4c5d6e7"
down_revision = "y1z2a3b4c5d6"
branch_labels = None
depends_on = None

SCHEMA_ECO = "gs_eco"
SCHEMA_REFDATA = "gs_sys"
TABLE_NORMS = "gs_eco_new_tes_norms"


def _schema_exists(connection, schema: str) -> bool:
    r = connection.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema"),
        {"schema": schema},
    )
    return r.fetchone() is not None


def _comment_on_table(conn, schema: str, table: str, comment: str) -> None:
    conn.execute(
        text(f'COMMENT ON TABLE "{schema}"."{table}" IS :comment'),
        {"comment": comment},
    )


def upgrade():
    conn = op.get_bind()
    ref_db_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REFDATA)
    if ref_db_versions is None:
        raise RuntimeError(f"Не найдена таблица версий БД в {SCHEMA_REFDATA}")
    years = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_years")
    if years is None:
        raise RuntimeError(f"Не найдена таблица годов в {SCHEMA_REFDATA}")
    if not _schema_exists(conn, SCHEMA_ECO):
        op.execute(sa.text(f'CREATE SCHEMA "{SCHEMA_ECO}"'))

    numeric = sa.Numeric(36, 16)
    if column_utils.table_exists(conn, SCHEMA_ECO, TABLE_NORMS):
        return
    op.create_table(
        TABLE_NORMS,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("fuel_key", sa.String(length=80), nullable=False),
        sa.Column("capacity_class", sa.String(length=16), nullable=False),
        sa.Column("year_number", sa.Integer(), nullable=False),
        sa.Column("ash", numeric, nullable=True),
        sa.Column("so2", numeric, nullable=True),
        sa.Column("nox", numeric, nullable=True),
        sa.Column("co", numeric, nullable=True),
        sa.Column("pg", numeric, nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
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
            ["year_number", "database_version_id"],
            [
                f"{SCHEMA_REFDATA}.gs_sys_years.number",
                f"{SCHEMA_REFDATA}.gs_sys_years.database_version_id",
            ],
            ondelete="RESTRICT",
            name="fk_eco_nt_norm_year_ver",
        ),
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            [f"{SCHEMA_REFDATA}.{ref_db_versions}.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "fuel_key",
            "capacity_class",
            "year_number",
            "database_version_id",
            name="uq_eco_nt_norm_fuel_class_year_ver",
        ),
        schema=SCHEMA_ECO,
    )
    op.create_index("ix_eco_nt_norm_fuel", TABLE_NORMS, ["fuel_key"], schema=SCHEMA_ECO)
    op.create_index(
        "ix_eco_nt_norm_class", TABLE_NORMS, ["capacity_class"], schema=SCHEMA_ECO
    )
    op.create_index("ix_eco_nt_norm_year", TABLE_NORMS, ["year_number"], schema=SCHEMA_ECO)
    op.create_index(
        "ix_eco_nt_norm_dbver", TABLE_NORMS, ["database_version_id"], schema=SCHEMA_ECO
    )
    _comment_on_table(
        conn,
        SCHEMA_ECO,
        TABLE_NORMS,
        "Нормативы удельных выбросов расчёта по новым ТЭС (до/более 100 МВт)",
    )


def downgrade():
    conn = op.get_bind()
    if column_utils.table_exists(conn, SCHEMA_ECO, TABLE_NORMS):
        op.drop_table(TABLE_NORMS, schema=SCHEMA_ECO)

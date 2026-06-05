# -*- coding: utf-8 -*-
"""Накопленные денежные доходы населения по ФО и году.

Revision ID: e6f7a8b9c0d5
Revises: e5f6a7b8c9d3
Create Date: 2026-06-05
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

revision = "e6f7a8b9c0d5"
down_revision = "e5f6a7b8c9d3"
branch_labels = None
depends_on = None

SCHEMA = "gs_ekp"
SCHEMA_REFDATA = "gs_sys"

TABLE = "gs_ekp_federal_district_accum_monetary_income_params"
VALUE_COL = "accum_monetary_income_mln_rub"


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
    ref_db_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REFDATA)
    if ref_db_versions is None:
        raise RuntimeError(
            f"Не найдена таблица версий БД в {SCHEMA_REFDATA} "
            "(ожидались gs_sys_database_versions или gs_database_versions)"
        )

    if not _schema_exists(conn, SCHEMA):
        op.execute(sa.text(f'CREATE SCHEMA "{SCHEMA}"'))

    if _table_exists(conn, SCHEMA, TABLE):
        return

    numeric = sa.Numeric(precision=25, scale=16)
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_federal_district", sa.Integer(), nullable=False),
        sa.Column("year_number", sa.Integer(), nullable=True),
        sa.Column(VALUE_COL, numeric, nullable=True),
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
            ["id_federal_district"],
            [f"{SCHEMA_REFDATA}.gs_sys_federal_districts.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            [f"{SCHEMA_REFDATA}.{ref_db_versions}.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )

    op.create_index(
        "ix_gs_ekp_fd_ami_fd",
        TABLE,
        ["id_federal_district"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_ekp_fd_ami_year",
        TABLE,
        ["year_number"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_ekp_fd_ami_dbver",
        TABLE,
        ["database_version_id"],
        unique=False,
        schema=SCHEMA,
    )

    op.execute(
        sa.text(
            f"""
            CREATE UNIQUE INDEX uq_gs_ekp_fd_ami_year
            ON "{SCHEMA}"."{TABLE}" (
                id_federal_district,
                year_number,
                COALESCE(database_version_id, 0)
            )
            WHERE year_number IS NOT NULL
            """
        )
    )

    table_years = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_years")
    if table_years and not column_utils.constraint_exists(
        conn, SCHEMA, "fk_ekp_fd_ami_year_ver"
    ):
        op.create_foreign_key(
            "fk_ekp_fd_ami_year_ver",
            TABLE,
            table_years,
            ["year_number", "database_version_id"],
            ["number", "database_version_id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA_REFDATA,
            ondelete="RESTRICT",
        )


def downgrade():
    conn = op.get_bind()
    if _table_exists(conn, SCHEMA, TABLE):
        op.drop_table(TABLE, schema=SCHEMA)

# -*- coding: utf-8 -*-
"""Численность населения по ФО и году (без ВЭД).

Revision ID: h9i0j1k2l3m4
Revises: g8b9c0d1e2f3
Create Date: 2026-06-04
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

revision = "h9i0j1k2l3m4"
down_revision = "g8b9c0d1e2f3"
branch_labels = None
depends_on = None

SCHEMA_EC = "gs_ec"
SCHEMA_REFDATA = "gs_sys"

TABLE = "gs_ec_federal_district_population_params"
VALUE_COL = "population_thousand_persons"


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

    if not _schema_exists(conn, SCHEMA_EC):
        op.execute(sa.text(f'CREATE SCHEMA "{SCHEMA_EC}"'))

    if _table_exists(conn, SCHEMA_EC, TABLE):
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
        schema=SCHEMA_EC,
    )

    op.create_index(
        "ix_gs_ec_fd_pop_fd",
        TABLE,
        ["id_federal_district"],
        unique=False,
        schema=SCHEMA_EC,
    )
    op.create_index(
        "ix_gs_ec_fd_pop_year",
        TABLE,
        ["year_number"],
        unique=False,
        schema=SCHEMA_EC,
    )
    op.create_index(
        "ix_gs_ec_fd_pop_dbver",
        TABLE,
        ["database_version_id"],
        unique=False,
        schema=SCHEMA_EC,
    )

    op.execute(
        sa.text(
            f"""
            CREATE UNIQUE INDEX uq_gs_ec_fd_pop_year
            ON "{SCHEMA_EC}"."{TABLE}" (
                id_federal_district,
                year_number,
                COALESCE(database_version_id, 0)
            )
            WHERE year_number IS NOT NULL
            """
        )
    )

    table_years = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_years")
    if table_years and not column_utils.constraint_exists(conn, SCHEMA_EC, "fk_ec_fd_pop_year_ver"):
        op.create_foreign_key(
            "fk_ec_fd_pop_year_ver",
            TABLE,
            table_years,
            ["year_number", "database_version_id"],
            ["number", "database_version_id"],
            source_schema=SCHEMA_EC,
            referent_schema=SCHEMA_REFDATA,
            ondelete="RESTRICT",
        )


def downgrade():
    conn = op.get_bind()
    if _table_exists(conn, SCHEMA_EC, TABLE):
        op.drop_table(TABLE, schema=SCHEMA_EC)

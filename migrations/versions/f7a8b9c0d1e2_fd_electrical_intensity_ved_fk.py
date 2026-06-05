# -*- coding: utf-8 -*-
"""Электроёмкость по ФО: привязка коэффициентов и годовых значений к ВЭД.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d4
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "f7a8b9c0d1e2"
down_revision = "e6f7a8b9c0d4"
branch_labels = None
depends_on = None

SCHEMA_EC = "gs_ec"
SCHEMA_REFDATA = "gs_sys"

TABLE_FD_YEAR = "gs_ec_federal_district_electrical_intensity_year_params"
TABLE_FD_COEF = "gs_ec_federal_district_electrical_intensity_coefficients"
VED_TABLE = "gs_sys_economic_activity_types"


def _table_exists(connection, schema: str, table: str) -> bool:
    r = connection.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :table"
        ),
        {"schema": schema, "table": table},
    )
    return r.fetchone() is not None


def _index_exists(connection, schema: str, index_name: str) -> bool:
    r = connection.execute(
        text(
            "SELECT 1 FROM pg_indexes "
            "WHERE schemaname = :schema AND indexname = :index_name"
        ),
        {"schema": schema, "index_name": index_name},
    )
    return r.fetchone() is not None


def upgrade():
    conn = op.get_bind()
    if not _table_exists(conn, SCHEMA_EC, TABLE_FD_YEAR):
        return

    for idx in ("uq_gs_ec_fd_ei_y_year", "uq_gs_ec_fd_ei_c_coef"):
        if _index_exists(conn, SCHEMA_EC, idx):
            op.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA_EC}"."{idx}"'))

    # Старые строки без ВЭД не переносятся — структура стала показателем на уровне ВЭД.
    op.execute(text(f'DELETE FROM "{SCHEMA_EC}"."{TABLE_FD_YEAR}"'))
    op.execute(text(f'DELETE FROM "{SCHEMA_EC}"."{TABLE_FD_COEF}"'))

    op.add_column(
        TABLE_FD_YEAR,
        sa.Column("id_economic_activity_type", sa.Integer(), nullable=True),
        schema=SCHEMA_EC,
    )
    op.add_column(
        TABLE_FD_COEF,
        sa.Column("id_economic_activity_type", sa.Integer(), nullable=True),
        schema=SCHEMA_EC,
    )

    op.create_foreign_key(
        "fk_ec_fd_ei_y_ved",
        TABLE_FD_YEAR,
        VED_TABLE,
        ["id_economic_activity_type"],
        ["id"],
        source_schema=SCHEMA_EC,
        referent_schema=SCHEMA_REFDATA,
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_ec_fd_ei_c_ved",
        TABLE_FD_COEF,
        VED_TABLE,
        ["id_economic_activity_type"],
        ["id"],
        source_schema=SCHEMA_EC,
        referent_schema=SCHEMA_REFDATA,
        ondelete="RESTRICT",
    )

    op.create_index(
        "ix_gs_ec_fd_ei_y_ved",
        TABLE_FD_YEAR,
        ["id_economic_activity_type"],
        unique=False,
        schema=SCHEMA_EC,
    )
    op.create_index(
        "ix_gs_ec_fd_ei_c_ved",
        TABLE_FD_COEF,
        ["id_economic_activity_type"],
        unique=False,
        schema=SCHEMA_EC,
    )

    op.alter_column(
        TABLE_FD_YEAR,
        "id_economic_activity_type",
        nullable=False,
        schema=SCHEMA_EC,
    )
    op.alter_column(
        TABLE_FD_COEF,
        "id_economic_activity_type",
        nullable=False,
        schema=SCHEMA_EC,
    )

    op.execute(
        text(
            f"""
            CREATE UNIQUE INDEX uq_gs_ec_fd_ei_y_year
            ON "{SCHEMA_EC}"."{TABLE_FD_YEAR}" (
                id_federal_district,
                id_economic_activity_type,
                row_kind,
                year_number,
                COALESCE(database_version_id, 0)
            )
            WHERE year_number IS NOT NULL
            """
        )
    )
    op.execute(
        text(
            f"""
            CREATE UNIQUE INDEX uq_gs_ec_fd_ei_c_coef
            ON "{SCHEMA_EC}"."{TABLE_FD_COEF}" (
                id_federal_district,
                id_economic_activity_type,
                COALESCE(database_version_id, 0)
            )
            """
        )
    )


def downgrade():
    conn = op.get_bind()
    if not _table_exists(conn, SCHEMA_EC, TABLE_FD_YEAR):
        return

    for idx in ("uq_gs_ec_fd_ei_y_year", "uq_gs_ec_fd_ei_c_coef"):
        if _index_exists(conn, SCHEMA_EC, idx):
            op.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA_EC}"."{idx}"'))

    op.drop_constraint("fk_ec_fd_ei_y_ved", TABLE_FD_YEAR, schema=SCHEMA_EC, type_="foreignkey")
    op.drop_constraint("fk_ec_fd_ei_c_ved", TABLE_FD_COEF, schema=SCHEMA_EC, type_="foreignkey")
    op.drop_index("ix_gs_ec_fd_ei_y_ved", table_name=TABLE_FD_YEAR, schema=SCHEMA_EC)
    op.drop_index("ix_gs_ec_fd_ei_c_ved", table_name=TABLE_FD_COEF, schema=SCHEMA_EC)
    op.drop_column(TABLE_FD_YEAR, "id_economic_activity_type", schema=SCHEMA_EC)
    op.drop_column(TABLE_FD_COEF, "id_economic_activity_type", schema=SCHEMA_EC)

    op.execute(
        text(
            f"""
            CREATE UNIQUE INDEX uq_gs_ec_fd_ei_y_year
            ON "{SCHEMA_EC}"."{TABLE_FD_YEAR}" (
                id_federal_district,
                row_kind,
                year_number,
                COALESCE(database_version_id, 0)
            )
            WHERE year_number IS NOT NULL
            """
        )
    )
    op.execute(
        text(
            f"""
            CREATE UNIQUE INDEX uq_gs_ec_fd_ei_c_coef
            ON "{SCHEMA_EC}"."{TABLE_FD_COEF}" (
                id_federal_district,
                COALESCE(database_version_id, 0)
            )
            """
        )
    )

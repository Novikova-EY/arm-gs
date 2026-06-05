# -*- coding: utf-8 -*-
"""Таблицы блока «Население» на странице электроёмкости (ФО).

Revision ID: p9q0r1s2t3u4
Revises: e6f7a8b9c0d5
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

revision = "p9q0r1s2t3u4"
down_revision = "e6f7a8b9c0d5"
branch_labels = None
depends_on = None

SCHEMA_EC = "gs_ec"
SCHEMA_REFDATA = "gs_sys"

TABLE_YEAR = "gs_ec_federal_district_population_consumption_year_params"
TABLE_COEF = "gs_ec_federal_district_population_consumption_coefficients"


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


def _audit_columns():
    return [
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
    ]


def upgrade():
    conn = op.get_bind()
    ref_db_versions = column_utils.database_versions_physical_table_name(
        conn, SCHEMA_REFDATA
    )
    if ref_db_versions is None:
        raise RuntimeError(
            f"Не найдена таблица версий БД в {SCHEMA_REFDATA} "
            "(ожидались gs_sys_database_versions или gs_database_versions)"
        )
    if not _schema_exists(conn, SCHEMA_EC):
        return

    numeric = sa.Numeric(precision=25, scale=16)
    value_numeric = sa.Numeric(precision=25, scale=10)

    if not _table_exists(conn, SCHEMA_EC, TABLE_COEF):
        op.create_table(
            TABLE_COEF,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("id_federal_district", sa.Integer(), nullable=False),
            sa.Column("coefficient_a", numeric, nullable=True),
            sa.Column("coefficient_x", numeric, nullable=True),
            *_audit_columns(),
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
            "ix_ec_fd_pop_cons_coef_fd",
            TABLE_COEF,
            ["id_federal_district"],
            unique=False,
            schema=SCHEMA_EC,
        )

    if not _table_exists(conn, SCHEMA_EC, TABLE_YEAR):
        op.create_table(
            TABLE_YEAR,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("id_federal_district", sa.Integer(), nullable=False),
            sa.Column("row_kind", sa.String(length=32), nullable=False),
            sa.Column("year_number", sa.Integer(), nullable=True),
            sa.Column("parameter_value", value_numeric, nullable=True),
            *_audit_columns(),
            sa.ForeignKeyConstraint(
                ["id_federal_district"],
                [f"{SCHEMA_REFDATA}.gs_sys_federal_districts.id"],
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["year_number", "database_version_id"],
                [
                    f"{SCHEMA_REFDATA}.gs_sys_years.number",
                    f"{SCHEMA_REFDATA}.gs_sys_years.database_version_id",
                ],
                ondelete="RESTRICT",
                name="fk_ec_fd_pop_cons_y_year_ver",
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
            "ix_ec_fd_pop_cons_year_fd",
            TABLE_YEAR,
            ["id_federal_district"],
            unique=False,
            schema=SCHEMA_EC,
        )
        op.create_index(
            "ix_ec_fd_pop_cons_year_kind",
            TABLE_YEAR,
            ["row_kind"],
            unique=False,
            schema=SCHEMA_EC,
        )
        op.create_index(
            "ix_ec_fd_pop_cons_year_num",
            TABLE_YEAR,
            ["year_number"],
            unique=False,
            schema=SCHEMA_EC,
        )


def downgrade():
    conn = op.get_bind()
    if not _schema_exists(conn, SCHEMA_EC):
        return
    if _table_exists(conn, SCHEMA_EC, TABLE_YEAR):
        op.drop_table(TABLE_YEAR, schema=SCHEMA_EC)
    if _table_exists(conn, SCHEMA_EC, TABLE_COEF):
        op.drop_table(TABLE_COEF, schema=SCHEMA_EC)

# -*- coding: utf-8 -*-
"""Таблицы электроёмкости по ФО и РФ (долгосрочный прогноз).

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-06-03
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

revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None

SCHEMA_EC = "gs_ec"
SCHEMA_REFDATA = "gs_sys"

TABLE_FD_YEAR = "gs_ec_federal_district_electrical_intensity_year_params"
TABLE_RF_YEAR = "gs_ec_russia_federation_electrical_intensity_year_params"
TABLE_FD_COEF = "gs_ec_federal_district_electrical_intensity_coefficients"
TABLE_RF_COEF = "gs_ec_russia_federation_electrical_intensity_coefficients"
TABLE_FORMULA = "gs_ec_long_term_electrical_intensity_formula_texts"


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


def _create_year_table(
    conn,
    *,
    table: str,
    fk_col: str | None,
    ref_tbl: str | None,
    ref_db_versions: str,
    uq_prefix: str,
):
    if _table_exists(conn, SCHEMA_EC, table):
        return

    numeric = sa.Numeric(precision=25, scale=16)
    cols = [sa.Column("id", sa.Integer(), autoincrement=True, nullable=False)]
    fks: list = []

    if fk_col and ref_tbl:
        cols.append(sa.Column(fk_col, sa.Integer(), nullable=False))
        fks.append(
            sa.ForeignKeyConstraint(
                [fk_col],
                [f"{SCHEMA_REFDATA}.{ref_tbl}.id"],
                ondelete="RESTRICT",
            ),
        )

    cols.extend(
        [
            sa.Column("row_kind", sa.String(length=32), nullable=False),
            sa.Column("year_number", sa.Integer(), nullable=True),
            sa.Column("parameter_value", numeric, nullable=True),
            *_audit_columns(),
        ]
    )
    fks.append(
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            [f"{SCHEMA_REFDATA}.{ref_db_versions}.id"],
            ondelete="SET NULL",
        ),
    )

    op.create_table(table, *cols, *fks, sa.PrimaryKeyConstraint("id"), schema=SCHEMA_EC)

    if fk_col:
        op.create_index(
            f"ix_gs_ec_{uq_prefix}_fd",
            table,
            [fk_col],
            unique=False,
            schema=SCHEMA_EC,
        )
    op.create_index(
        f"ix_gs_ec_{uq_prefix}_kind",
        table,
        ["row_kind"],
        unique=False,
        schema=SCHEMA_EC,
    )
    op.create_index(
        f"ix_gs_ec_{uq_prefix}_year",
        table,
        ["year_number"],
        unique=False,
        schema=SCHEMA_EC,
    )
    op.create_index(
        f"ix_gs_ec_{uq_prefix}_dbver",
        table,
        ["database_version_id"],
        unique=False,
        schema=SCHEMA_EC,
    )

    if fk_col:
        op.execute(
            sa.text(
                f"""
                CREATE UNIQUE INDEX uq_gs_ec_{uq_prefix}_year
                ON "{SCHEMA_EC}"."{table}" (
                    {fk_col},
                    row_kind,
                    year_number,
                    COALESCE(database_version_id, 0)
                )
                WHERE year_number IS NOT NULL
                """
            )
        )
    else:
        op.execute(
            sa.text(
                f"""
                CREATE UNIQUE INDEX uq_gs_ec_{uq_prefix}_year
                ON "{SCHEMA_EC}"."{table}" (
                    row_kind,
                    year_number,
                    COALESCE(database_version_id, 0)
                )
                WHERE year_number IS NOT NULL
                """
            )
        )


def _create_coef_table(
    conn,
    *,
    table: str,
    fk_col: str | None,
    ref_tbl: str | None,
    ref_db_versions: str,
    uq_prefix: str,
):
    if _table_exists(conn, SCHEMA_EC, table):
        return

    numeric = sa.Numeric(precision=25, scale=16)
    cols = [sa.Column("id", sa.Integer(), autoincrement=True, nullable=False)]
    fks: list = []

    if fk_col and ref_tbl:
        cols.append(sa.Column(fk_col, sa.Integer(), nullable=False))
        fks.append(
            sa.ForeignKeyConstraint(
                [fk_col],
                [f"{SCHEMA_REFDATA}.{ref_tbl}.id"],
                ondelete="RESTRICT",
            ),
        )

    cols.extend(
        [
            sa.Column("coefficient_a", numeric, nullable=True),
            sa.Column("coefficient_x", numeric, nullable=True),
            *_audit_columns(),
        ]
    )
    fks.append(
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            [f"{SCHEMA_REFDATA}.{ref_db_versions}.id"],
            ondelete="SET NULL",
        ),
    )

    op.create_table(table, *cols, *fks, sa.PrimaryKeyConstraint("id"), schema=SCHEMA_EC)

    if fk_col:
        op.create_index(
            f"ix_gs_ec_{uq_prefix}_fd",
            table,
            [fk_col],
            unique=False,
            schema=SCHEMA_EC,
        )
        op.execute(
            sa.text(
                f"""
                CREATE UNIQUE INDEX uq_gs_ec_{uq_prefix}_coef
                ON "{SCHEMA_EC}"."{table}" (
                    {fk_col},
                    COALESCE(database_version_id, 0)
                )
                """
            )
        )
    else:
        op.execute(
            sa.text(
                f"""
                CREATE UNIQUE INDEX uq_gs_ec_{uq_prefix}_coef
                ON "{SCHEMA_EC}"."{table}" (
                    COALESCE(database_version_id, 0)
                )
                """
            )
        )


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

    _create_year_table(
        conn,
        table=TABLE_FD_YEAR,
        fk_col="id_federal_district",
        ref_tbl="gs_sys_federal_districts",
        ref_db_versions=ref_db_versions,
        uq_prefix="fd_ei_y",
    )
    _create_year_table(
        conn,
        table=TABLE_RF_YEAR,
        fk_col=None,
        ref_tbl=None,
        ref_db_versions=ref_db_versions,
        uq_prefix="rf_ei_y",
    )
    _create_coef_table(
        conn,
        table=TABLE_FD_COEF,
        fk_col="id_federal_district",
        ref_tbl="gs_sys_federal_districts",
        ref_db_versions=ref_db_versions,
        uq_prefix="fd_ei_c",
    )
    _create_coef_table(
        conn,
        table=TABLE_RF_COEF,
        fk_col=None,
        ref_tbl=None,
        ref_db_versions=ref_db_versions,
        uq_prefix="rf_ei_c",
    )

    if not _table_exists(conn, SCHEMA_EC, TABLE_FORMULA):
        op.create_table(
            TABLE_FORMULA,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("formula_key", sa.String(length=128), nullable=False),
            sa.Column("formula_text", sa.Text(), nullable=False),
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
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("formula_key", name="uq_gs_ec_lt_ei_formula_texts_key"),
            schema=SCHEMA_EC,
        )
        op.create_index(
            "ix_gs_ec_lt_ei_formula_key",
            TABLE_FORMULA,
            ["formula_key"],
            unique=False,
            schema=SCHEMA_EC,
        )


def downgrade():
    conn = op.get_bind()
    for table in (TABLE_FORMULA, TABLE_RF_COEF, TABLE_FD_COEF, TABLE_RF_YEAR, TABLE_FD_YEAR):
        if _table_exists(conn, SCHEMA_EC, table):
            op.drop_table(table, schema=SCHEMA_EC)

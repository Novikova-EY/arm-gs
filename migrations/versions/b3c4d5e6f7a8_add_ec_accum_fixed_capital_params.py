# -*- coding: utf-8 -*-
"""Таблицы накопленных инвестиций в основной капитал по ВЭД (ФО и РФ).

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
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

revision = "b3c4d5e6f7a8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None

SCHEMA_EC = "gs_ec"
SCHEMA_REFDATA = "gs_sys"

TABLE_FD = "gs_ec_federal_district_economic_activity_accum_fixed_capital_params"
TABLE_RF = "gs_ec_russia_federation_economic_activity_accum_fixed_capital_params"
TABLE_FORMULA = "gs_ec_long_term_accum_fixed_capital_formula_texts"
VALUE_COL = "accumulated_fixed_capital_investment_mln_rub"


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


def _create_table(
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
            sa.Column("id_economic_activity_type", sa.Integer(), nullable=False),
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
        ]
    )
    fks.append(
        sa.ForeignKeyConstraint(
            ["id_economic_activity_type"],
            [f"{SCHEMA_REFDATA}.gs_sys_economic_activity_types.id"],
            ondelete="RESTRICT",
        ),
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
        f"ix_gs_ec_{uq_prefix}_ved",
        table,
        ["id_economic_activity_type"],
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
                    id_economic_activity_type,
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
                    id_economic_activity_type,
                    year_number,
                    COALESCE(database_version_id, 0)
                )
                WHERE year_number IS NOT NULL
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

    _create_table(
        conn,
        table=TABLE_FD,
        fk_col="id_federal_district",
        ref_tbl="gs_sys_federal_districts",
        ref_db_versions=ref_db_versions,
        uq_prefix="fd_afci",
    )
    _create_table(
        conn,
        table=TABLE_RF,
        fk_col=None,
        ref_tbl=None,
        ref_db_versions=ref_db_versions,
        uq_prefix="rf_afci",
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
            sa.UniqueConstraint("formula_key", name="uq_gs_ec_lt_afci_formula_texts_key"),
            schema=SCHEMA_EC,
        )
        op.create_index(
            "ix_gs_ec_lt_afci_formula_key",
            TABLE_FORMULA,
            ["formula_key"],
            unique=False,
            schema=SCHEMA_EC,
        )


def downgrade():
    conn = op.get_bind()
    for table in (TABLE_FORMULA, TABLE_RF, TABLE_FD):
        if _table_exists(conn, SCHEMA_EC, table):
            op.drop_table(table, schema=SCHEMA_EC)

# -*- coding: utf-8 -*-
"""Таблицы расчёта по действующим ТЭС (характеристики топлива и коэффициенты).

Revision ID: s5t6u7v8w9x0
Revises: r4s5t6u7v8w9
Create Date: 2026-08-31
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

revision = "s5t6u7v8w9x0"
down_revision = "r4s5t6u7v8w9"
branch_labels = None
depends_on = None

SCHEMA_ECO = "gs_eco"
SCHEMA_REFDATA = "gs_sys"
TABLE_CHARS = "gs_eco_operating_tes_fuel_chars"
TABLE_COEFF = "gs_eco_operating_tes_coefficients"


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
    if not column_utils.table_exists(conn, SCHEMA_ECO, TABLE_CHARS):
        op.create_table(
            TABLE_CHARS,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("fuel_key", sa.String(length=80), nullable=False),
            sa.Column("year_number", sa.Integer(), nullable=False),
            sa.Column("ash", numeric, nullable=True),
            sa.Column("ash_share", numeric, nullable=True),
            sa.Column("q_mech", numeric, nullable=True),
            sa.Column("sulfur", numeric, nullable=True),
            sa.Column("sulfur_share", numeric, nullable=True),
            sa.Column("qh_kj", numeric, nullable=True),
            sa.Column("qh_kcal", numeric, nullable=True),
            sa.Column("bj", numeric, nullable=True),
            sa.Column("k_co2", numeric, nullable=True),
            sa.Column("r_chem", numeric, nullable=True),
            sa.Column("q_chem", numeric, nullable=True),
            sa.Column("tut_per_t", numeric, nullable=True),
            sa.Column("tj_per_kt", numeric, nullable=True),
            sa.Column("t_co2_per_tj", numeric, nullable=True),
            sa.Column("k_natural", numeric, nullable=True),
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
                name="fk_eco_ot_fuel_char_year_ver",
            ),
            sa.ForeignKeyConstraint(
                ["database_version_id"],
                [f"{SCHEMA_REFDATA}.{ref_db_versions}.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "fuel_key",
                "year_number",
                "database_version_id",
                name="uq_eco_ot_fuel_char_key_year_ver",
            ),
            schema=SCHEMA_ECO,
        )
        op.create_index("ix_eco_ot_fuel_char_key", TABLE_CHARS, ["fuel_key"], schema=SCHEMA_ECO)
        op.create_index("ix_eco_ot_fuel_char_year", TABLE_CHARS, ["year_number"], schema=SCHEMA_ECO)
        op.create_index(
            "ix_eco_ot_fuel_char_dbver", TABLE_CHARS, ["database_version_id"], schema=SCHEMA_ECO
        )
        _comment_on_table(
            conn,
            SCHEMA_ECO,
            TABLE_CHARS,
            "Характеристики топлива расчёта по действующим ТЭС (Хар.топл.)",
        )

    if not column_utils.table_exists(conn, SCHEMA_ECO, TABLE_COEFF):
        op.create_table(
            TABLE_COEFF,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("territory_slug", sa.String(length=80), nullable=False),
            sa.Column("year_number", sa.Integer(), nullable=False),
            sa.Column("kind", sa.String(length=40), nullable=False),
            sa.Column("value", numeric, nullable=True),
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
                name="fk_eco_ot_coeff_year_ver",
            ),
            sa.ForeignKeyConstraint(
                ["database_version_id"],
                [f"{SCHEMA_REFDATA}.{ref_db_versions}.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "territory_slug",
                "year_number",
                "kind",
                "database_version_id",
                name="uq_eco_ot_coeff_terr_year_kind_ver",
            ),
            schema=SCHEMA_ECO,
        )
        op.create_index(
            "ix_eco_ot_coeff_terr", TABLE_COEFF, ["territory_slug"], schema=SCHEMA_ECO
        )
        op.create_index("ix_eco_ot_coeff_year", TABLE_COEFF, ["year_number"], schema=SCHEMA_ECO)
        op.create_index("ix_eco_ot_coeff_kind", TABLE_COEFF, ["kind"], schema=SCHEMA_ECO)
        op.create_index(
            "ix_eco_ot_coeff_dbver", TABLE_COEFF, ["database_version_id"], schema=SCHEMA_ECO
        )
        _comment_on_table(
            conn,
            SCHEMA_ECO,
            TABLE_COEFF,
            "КПД очистки и коэффициенты подавления (лист Коэфф.)",
        )


def downgrade():
    conn = op.get_bind()
    if column_utils.table_exists(conn, SCHEMA_ECO, TABLE_COEFF):
        op.drop_table(TABLE_COEFF, schema=SCHEMA_ECO)
    if column_utils.table_exists(conn, SCHEMA_ECO, TABLE_CHARS):
        op.drop_table(TABLE_CHARS, schema=SCHEMA_ECO)

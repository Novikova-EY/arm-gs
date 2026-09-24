# -*- coding: utf-8 -*-
"""Сохранённые значения ввода расчёта по действующим ТЭС.

Revision ID: t6u7v8w9x0y1
Revises: s5t6u7v8w9x0
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

revision = "t6u7v8w9x0y1"
down_revision = "s5t6u7v8w9x0"
branch_labels = None
depends_on = None

SCHEMA_ECO = "gs_eco"
SCHEMA_REFDATA = "gs_sys"
TABLE_INPUTS = "gs_eco_operating_tes_inputs"


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
    if not column_utils.table_exists(conn, SCHEMA_ECO, TABLE_INPUTS):
        op.create_table(
            TABLE_INPUTS,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("territory_slug", sa.String(length=80), nullable=False),
            sa.Column("year_number", sa.Integer(), nullable=False),
            sa.Column("row_key", sa.String(length=80), nullable=False),
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
                name="fk_eco_ot_input_year_ver",
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
                "row_key",
                "database_version_id",
                name="uq_eco_ot_input_terr_year_key_ver",
            ),
            schema=SCHEMA_ECO,
        )
        op.create_index(
            "ix_eco_ot_input_terr", TABLE_INPUTS, ["territory_slug"], schema=SCHEMA_ECO
        )
        op.create_index("ix_eco_ot_input_year", TABLE_INPUTS, ["year_number"], schema=SCHEMA_ECO)
        op.create_index("ix_eco_ot_input_key", TABLE_INPUTS, ["row_key"], schema=SCHEMA_ECO)
        op.create_index(
            "ix_eco_ot_input_dbver", TABLE_INPUTS, ["database_version_id"], schema=SCHEMA_ECO
        )
        _comment_on_table(
            conn,
            SCHEMA_ECO,
            TABLE_INPUTS,
            "Переопределения ввода расчёта по действующим ТЭС (топливо, выработка, тепло)",
        )


def downgrade():
    conn = op.get_bind()
    if column_utils.table_exists(conn, SCHEMA_ECO, TABLE_INPUTS):
        op.drop_table(TABLE_INPUTS, schema=SCHEMA_ECO)

# -*- coding: utf-8 -*-
"""Параметры распределения: year_number -> FK на gs_years (Year).

Revision ID: f2e3d4c5b6a8
Revises: f1e2d3c4b5a7
Create Date: 2026-04-03
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


revision = "f2e3d4c5b6a8"
down_revision = "f1e2d3c4b5a7"
branch_labels = None
depends_on = None

SCHEMA_FUEL = "gs_fue"
SCHEMA_REFDATA = "gs_sys"
TABLE = "gs_fue_distribution_parameters"
COL = "id_year"


def _column_exists(connection, column: str) -> bool:
    r = connection.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :col"
        ),
        {"schema": SCHEMA_FUEL, "table": TABLE, "col": column},
    )
    return r.fetchone() is not None


def upgrade():
    conn = op.get_bind()
    table_years = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_years")
    if table_years is None:
        return
    if not _column_exists(conn, COL):
        op.add_column(
            TABLE,
            sa.Column(COL, sa.Integer(), nullable=True),
            schema=SCHEMA_FUEL,
        )
        op.create_foreign_key(
            f"fk_{TABLE}_{COL}",
            TABLE,
            table_years,
            [COL],
            ["id"],
            source_schema=SCHEMA_FUEL,
            referent_schema=SCHEMA_REFDATA,
            ondelete="RESTRICT",
        )
        op.create_index(
            f"ix_{TABLE}_{COL}",
            TABLE,
            [COL],
            unique=False,
            schema=SCHEMA_FUEL,
        )

    if _column_exists(conn, "year_number"):
        conn.execute(
            text(
                f"""
                UPDATE {SCHEMA_FUEL}.{TABLE} AS dp
                SET {COL} = y.id
                FROM {SCHEMA_REFDATA}.{table_years} AS y
                WHERE dp.year_number = y.number
                  AND (
                    (dp.database_version_id IS NULL AND y.database_version_id IS NULL)
                    OR (dp.database_version_id = y.database_version_id)
                  )
                """
            )
        )
        n_null = conn.execute(
            text(f"SELECT COUNT(*) FROM {SCHEMA_FUEL}.{TABLE} WHERE {COL} IS NULL")
        ).scalar()
        if n_null and int(n_null) > 0:
            raise RuntimeError(
                f"Миграция: для {n_null} строк gs_fue_distribution_parameters не найден "
                f"Year в {table_years} (number + database_version_id). Заполните вручную или добавьте годы в справочник."
            )
        op.alter_column(
            TABLE,
            COL,
            existing_type=sa.Integer(),
            nullable=False,
            schema=SCHEMA_FUEL,
        )
        op.drop_index(
            f"ix_{TABLE}_year_number",
            table_name=TABLE,
            schema=SCHEMA_FUEL,
        )
        op.drop_column(TABLE, "year_number", schema=SCHEMA_FUEL)


def downgrade():
    op.add_column(
        TABLE,
        sa.Column("year_number", sa.Integer(), nullable=True),
        schema=SCHEMA_FUEL,
    )
    conn = op.get_bind()
    table_years = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_years")
    if table_years is None:
        return
    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA_FUEL}.{TABLE} AS dp
            SET year_number = y.number
            FROM {SCHEMA_REFDATA}.{table_years} AS y
            WHERE dp.{COL} = y.id
            """
        )
    )
    op.alter_column(
        TABLE,
        "year_number",
        existing_type=sa.Integer(),
        nullable=False,
        schema=SCHEMA_FUEL,
    )
    op.drop_constraint(
        f"fk_{TABLE}_{COL}",
        TABLE,
        schema=SCHEMA_FUEL,
        type_="foreignkey",
    )
    op.drop_index(f"ix_{TABLE}_{COL}", table_name=TABLE, schema=SCHEMA_FUEL)
    op.drop_column(TABLE, COL, schema=SCHEMA_FUEL)
    op.create_index(
        f"ix_{TABLE}_year_number",
        TABLE,
        ["year_number"],
        unique=False,
        schema=SCHEMA_FUEL,
    )

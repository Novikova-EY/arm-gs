# -*- coding: utf-8 -*-
"""Параметры распределения: byear -> FK на gs_years (базовый Year).

Revision ID: f3e4d5c6b7a9
Revises: f2e3d4c5b6a8
Create Date: 2026-04-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "f3e4d5c6b7a9"
down_revision = "f2e3d4c5b6a8"
branch_labels = None
depends_on = None

SCHEMA_FUEL = "gs_fue"
SCHEMA_REFDATA = "gs_sys"
TABLE = "gs_fue_distribution_parameters"
COL = "id_base_year"


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
    if not _column_exists(conn, COL):
        op.add_column(
            TABLE,
            sa.Column(COL, sa.Integer(), nullable=True),
            schema=SCHEMA_FUEL,
        )
        op.create_foreign_key(
            f"fk_{TABLE}_{COL}",
            TABLE,
            "gs_years",
            [COL],
            ["id"],
            source_schema=SCHEMA_FUEL,
            referent_schema=SCHEMA_REFDATA,
            ondelete="SET NULL",
        )
        op.create_index(
            f"ix_{TABLE}_{COL}",
            TABLE,
            [COL],
            unique=False,
            schema=SCHEMA_FUEL,
        )

    if _column_exists(conn, "byear"):
        conn.execute(
            text(
                f"""
                UPDATE {SCHEMA_FUEL}.{TABLE} AS dp
                SET {COL} = y.id
                FROM {SCHEMA_REFDATA}.gs_years AS y
                WHERE dp.byear IS NOT NULL
                  AND dp.byear = y.number
                  AND (
                    (dp.database_version_id IS NULL AND y.database_version_id IS NULL)
                    OR (dp.database_version_id = y.database_version_id)
                  )
                """
            )
        )
        op.drop_index(
            f"ix_{TABLE}_byear",
            table_name=TABLE,
            schema=SCHEMA_FUEL,
        )
        op.drop_column(TABLE, "byear", schema=SCHEMA_FUEL)


def downgrade():
    op.add_column(
        TABLE,
        sa.Column("byear", sa.Integer(), nullable=True),
        schema=SCHEMA_FUEL,
    )
    conn = op.get_bind()
    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA_FUEL}.{TABLE} AS dp
            SET byear = y.number
            FROM {SCHEMA_REFDATA}.gs_years AS y
            WHERE dp.{COL} = y.id
            """
        )
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
        f"ix_{TABLE}_byear",
        TABLE,
        ["byear"],
        unique=False,
        schema=SCHEMA_FUEL,
    )

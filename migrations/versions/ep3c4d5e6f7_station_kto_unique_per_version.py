# -*- coding: utf-8 -*-
"""gs_gen_stations: уникальность kto в пределах версии БД.

Revision ID: ep3c4d5e6f7
Revises: ep2c3d4e5f6
Create Date: 2026-06-30
"""
import os
import sys

from alembic import op
from sqlalchemy import text

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "ep3c4d5e6f7"
down_revision = "ep2c3d4e5f6"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
NEW_UQ = "uq_gs_gen_stations_ver_kto"


def _stations_table(conn) -> str | None:
    return column_utils.gs_gen_stations_table_name(conn, SCHEMA_GEN)


def _find_single_column_unique_constraint(conn, table: str, column: str) -> str | None:
    row = conn.execute(
        text(
            """
            SELECT c.conname
            FROM pg_constraint c
            JOIN pg_class cl ON cl.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = cl.relnamespace
            WHERE c.contype = 'u'
              AND n.nspname = :schema
              AND cl.relname = :table
              AND array_length(c.conkey, 1) = 1
              AND EXISTS (
                  SELECT 1
                  FROM unnest(c.conkey) AS colnum(attnum)
                  JOIN pg_attribute a
                    ON a.attrelid = cl.oid
                   AND a.attnum = colnum.attnum
                  WHERE a.attname = :column
              )
            LIMIT 1
            """
        ),
        {"schema": SCHEMA_GEN, "table": table, "column": column},
    ).fetchone()
    return row[0] if row else None


def upgrade():
    conn = op.get_bind()
    table = _stations_table(conn)
    if table is None:
        return

    old_uq = _find_single_column_unique_constraint(conn, table, "kto")
    if old_uq and not column_utils.constraint_exists(conn, SCHEMA_GEN, NEW_UQ):
        op.drop_constraint(old_uq, table, schema=SCHEMA_GEN, type_="unique")

    if not column_utils.constraint_exists(conn, SCHEMA_GEN, NEW_UQ):
        op.create_unique_constraint(
            NEW_UQ,
            table,
            ["database_version_id", "kto"],
            schema=SCHEMA_GEN,
        )


def downgrade():
    conn = op.get_bind()
    table = _stations_table(conn)
    if table is None:
        return

    if column_utils.constraint_exists(conn, SCHEMA_GEN, NEW_UQ):
        op.drop_constraint(NEW_UQ, table, schema=SCHEMA_GEN, type_="unique")

    old_uq = _find_single_column_unique_constraint(conn, table, "kto")
    if old_uq is None:
        op.create_unique_constraint(None, table, ["kto"], schema=SCHEMA_GEN)

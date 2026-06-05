# -*- coding: utf-8 -*-
"""Экономика: короткие имена таблиц параметров (без economic_activity_).

Revision ID: c3d4e5f6a7b0
Revises: b2c3d4e5f6a8
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

revision = "c3d4e5f6a7b0"
down_revision = "b2c3d4e5f6a8"
branch_labels = None
depends_on = None

SCHEMA = "gs_ekp"

# (new_table, old_table_candidates)
_TABLE_RENAMES = [
    (
        "gs_ekp_federal_district_product_output_params",
        (
            "gs_ekp_federal_district_economic_activity_product_output_params",
        ),
    ),
    (
        "gs_ekp_federal_district_accum_fixed_capital_params",
        (
            "gs_ekp_federal_district_economic_activity_accum_fixed_capital_params",
        ),
    ),
    (
        "gs_ekp_russia_federation_product_output_params",
        (
            "gs_ekp_russia_federation_economic_activity_product_output_params",
        ),
    ),
    (
        "gs_ekp_russia_federation_accum_fixed_capital_params",
        (
            "gs_ekp_russia_federation_economic_activity_accum_fixed_capital_params",
        ),
    ),
    (
        "gs_ekp_russia_federation_consumption_params",
        (
            "gs_ekp_russia_federation_economic_activity_consumption_params",
        ),
    ),
]


def _rename_sequences(conn, old_table: str, new_table: str) -> None:
    for old_seq, new_seq in (
        (f"{old_table}_id_seq", f"{new_table}_id_seq"),
        (f"{old_table}_id_seq1", f"{new_table}_id_seq1"),
    ):
        row = conn.execute(
            text(
                """
                SELECT 1
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = :schema AND c.relkind = 'S' AND c.relname = :seq
                """
            ),
            {"schema": SCHEMA, "seq": old_seq},
        ).fetchone()
        if row and old_seq != new_seq:
            op.execute(
                sa.text(f'ALTER SEQUENCE "{SCHEMA}"."{old_seq}" RENAME TO "{new_seq}"')
            )


def _rename_table(conn, new_table: str, old_candidates: tuple[str, ...]) -> None:
    if column_utils.table_exists(conn, SCHEMA, new_table):
        return
    for old_table in old_candidates:
        if not column_utils.table_exists(conn, SCHEMA, old_table):
            continue
        op.rename_table(old_table, new_table, schema=SCHEMA)
        _rename_sequences(conn, old_table, new_table)
        return


def upgrade():
    conn = op.get_bind()
    for new_table, old_candidates in _TABLE_RENAMES:
        _rename_table(conn, new_table, old_candidates)


def downgrade():
    conn = op.get_bind()
    for new_table, old_candidates in reversed(_TABLE_RENAMES):
        if not column_utils.table_exists(conn, SCHEMA, new_table):
            continue
        old_table = old_candidates[0]
        if column_utils.table_exists(conn, SCHEMA, old_table):
            continue
        op.rename_table(new_table, old_table, schema=SCHEMA)
        _rename_sequences(conn, new_table, old_table)

# -*- coding: utf-8 -*-
"""Таблицы раздела «Экономика»: префикс gs_ekp_ в именах (схема gs_ekp).

Revision ID: z9a0b1c2d3e4
Revises: j1k2l3m4n5o6
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

revision = "z9a0b1c2d3e4"
down_revision = "j1k2l3m4n5o6"
branch_labels = None
depends_on = None

SCHEMA = "gs_ekp"

_TABLE_RENAMES = [
    (
        "gs_ec_federal_district_economic_activity_accum_fixed_capital_params",
        "gs_ekp_federal_district_economic_activity_accum_fixed_capital_params",
    ),
    (
        "gs_ec_federal_district_economic_activity_consumption_params",
        "gs_ekp_federal_district_economic_activity_consumption_params",
    ),
    (
        "gs_ec_federal_district_economic_activity_product_output_params",
        "gs_ekp_federal_district_economic_activity_product_output_params",
    ),
    ("gs_ec_federal_district_population_params", "gs_ekp_federal_district_population_params"),
    (
        "gs_ec_long_term_accum_fixed_capital_formula_texts",
        "gs_ekp_long_term_accum_fixed_capital_formula_texts",
    ),
    (
        "gs_ec_long_term_product_output_formula_texts",
        "gs_ekp_long_term_product_output_formula_texts",
    ),
    (
        "gs_ec_long_term_ved_consumption_formula_texts",
        "gs_ekp_long_term_ved_consumption_formula_texts",
    ),
    (
        "gs_ec_russia_federation_economic_activity_accum_fixed_capital_params",
        "gs_ekp_russia_federation_economic_activity_accum_fixed_capital_params",
    ),
    (
        "gs_ec_russia_federation_economic_activity_consumption_params",
        "gs_ekp_russia_federation_economic_activity_consumption_params",
    ),
    (
        "gs_ec_russia_federation_economic_activity_product_output_params",
        "gs_ekp_russia_federation_economic_activity_product_output_params",
    ),
]


def _derive_db_object_name(old: str) -> str | None:
    if old.startswith("gs_ec_"):
        return "gs_ekp_" + old[6:]
    if old.startswith("fk_ec_"):
        return "fk_ekp_" + old[6:]
    if old.startswith("uq_gs_ec_"):
        return "uq_gs_ekp_" + old[9:]
    if old.startswith("ix_gs_ec_"):
        return "ix_gs_ekp_" + old[9:]
    if old.startswith("ix_ec_"):
        return "ix_ekp_" + old[6:]
    return None


def _list_table_indexes(conn, schema: str, table: str) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = :schema AND tablename = :table
            """
        ),
        {"schema": schema, "table": table},
    ).fetchall()
    return [r[0] for r in rows]


def _list_table_constraints(conn, schema: str, table: str) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT c.conname
            FROM pg_constraint c
            JOIN pg_class rel ON rel.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = rel.relnamespace
            WHERE n.nspname = :schema
              AND rel.relname = :table
              AND c.contype IN ('f', 'u', 'p')
            """
        ),
        {"schema": schema, "table": table},
    ).fetchall()
    return [r[0] for r in rows]


def _rename_index(conn, schema: str, old: str, new: str) -> None:
    if old == new or not column_utils.index_exists(conn, schema, old):
        return
    op.execute(sa.text(f'ALTER INDEX "{schema}"."{old}" RENAME TO "{new}"'))


def _rename_constraint(conn, schema: str, table: str, old: str, new: str) -> None:
    if old == new or not column_utils.constraint_exists(conn, schema, old):
        return
    op.execute(
        sa.text(
            f'ALTER TABLE "{schema}"."{table}" RENAME CONSTRAINT "{old}" TO "{new}"'
        )
    )


def _rename_table_db_objects(conn, schema: str, table: str) -> None:
    constraint_names = _list_table_constraints(conn, schema, table)
    for constraint_name in constraint_names:
        new_name = _derive_db_object_name(constraint_name)
        if new_name:
            _rename_constraint(conn, schema, table, constraint_name, new_name)

    for index_name in _list_table_indexes(conn, schema, table):
        if index_name in constraint_names:
            continue
        new_name = _derive_db_object_name(index_name)
        if new_name:
            _rename_index(conn, schema, index_name, new_name)


def _rename_sequences(conn, schema: str, old_table: str, new_table: str) -> None:
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
            {"schema": schema, "seq": old_seq},
        ).fetchone()
        if row and old_seq != new_seq:
            op.execute(sa.text(f'ALTER SEQUENCE "{schema}"."{old_seq}" RENAME TO "{new_seq}"'))


def _apply_table_renames(conn, renames: list[tuple[str, str]]) -> None:
    for old, new in renames:
        if not column_utils.table_exists(conn, SCHEMA, old):
            continue
        if column_utils.table_exists(conn, SCHEMA, new):
            continue
        _rename_table_db_objects(conn, SCHEMA, old)
        op.rename_table(old, new, schema=SCHEMA)
        _rename_sequences(conn, SCHEMA, old, new)


def upgrade():
    conn = op.get_bind()
    _apply_table_renames(conn, _TABLE_RENAMES)


def downgrade():
    conn = op.get_bind()
    _apply_table_renames(conn, list(reversed(_TABLE_RENAMES)))

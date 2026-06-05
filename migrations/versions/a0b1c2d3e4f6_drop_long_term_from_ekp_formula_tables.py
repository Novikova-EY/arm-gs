# -*- coding: utf-8 -*-
"""Формулы экономики: убрать long_term_ из имён таблиц и объектов БД.

Revision ID: a0b1c2d3e4f6
Revises: z9a0b1c2d3e4
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

revision = "a0b1c2d3e4f6"
down_revision = "z9a0b1c2d3e4"
branch_labels = None
depends_on = None

SCHEMA = "gs_ekp"

_TABLE_RENAMES = [
    (
        "gs_ekp_long_term_accum_fixed_capital_formula_texts",
        "gs_ekp_accum_fixed_capital_formula_texts",
    ),
    (
        "gs_ekp_long_term_product_output_formula_texts",
        "gs_ekp_product_output_formula_texts",
    ),
    (
        "gs_ekp_long_term_ved_consumption_formula_texts",
        "gs_ekp_ved_consumption_formula_texts",
    ),
]

_OBJECT_RENAMES = [
    ("uq_gs_ekp_lt_afci_formula_texts_key", "uq_gs_ekp_afci_formula_texts_key"),
    ("uq_gs_ekp_lt_po_formula_texts_key", "uq_gs_ekp_po_formula_texts_key"),
    ("uq_gs_ekp_lt_ved_formula_texts_key", "uq_gs_ekp_ved_formula_texts_key"),
    ("ix_gs_ekp_lt_afci_formula_key", "ix_gs_ekp_afci_formula_key"),
    ("ix_gs_ekp_lt_po_formula_key", "ix_gs_ekp_po_formula_key"),
    ("ix_gs_ekp_lt_ved_formula_key", "ix_gs_ekp_ved_formula_key"),
]


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


def _rename_objects_on_table(conn, table: str) -> None:
    constraint_names = set(_list_table_constraints(conn, SCHEMA, table))
    for old, new in _OBJECT_RENAMES:
        if old in constraint_names:
            _rename_constraint(conn, SCHEMA, table, old, new)
        elif column_utils.index_exists(conn, SCHEMA, old):
            _rename_index(conn, SCHEMA, old, new)

    for index_name in _list_table_indexes(conn, SCHEMA, table):
        if "long_term_" in index_name:
            new_name = index_name.replace("long_term_", "", 1)
            if new_name != index_name:
                _rename_index(conn, SCHEMA, index_name, new_name)

    for constraint_name in _list_table_constraints(conn, SCHEMA, table):
        if "long_term_" in constraint_name:
            new_name = constraint_name.replace("long_term_", "", 1)
            if new_name != constraint_name:
                _rename_constraint(conn, SCHEMA, table, constraint_name, new_name)


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
            op.execute(sa.text(f'ALTER SEQUENCE "{SCHEMA}"."{old_seq}" RENAME TO "{new_seq}"'))


def _apply_table_renames(conn, renames: list[tuple[str, str]]) -> None:
    for old, new in renames:
        if not column_utils.table_exists(conn, SCHEMA, old):
            continue
        if column_utils.table_exists(conn, SCHEMA, new):
            continue
        _rename_objects_on_table(conn, old)
        op.rename_table(old, new, schema=SCHEMA)
        _rename_sequences(conn, old, new)
        _rename_objects_on_table(conn, new)


def upgrade():
    conn = op.get_bind()
    _apply_table_renames(conn, _TABLE_RENAMES)


def downgrade():
    conn = op.get_bind()
    _apply_table_renames(conn, list(reversed(_TABLE_RENAMES)))

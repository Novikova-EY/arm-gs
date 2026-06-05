# -*- coding: utf-8 -*-
"""Переименование gs_ec_long_term_electrical_intensity_formula_texts -> gs_ec_electrical_intensity_formula_texts.

Revision ID: j1k2l3m4n5o6
Revises: i0j1k2l3m4n5
Create Date: 2026-06-04
"""
import os
import sys

from alembic import op

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "j1k2l3m4n5o6"
down_revision = "i0j1k2l3m4n5"
branch_labels = None
depends_on = None

SCHEMA = "gs_ec"
OLD_TABLE = "gs_ec_long_term_electrical_intensity_formula_texts"
NEW_TABLE = "gs_ec_electrical_intensity_formula_texts"

OLD_UQ = "uq_gs_ec_lt_ei_formula_texts_key"
NEW_UQ = "uq_gs_ec_ei_formula_texts_key"
OLD_IX = "ix_gs_ec_lt_ei_formula_key"
NEW_IX = "ix_gs_ec_ei_formula_key"


def _rename_table(conn) -> None:
    if column_utils.table_exists(conn, SCHEMA, OLD_TABLE) and not column_utils.table_exists(
        conn, SCHEMA, NEW_TABLE
    ):
        op.rename_table(OLD_TABLE, NEW_TABLE, schema=SCHEMA)


def _rename_constraints_and_indexes(conn, *, old_uq: str, new_uq: str, old_ix: str, new_ix: str) -> None:
    if not column_utils.table_exists(conn, SCHEMA, NEW_TABLE):
        return
    if column_utils.constraint_exists(conn, SCHEMA, old_uq) and not column_utils.constraint_exists(
        conn, SCHEMA, new_uq
    ):
        op.execute(
            f'ALTER TABLE "{SCHEMA}"."{NEW_TABLE}" RENAME CONSTRAINT '
            f"{old_uq} TO {new_uq}"
        )
    if column_utils.index_exists(conn, SCHEMA, old_ix) and not column_utils.index_exists(
        conn, SCHEMA, new_ix
    ):
        op.execute(f'ALTER INDEX "{SCHEMA}".{old_ix} RENAME TO {new_ix}')


def upgrade():
    conn = op.get_bind()
    _rename_table(conn)
    _rename_constraints_and_indexes(
        conn, old_uq=OLD_UQ, new_uq=NEW_UQ, old_ix=OLD_IX, new_ix=NEW_IX
    )


def downgrade():
    conn = op.get_bind()
    _rename_constraints_and_indexes(
        conn, old_uq=NEW_UQ, new_uq=OLD_UQ, old_ix=NEW_IX, new_ix=OLD_IX
    )
    if column_utils.table_exists(conn, SCHEMA, NEW_TABLE) and not column_utils.table_exists(
        conn, SCHEMA, OLD_TABLE
    ):
        op.rename_table(NEW_TABLE, OLD_TABLE, schema=SCHEMA)

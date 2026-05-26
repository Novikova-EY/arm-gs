# -*- coding: utf-8 -*-
"""Переименование столбцов *_billion_kwh -> *_million_kwh в таблицах ТЭП ГЭС/ГАЭС.

Revision ID: d3e4f5a6b7c8
Revises: c1d2e3f4a5b6
Create Date: 2026-05-14
"""
import os
import sys

from alembic import op
from sqlalchemy import text

_MIGRATIONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS_DIR not in sys.path:
    sys.path.insert(0, _MIGRATIONS_DIR)
import column_utils  # noqa: E402

revision = "d3e4f5a6b7c8"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"

_KWH_COLUMN_RENAMES = (
    ("generation_average_multiyear_billion_kwh", "generation_average_multiyear_million_kwh"),
    ("generation_medium_water_50pct_billion_kwh", "generation_medium_water_50pct_million_kwh"),
    ("generation_low_water_95pct_billion_kwh", "generation_low_water_95pct_million_kwh"),
)


def _rename_column(conn, table: str, old_name: str, new_name: str) -> None:
    if not column_utils.table_has_column(conn, SCHEMA_GEN, table, old_name):
        return
    if column_utils.table_has_column(conn, SCHEMA_GEN, table, new_name):
        return
    op.execute(
        text(f'ALTER TABLE "{SCHEMA_GEN}"."{table}" RENAME COLUMN "{old_name}" TO "{new_name}"')
    )


def upgrade() -> None:
    conn = op.get_bind()
    for resolver in (
        column_utils.ges_tep_source_project_indicators_table_name,
        column_utils.gaes_tep_source_project_indicators_table_name,
    ):
        table_tep = resolver(conn, SCHEMA_GEN)
        if table_tep is None:
            continue
        for old_c, new_c in _KWH_COLUMN_RENAMES:
            _rename_column(conn, table_tep, old_c, new_c)


def downgrade() -> None:
    conn = op.get_bind()
    for resolver in (
        column_utils.ges_tep_source_project_indicators_table_name,
        column_utils.gaes_tep_source_project_indicators_table_name,
    ):
        table_tep = resolver(conn, SCHEMA_GEN)
        if table_tep is None:
            continue
        for old_c, new_c in reversed(_KWH_COLUMN_RENAMES):
            _rename_column(conn, table_tep, new_c, old_c)

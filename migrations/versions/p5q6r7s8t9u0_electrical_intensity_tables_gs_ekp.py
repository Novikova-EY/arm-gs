# -*- coding: utf-8 -*-
"""Электроёмкость: перенос таблиц из gs_ec в схему gs_ekp и префикс gs_ekp_.

Revision ID: p5q6r7s8t9u0
Revises: o4p5q6r7s8t9
Create Date: 2026-06-22
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

revision = "p5q6r7s8t9u0"
down_revision = "o4p5q6r7s8t9"
branch_labels = None
depends_on = None

SCHEMA_SOURCE = "gs_ec"
SCHEMA_TARGET = "gs_ekp"

_EI_TABLES = (
    "gs_ec_federal_district_electrical_intensity_year_params",
    "gs_ec_russia_federation_electrical_intensity_year_params",
    "gs_ec_federal_district_electrical_intensity_coefficients",
    "gs_ec_russia_federation_electrical_intensity_coefficients",
    "gs_ec_electrical_intensity_formula_texts",
    "gs_ec_long_term_electrical_intensity_formula_texts",
    "gs_ec_federal_district_population_consumption_year_params",
    "gs_ec_federal_district_population_consumption_coefficients",
    "gs_ec_federal_district_fd_total_consumption_coefficients",
)

_TABLE_RENAMES = [
    (
        "gs_ec_federal_district_electrical_intensity_year_params",
        "gs_ekp_federal_district_electrical_intensity_year_params",
    ),
    (
        "gs_ec_russia_federation_electrical_intensity_year_params",
        "gs_ekp_russia_federation_electrical_intensity_year_params",
    ),
    (
        "gs_ec_federal_district_electrical_intensity_coefficients",
        "gs_ekp_federal_district_electrical_intensity_coefficients",
    ),
    (
        "gs_ec_russia_federation_electrical_intensity_coefficients",
        "gs_ekp_russia_federation_electrical_intensity_coefficients",
    ),
    (
        "gs_ec_electrical_intensity_formula_texts",
        "gs_ekp_electrical_intensity_formula_texts",
    ),
    (
        "gs_ec_long_term_electrical_intensity_formula_texts",
        "gs_ekp_electrical_intensity_formula_texts",
    ),
    (
        "gs_ec_federal_district_population_consumption_year_params",
        "gs_ekp_federal_district_population_consumption_year_params",
    ),
    (
        "gs_ec_federal_district_population_consumption_coefficients",
        "gs_ekp_federal_district_population_consumption_coefficients",
    ),
    (
        "gs_ec_federal_district_fd_total_consumption_coefficients",
        "gs_ekp_federal_district_fd_total_consumption_coefficients",
    ),
]


def _schema_exists(connection, schema: str) -> bool:
    r = connection.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema"),
        {"schema": schema},
    )
    return r.fetchone() is not None


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


def _relocate_tables(conn, source_schema: str, target_schema: str) -> None:
    if not _schema_exists(conn, target_schema):
        op.execute(sa.text(f'CREATE SCHEMA "{target_schema}"'))

    for table in _EI_TABLES:
        if column_utils.table_exists(conn, target_schema, table):
            continue
        if not column_utils.table_exists(conn, source_schema, table):
            continue
        op.execute(
            sa.text(
                f'ALTER TABLE "{source_schema}"."{table}" SET SCHEMA "{target_schema}"'
            )
        )


def _apply_table_renames(conn, renames: list[tuple[str, str]]) -> None:
    for old, new in renames:
        if not column_utils.table_exists(conn, SCHEMA_TARGET, old):
            continue
        if column_utils.table_exists(conn, SCHEMA_TARGET, new):
            continue
        _rename_table_db_objects(conn, SCHEMA_TARGET, old)
        op.rename_table(old, new, schema=SCHEMA_TARGET)
        _rename_sequences(conn, SCHEMA_TARGET, old, new)


def upgrade():
    conn = op.get_bind()
    _relocate_tables(conn, SCHEMA_SOURCE, SCHEMA_TARGET)
    _apply_table_renames(conn, _TABLE_RENAMES)


def downgrade():
    conn = op.get_bind()
    _apply_table_renames(conn, list(reversed(_TABLE_RENAMES)))

    if not _schema_exists(conn, SCHEMA_SOURCE):
        op.execute(sa.text(f'CREATE SCHEMA "{SCHEMA_SOURCE}"'))

    for table in reversed(_EI_TABLES):
        target_name = table
        for old, new in _TABLE_RENAMES:
            if new == table:
                target_name = old
                break
        if column_utils.table_exists(conn, SCHEMA_SOURCE, target_name):
            continue
        if not column_utils.table_exists(conn, SCHEMA_TARGET, target_name):
            continue
        op.execute(
            sa.text(
                f'ALTER TABLE "{SCHEMA_TARGET}"."{target_name}" SET SCHEMA "{SCHEMA_SOURCE}"'
            )
        )

# -*- coding: utf-8 -*-
"""Ремонт имени таблицы коэффициентов ТЭП: финально gs_sys.gs_sys_tep_price_conversion_coefficients.

Revision ID: f0e1d2c3b4a5
Revises: e9f0a1b2c3d4
Create Date: 2026-05-14

На сервере иногда остаётся gs_sys.tep_price_conversion_coefficients (не отработала цепочка
c2d3 → m9n0) или gs_sys.gs_gen_tep_price_conversion_coefficients (перенос без финального
rename). Миграция m9n0o1p2q3r4 искала только gs_gen.gs_gen_tep_price_conversion_coefficients.
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "f0e1d2c3b4a5"
down_revision = "e9f0a1b2c3d4"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REF = "gs_sys"
TARGET = "gs_sys_tep_price_conversion_coefficients"
GEN_PREFixed = "gs_gen_tep_price_conversion_coefficients"
LEGACY_SHORT = "tep_price_conversion_coefficients"


def _row_count(conn: sa.Connection, schema: str, table: str) -> int:
    return conn.execute(
        sa.text(f'SELECT COUNT(*) FROM "{schema}"."{table}"'),
    ).scalar()


def _rename_within_schema(conn: sa.Connection, schema: str, src: str, dest: str) -> None:
    """Переименование src -> dest в schema; учёт пустой заглушки dest."""
    if not column_utils.table_exists(conn, schema, src):
        return
    if column_utils.table_exists(conn, schema, dest):
        n_dest = _row_count(conn, schema, dest)
        n_src = _row_count(conn, schema, src)
        if n_dest > 0 and n_src > 0:
            raise RuntimeError(
                f"Конфликт: в {schema} есть данные и в {src!r}, и в {dest!r}; нужна ручная правка."
            )
        if n_dest > 0 and n_src == 0:
            op.drop_table(src, schema=schema)
            return

        backup = f"{dest}__alembic_empty_stub_backup"
        if column_utils.table_exists(conn, schema, backup):
            op.drop_table(backup, schema=schema)
        op.rename_table(dest, backup, schema=schema)

        op.rename_table(src, dest, schema=schema)

        if column_utils.table_exists(conn, schema, backup):
            op.drop_table(backup, schema=schema)
        return

    op.rename_table(src, dest, schema=schema)


def _upgrade_impl(conn: sa.Connection) -> None:
    if column_utils.table_exists(conn, SCHEMA_REF, TARGET):
        if column_utils.table_exists(conn, SCHEMA_REF, LEGACY_SHORT):
            nt = _row_count(conn, SCHEMA_REF, TARGET)
            ns = _row_count(conn, SCHEMA_REF, LEGACY_SHORT)
            if nt > 0 and ns > 0:
                raise RuntimeError(
                    "В gs_sys одновременно заполнены "
                    f"{TARGET!r} и {LEGACY_SHORT!r}; нужна ручная правка."
                )
            if nt == 0:
                op.drop_table(TARGET, schema=SCHEMA_REF)
                op.rename_table(LEGACY_SHORT, TARGET, schema=SCHEMA_REF)
            elif ns == 0:
                op.drop_table(LEGACY_SHORT, schema=SCHEMA_REF)
        elif column_utils.table_exists(conn, SCHEMA_REF, GEN_PREFixed):
            nt = _row_count(conn, SCHEMA_REF, TARGET)
            ng = _row_count(conn, SCHEMA_REF, GEN_PREFixed)
            if nt > 0 and ng > 0:
                raise RuntimeError(
                    "В gs_sys одновременно заполнены "
                    f"{TARGET!r} и {GEN_PREFixed!r}; нужна ручная правка."
                )
            if nt == 0:
                op.drop_table(TARGET, schema=SCHEMA_REF)
                op.rename_table(GEN_PREFixed, TARGET, schema=SCHEMA_REF)
            elif ng == 0:
                op.drop_table(GEN_PREFixed, schema=SCHEMA_REF)
        return

    # Уже в gs_sys под промежуточным именем после SET SCHEMA
    if column_utils.table_exists(conn, SCHEMA_REF, GEN_PREFixed):
        _rename_within_schema(conn, SCHEMA_REF, GEN_PREFixed, TARGET)
        return

    if column_utils.table_exists(conn, SCHEMA_REF, LEGACY_SHORT):
        _rename_within_schema(conn, SCHEMA_REF, LEGACY_SHORT, TARGET)
        return

    if column_utils.table_exists(conn, SCHEMA_GEN, GEN_PREFixed):
        op.execute(
            sa.text(
                f'ALTER TABLE "{SCHEMA_GEN}"."{GEN_PREFixed}" SET SCHEMA "{SCHEMA_REF}"'
            ),
        )
        if column_utils.table_exists(conn, SCHEMA_REF, GEN_PREFixed):
            op.rename_table(GEN_PREFixed, TARGET, schema=SCHEMA_REF)
        return

    if column_utils.table_exists(conn, SCHEMA_GEN, LEGACY_SHORT):
        op.execute(
            sa.text(
                f'ALTER TABLE "{SCHEMA_GEN}"."{LEGACY_SHORT}" SET SCHEMA "{SCHEMA_REF}"'
            ),
        )
        if column_utils.table_exists(conn, SCHEMA_REF, LEGACY_SHORT):
            op.rename_table(LEGACY_SHORT, TARGET, schema=SCHEMA_REF)
        return


def upgrade():
    conn = op.get_bind()
    _upgrade_impl(conn)


def downgrade():
    pass

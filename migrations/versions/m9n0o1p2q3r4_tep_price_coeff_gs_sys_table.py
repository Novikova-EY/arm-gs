# -*- coding: utf-8 -*-
"""Перенос gs_gen_tep_price_conversion_coefficients -> gs_sys.gs_sys_tep_price_conversion_coefficients

Revision ID: m9n0o1p2q3r4
Revises: e0f1a2b3c4d5
Create Date: 2026-04-24
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "m9n0o1p2q3r4"
down_revision = "e0f1a2b3c4d5"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REF = "gs_sys"
OLD = "gs_gen_tep_price_conversion_coefficients"
NEW = "gs_sys_tep_price_conversion_coefficients"
LEGACY_SHORT = "tep_price_conversion_coefficients"


def _row_count(conn: sa.Connection, schema: str, table: str) -> int:
    return conn.execute(
        sa.text(f'SELECT COUNT(*) FROM "{schema}"."{table}"'),
    ).scalar()


def _rename_within_schema(conn: sa.Connection, schema: str, src: str, dest: str) -> None:
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


def upgrade():
    conn = op.get_bind()
    if column_utils.table_exists(conn, SCHEMA_REF, NEW):
        if column_utils.table_exists(conn, SCHEMA_REF, LEGACY_SHORT):
            nn = _row_count(conn, SCHEMA_REF, NEW)
            ns = _row_count(conn, SCHEMA_REF, LEGACY_SHORT)
            if nn > 0 and ns > 0:
                raise RuntimeError(
                    "В gs_sys одновременно заполнены "
                    f"{NEW!r} и {LEGACY_SHORT!r}; нужна ручная правка."
                )
            if nn == 0:
                op.drop_table(NEW, schema=SCHEMA_REF)
                op.rename_table(LEGACY_SHORT, NEW, schema=SCHEMA_REF)
            elif ns == 0:
                op.drop_table(LEGACY_SHORT, schema=SCHEMA_REF)
        elif column_utils.table_exists(conn, SCHEMA_REF, OLD):
            nn = _row_count(conn, SCHEMA_REF, NEW)
            no = _row_count(conn, SCHEMA_REF, OLD)
            if nn > 0 and no > 0:
                raise RuntimeError(
                    "В gs_sys одновременно заполнены "
                    f"{NEW!r} и {OLD!r}; нужна ручная правка."
                )
            if nn == 0:
                op.drop_table(NEW, schema=SCHEMA_REF)
                op.rename_table(OLD, NEW, schema=SCHEMA_REF)
            elif no == 0:
                op.drop_table(OLD, schema=SCHEMA_REF)
        return

    if column_utils.table_exists(conn, SCHEMA_REF, OLD):
        _rename_within_schema(conn, SCHEMA_REF, OLD, NEW)
        return

    if column_utils.table_exists(conn, SCHEMA_REF, LEGACY_SHORT):
        _rename_within_schema(conn, SCHEMA_REF, LEGACY_SHORT, NEW)
        return

    if column_utils.table_exists(conn, SCHEMA_GEN, OLD):
        op.execute(
            sa.text(
                f'ALTER TABLE "{SCHEMA_GEN}"."{OLD}" SET SCHEMA "{SCHEMA_REF}"'
            ),
        )
        if column_utils.table_exists(conn, SCHEMA_REF, OLD):
            op.rename_table(OLD, NEW, schema=SCHEMA_REF)
        return

    if column_utils.table_exists(conn, SCHEMA_GEN, LEGACY_SHORT):
        op.execute(
            sa.text(
                f'ALTER TABLE "{SCHEMA_GEN}"."{LEGACY_SHORT}" SET SCHEMA "{SCHEMA_REF}"'
            ),
        )
        if column_utils.table_exists(conn, SCHEMA_REF, LEGACY_SHORT):
            op.rename_table(LEGACY_SHORT, NEW, schema=SCHEMA_REF)
        return


def downgrade():
    conn = op.get_bind()
    if column_utils.table_exists(conn, SCHEMA_GEN, OLD):
        return
    if column_utils.table_exists(conn, SCHEMA_REF, NEW):
        op.rename_table(NEW, OLD, schema=SCHEMA_REF)
    if column_utils.table_exists(conn, SCHEMA_REF, OLD):
        op.execute(
            f'ALTER TABLE "{SCHEMA_REF}"."{OLD}" SET SCHEMA "{SCHEMA_GEN}"',
        )

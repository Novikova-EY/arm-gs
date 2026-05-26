# -*- coding: utf-8 -*-
"""Ремонт: справочники типов перспективных площадок только в gs_gen.

Revision ID: e9f0a1b2c3d4
Revises: d3e4f5a6b7c8
Create Date: 2026-05-14

Исправляет случай, когда d0e1f2a3b4c5 не перенесла таблицы из-за раннего ``continue``:
если в gs_gen уже существовала пустая таблица с целевым именем (например после
create_all), данные оставались в gs_sys под именами gs_gen_gs_prospective_place_types*.
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS_DIR not in sys.path:
    sys.path.insert(0, _MIGRATIONS_DIR)
import column_utils  # noqa: E402

revision = "e9f0a1b2c3d4"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None

SCHEMA_REFDATA = "gs_sys"
SCHEMA_GENERATION = "gs_gen"

_MOVES = [
    ("gs_gen_gs_prospective_place_types", "gs_gen_prospective_place_types"),
    ("gs_gen_gs_prospective_place_types_ges", "gs_gen_prospective_place_types_ges"),
    ("gs_gen_gs_prospective_place_types_gaes", "gs_gen_prospective_place_types_gaes"),
]


def _row_count(conn: sa.Connection, schema: str, table: str) -> int:
    return conn.execute(
        sa.text(f'SELECT COUNT(*) FROM "{schema}"."{table}"'),
    ).scalar()


def _id_name_snapshot(conn: sa.Connection, schema: str, table: str) -> list[tuple]:
    rows = conn.execute(
        sa.text(
            f'SELECT id, CAST(name AS TEXT) FROM "{schema}"."{table}" ORDER BY id'
        ),
    ).fetchall()
    return [tuple(r) for r in rows]


def _relocate_one(conn: sa.Connection, old: str, new: str) -> None:
    for _ in range(6):
        has_gen_old = column_utils.table_exists(conn, SCHEMA_GENERATION, old)
        if has_gen_old:
            op.rename_table(old, new, schema=SCHEMA_GENERATION)
            return

        has_sys_old = column_utils.table_exists(conn, SCHEMA_REFDATA, old)
        if not has_sys_old:
            return

        has_gen_new = column_utils.table_exists(conn, SCHEMA_GENERATION, new)

        if has_gen_new:
            n_new = _row_count(conn, SCHEMA_GENERATION, new)
            n_old = _row_count(conn, SCHEMA_REFDATA, old)
            if n_new > 0 and n_old > 0:
                snap_old = _id_name_snapshot(conn, SCHEMA_REFDATA, old)
                snap_new = _id_name_snapshot(conn, SCHEMA_GENERATION, new)
                fk_sys = column_utils.incoming_foreign_key_count(conn, SCHEMA_REFDATA, old)
                fk_gen = column_utils.incoming_foreign_key_count(conn, SCHEMA_GENERATION, new)
                if snap_old == snap_new:
                    if fk_sys == 0:
                        op.drop_table(old, schema=SCHEMA_REFDATA)
                        return
                    if fk_gen == 0:
                        op.drop_table(new, schema=SCHEMA_GENERATION)
                        continue
                raise RuntimeError(
                    f"Конфликт данных: gs_sys.{old} и gs_gen.{new} непусты; "
                    f"совпадение строк id/name: {snap_old == snap_new}; "
                    f"число FK на gs_sys.{old}={fk_sys}, на gs_gen.{new}={fk_gen}. "
                    "При одинаковых данных удалите таблицу без входящих FK или объедините вручную."
                )
            if n_new > 0 and n_old == 0:
                op.drop_table(old, schema=SCHEMA_REFDATA)
                return

            backup = f"{new}__alembic_empty_stub_backup"
            if column_utils.table_exists(conn, SCHEMA_GENERATION, backup):
                op.drop_table(backup, schema=SCHEMA_GENERATION)
            op.rename_table(new, backup, schema=SCHEMA_GENERATION)

            op.execute(
                sa.text(
                    f'ALTER TABLE "{SCHEMA_REFDATA}"."{old}" '
                    f'SET SCHEMA "{SCHEMA_GENERATION}"'
                ),
            )
            if column_utils.table_exists(conn, SCHEMA_GENERATION, old):
                op.rename_table(old, new, schema=SCHEMA_GENERATION)

            if column_utils.table_exists(conn, SCHEMA_GENERATION, backup):
                op.drop_table(backup, schema=SCHEMA_GENERATION)
            return

        op.execute(
            sa.text(
                f'ALTER TABLE "{SCHEMA_REFDATA}"."{old}" '
                f'SET SCHEMA "{SCHEMA_GENERATION}"'
            ),
        )
        if column_utils.table_exists(conn, SCHEMA_GENERATION, old):
            op.rename_table(old, new, schema=SCHEMA_GENERATION)
        return

    raise RuntimeError(
        f"Зацикливание при слиянии дубликатов gs_sys.{old} / gs_gen.{new}; правка вручную."
    )


def upgrade():
    conn = op.get_bind()
    for old, new in _MOVES:
        _relocate_one(conn, old, new)


def downgrade():
    pass

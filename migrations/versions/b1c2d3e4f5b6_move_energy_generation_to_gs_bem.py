# -*- coding: utf-8 -*-
"""Таблицы выработки ЭЭ: перенос из gs_gen в gs_bem с префиксом gs_bem_.

Revision ID: b1c2d3e4f5b6
Revises: z0a1b2c3d4e5
Create Date: 2026-06-09
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

revision = "b1c2d3e4f5b6"
down_revision = "z0a1b2c3d4e5"
branch_labels = None
depends_on = None

SCHEMA_SOURCE = "gs_gen"
SCHEMA_TARGET = "gs_bem"

_TABLES = (
    ("gs_gen_station_energy_generations", "gs_bem_station_energy_generations"),
    ("gs_gen_espp_energy_generations", "gs_bem_espp_energy_generations"),
    ("gs_gen_regional_energy_system_energy_generations", "gs_bem_regional_energy_system_energy_generations"),
)


def _schema_exists(connection, schema: str) -> bool:
    r = connection.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema"),
        {"schema": schema},
    )
    return r.fetchone() is not None


def _relocate_tables(conn, source_schema: str, target_schema: str) -> None:
    if not _schema_exists(conn, target_schema):
        op.execute(sa.text(f'CREATE SCHEMA "{target_schema}"'))

    for old_name, new_name in _TABLES:
        if column_utils.table_exists(conn, target_schema, new_name):
            continue
        if column_utils.table_exists(conn, target_schema, old_name):
            op.execute(
                sa.text(
                    f'ALTER TABLE "{target_schema}"."{old_name}" RENAME TO "{new_name}"'
                )
            )
            continue
        if not column_utils.table_exists(conn, source_schema, old_name):
            continue
        op.execute(
            sa.text(
                f'ALTER TABLE "{source_schema}"."{old_name}" SET SCHEMA "{target_schema}"'
            )
        )
        op.execute(
            sa.text(
                f'ALTER TABLE "{target_schema}"."{old_name}" RENAME TO "{new_name}"'
            )
        )


def upgrade():
    conn = op.get_bind()
    _relocate_tables(conn, SCHEMA_SOURCE, SCHEMA_TARGET)


def downgrade():
    conn = op.get_bind()
    if not _schema_exists(conn, SCHEMA_SOURCE):
        op.execute(sa.text(f'CREATE SCHEMA "{SCHEMA_SOURCE}"'))

    for old_name, new_name in reversed(_TABLES):
        if column_utils.table_exists(conn, SCHEMA_SOURCE, old_name):
            continue
        if not column_utils.table_exists(conn, SCHEMA_TARGET, new_name):
            continue
        op.execute(
            sa.text(
                f'ALTER TABLE "{SCHEMA_TARGET}"."{new_name}" RENAME TO "{old_name}"'
            )
        )
        op.execute(
            sa.text(
                f'ALTER TABLE "{SCHEMA_TARGET}"."{old_name}" SET SCHEMA "{SCHEMA_SOURCE}"'
            )
        )

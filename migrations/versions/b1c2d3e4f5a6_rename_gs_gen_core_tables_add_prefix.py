# -*- coding: utf-8 -*-
"""rename gs_gen core generation tables: add gs_gen_ prefix

Revision ID: b1c2d3e4f5a6
Revises: a6b7c8d9e0f1
Create Date: 2026-04-24

Переименование таблиц в схеме gs_gen: префикс gs_gen_ в имени таблицы
(модели app/generation/models).
"""
import os
import sys

from alembic import op

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "b1c2d3e4f5a6"
down_revision = "a6b7c8d9e0f1"
branch_labels = None
depends_on = None

SCHEMA = "gs_gen"

# Порядок: не критичен для PostgreSQL (FK обновляются вместе с rename).
_RENAMES = [
    ("station_groups", "gs_gen_station_groups"),
    ("stations", "gs_gen_stations"),
    ("station_powers", "gs_gen_station_powers"),
    ("machines", "gs_gen_machines"),
    ("machine_powers", "gs_gen_machine_powers"),
    ("machine_fuels", "gs_gen_machine_fuels"),
    ("machine_tes_types", "gs_gen_machine_tes_types"),
    ("machine_names", "gs_gen_machine_names"),
    ("pgu_machines", "gs_gen_pgu_machines"),
    ("pgu_machine_names", "gs_gen_pgu_machine_names"),
    ("pgu_machine_powers", "gs_gen_pgu_machine_powers"),
    ("boilers", "gs_gen_boilers"),
    ("documents_kommod", "gs_gen_documents_kommod"),
]


def upgrade():
    conn = op.get_bind()
    for old, new in _RENAMES:
        if column_utils.table_exists(conn, SCHEMA, old) and not column_utils.table_exists(
            conn, SCHEMA, new
        ):
            op.rename_table(old, new, schema=SCHEMA)


def downgrade():
    conn = op.get_bind()
    for old, new in reversed(_RENAMES):
        if column_utils.table_exists(conn, SCHEMA, new) and not column_utils.table_exists(
            conn, SCHEMA, old
        ):
            op.rename_table(new, old, schema=SCHEMA)

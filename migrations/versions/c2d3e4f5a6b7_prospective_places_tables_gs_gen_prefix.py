# -*- coding: utf-8 -*-
"""prospective_places: gs_gen_ prefix for table names

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-04-24

Префикс gs_gen_ в именах таблиц моделей app/generation/prospective_places/models
(схема gs_gen — перспективные площадки, ТЭП, коэффициенты; схема gs_sys — справочники типов площадок).
"""
import os
import sys

from alembic import op

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REF = "gs_sys"

# Таблицы в gs_gen
_RENAMES_GEN = [
    ("station_prospective_place_aes", "gs_gen_station_prospective_place_aes"),
    ("machine_prospective_place_aes", "gs_gen_machine_prospective_place_aes"),
    ("station_prospective_place_ges", "gs_gen_station_prospective_place_ges"),
    ("ges_tep_source_project_indicators", "gs_gen_ges_tep_source_project_indicators"),
    ("station_prospective_place_gaes", "gs_gen_station_prospective_place_gaes"),
    ("gaes_tep_source_project_indicators", "gs_gen_gaes_tep_source_project_indicators"),
    ("tep_price_conversion_coefficients", "gs_gen_tep_price_conversion_coefficients"),
]

# Справочники в gs_sys
_RENAMES_REF = [
    ("gs_prospective_place_types", "gs_gen_gs_prospective_place_types"),
    ("gs_prospective_place_types_ges", "gs_gen_gs_prospective_place_types_ges"),
    ("gs_prospective_place_types_gaes", "gs_gen_gs_prospective_place_types_gaes"),
]


def upgrade():
    conn = op.get_bind()
    for old, new in _RENAMES_REF:
        if column_utils.table_exists(conn, SCHEMA_REF, old) and not column_utils.table_exists(
            conn, SCHEMA_REF, new
        ):
            op.rename_table(old, new, schema=SCHEMA_REF)
    for old, new in _RENAMES_GEN:
        if column_utils.table_exists(conn, SCHEMA_GEN, old) and not column_utils.table_exists(
            conn, SCHEMA_GEN, new
        ):
            op.rename_table(old, new, schema=SCHEMA_GEN)


def downgrade():
    conn = op.get_bind()
    for old, new in reversed(_RENAMES_GEN):
        if column_utils.table_exists(conn, SCHEMA_GEN, new) and not column_utils.table_exists(
            conn, SCHEMA_GEN, old
        ):
            op.rename_table(new, old, schema=SCHEMA_GEN)
    for old, new in reversed(_RENAMES_REF):
        if column_utils.table_exists(conn, SCHEMA_REF, new) and not column_utils.table_exists(
            conn, SCHEMA_REF, old
        ):
            op.rename_table(new, old, schema=SCHEMA_REF)

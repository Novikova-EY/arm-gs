# -*- coding: utf-8 -*-
"""Прогноз выработки ГЭС/ГАЭС: place_kind station для карточки электростанции.

Revision ID: h4y5d6r7o8s9
Revises: dexp1d2a3t4e5
Create Date: 2026-09-17
"""
import os
import sys

from alembic import op

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "h4y5d6r7o8s9"
down_revision = "dexp1d2a3t4e5"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE = "gs_gen_prospective_place_hydro_energy_forecasts"
CONSTRAINT = "ck_pp_hydro_forecast_place_kind"


def upgrade():
    conn = op.get_bind()
    if not column_utils.table_exists(conn, SCHEMA_GEN, TABLE):
        return
    if column_utils.constraint_exists(conn, SCHEMA_GEN, CONSTRAINT):
        op.drop_constraint(CONSTRAINT, TABLE, schema=SCHEMA_GEN, type_="check")
    op.create_check_constraint(
        CONSTRAINT,
        TABLE,
        "place_kind IN ('ges', 'gaes', 'station')",
        schema=SCHEMA_GEN,
    )


def downgrade():
    conn = op.get_bind()
    if not column_utils.table_exists(conn, SCHEMA_GEN, TABLE):
        return
    if column_utils.constraint_exists(conn, SCHEMA_GEN, CONSTRAINT):
        op.drop_constraint(CONSTRAINT, TABLE, schema=SCHEMA_GEN, type_="check")
    op.create_check_constraint(
        CONSTRAINT,
        TABLE,
        "place_kind IN ('ges', 'gaes')",
        schema=SCHEMA_GEN,
    )

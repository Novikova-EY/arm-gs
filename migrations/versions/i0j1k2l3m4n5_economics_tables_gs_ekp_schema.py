# -*- coding: utf-8 -*-
"""Таблицы раздела «Экономика»: перенос из gs_ec в gs_ekp.

Revision ID: i0j1k2l3m4n5
Revises: h9i0j1k2l3m4
Create Date: 2026-06-04
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

revision = "i0j1k2l3m4n5"
down_revision = "h9i0j1k2l3m4"
branch_labels = None
depends_on = None

SCHEMA_SOURCE = "gs_ec"
SCHEMA_TARGET = "gs_ekp"

_ECONOMICS_TABLES = (
    "gs_ec_federal_district_economic_activity_accum_fixed_capital_params",
    "gs_ec_federal_district_economic_activity_consumption_params",
    "gs_ec_federal_district_economic_activity_product_output_params",
    "gs_ec_federal_district_population_params",
    "gs_ec_long_term_accum_fixed_capital_formula_texts",
    "gs_ec_long_term_product_output_formula_texts",
    "gs_ec_long_term_ved_consumption_formula_texts",
    "gs_ec_russia_federation_economic_activity_accum_fixed_capital_params",
    "gs_ec_russia_federation_economic_activity_consumption_params",
    "gs_ec_russia_federation_economic_activity_product_output_params",
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

    for table in _ECONOMICS_TABLES:
        if column_utils.table_exists(conn, target_schema, table):
            continue
        if not column_utils.table_exists(conn, source_schema, table):
            continue
        op.execute(
            sa.text(
                f'ALTER TABLE "{source_schema}"."{table}" SET SCHEMA "{target_schema}"'
            )
        )


def upgrade():
    conn = op.get_bind()
    _relocate_tables(conn, SCHEMA_SOURCE, SCHEMA_TARGET)


def downgrade():
    conn = op.get_bind()
    if not _schema_exists(conn, SCHEMA_SOURCE):
        op.execute(sa.text(f'CREATE SCHEMA "{SCHEMA_SOURCE}"'))

    for table in reversed(_ECONOMICS_TABLES):
        if column_utils.table_exists(conn, SCHEMA_SOURCE, table):
            continue
        if not column_utils.table_exists(conn, SCHEMA_TARGET, table):
            continue
        op.execute(
            sa.text(
                f'ALTER TABLE "{SCHEMA_TARGET}"."{table}" SET SCHEMA "{SCHEMA_SOURCE}"'
            )
        )

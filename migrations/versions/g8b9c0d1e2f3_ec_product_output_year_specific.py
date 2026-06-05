# -*- coding: utf-8 -*-
"""Выпуск продукции: год цен (Year) — id_year_specific_product_output.

Revision ID: g8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-06-03
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "g8b9c0d1e2f3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None

SCHEMA_EC = "gs_ec"
SCHEMA_REFDATA = "gs_sys"

COL = "id_year_specific_product_output"

TABLES = (
    "gs_ec_federal_district_economic_activity_product_output_params",
    "gs_ec_russia_federation_economic_activity_product_output_params",
)


def _add_year_specific_column(conn, table: str, table_years: str, pfx: str) -> None:
    if not column_utils.table_exists(conn, SCHEMA_EC, table):
        return
    if column_utils.table_has_column(conn, SCHEMA_EC, table, COL):
        return

    op.add_column(
        table,
        sa.Column(COL, sa.Integer(), nullable=True),
        schema=SCHEMA_EC,
    )
    fk_name = f"fk_ec_{pfx}_po_year_spec_out"
    if not column_utils.constraint_exists(conn, SCHEMA_EC, fk_name):
        op.create_foreign_key(
            fk_name,
            table,
            table_years,
            [COL],
            ["id"],
            source_schema=SCHEMA_EC,
            referent_schema=SCHEMA_REFDATA,
            ondelete="SET NULL",
        )
    ix_name = f"ix_ec_{pfx}_po_id_year_spec_out"
    if not column_utils.index_exists(conn, SCHEMA_EC, ix_name):
        op.create_index(
            ix_name,
            table,
            [COL],
            unique=False,
            schema=SCHEMA_EC,
        )


def upgrade():
    conn = op.get_bind()
    table_years = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_years")
    if table_years is None:
        raise RuntimeError(
            f"Не найдена таблица годов в {SCHEMA_REFDATA} "
            "(ожидались gs_sys_years или gs_years)"
        )

    _add_year_specific_column(conn, TABLES[0], table_years, "fd")
    _add_year_specific_column(conn, TABLES[1], table_years, "rf")


def downgrade():
    conn = op.get_bind()
    for table, pfx in (TABLES[0], "fd"), (TABLES[1], "rf"):
        if not column_utils.table_exists(conn, SCHEMA_EC, table):
            continue
        ix_name = f"ix_ec_{pfx}_po_id_year_spec_out"
        if column_utils.index_exists(conn, SCHEMA_EC, ix_name):
            op.drop_index(ix_name, table_name=table, schema=SCHEMA_EC)
        fk_name = f"fk_ec_{pfx}_po_year_spec_out"
        if column_utils.constraint_exists(conn, SCHEMA_EC, fk_name):
            op.drop_constraint(fk_name, table, schema=SCHEMA_EC, type_="foreignkey")
        if column_utils.table_has_column(conn, SCHEMA_EC, table, COL):
            op.drop_column(table, COL, schema=SCHEMA_EC)

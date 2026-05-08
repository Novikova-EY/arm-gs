# -*- coding: utf-8 -*-
"""Переименование ges_tep_price_conversion_coefficients -> tep_price_conversion_coefficients
(общие коэффициенты ТЭП для всех типов станций).

Revision ID: z2b3c4d5e6f8
Revises: z1a2b3c4d5e6
Create Date: 2026-04-13
"""
import os
import sys

from alembic import op

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "z2b3c4d5e6f8"
down_revision = "z1a2b3c4d5e6"
branch_labels = None
depends_on = None

SCHEMA = "gs_gen"
OLD_TABLE = "ges_tep_price_conversion_coefficients"
NEW_TABLE = "tep_price_conversion_coefficients"


def upgrade():
    conn = op.get_bind()
    if column_utils.table_exists(conn, SCHEMA, OLD_TABLE) and not column_utils.table_exists(conn, SCHEMA, NEW_TABLE):
        op.rename_table(OLD_TABLE, NEW_TABLE, schema=SCHEMA)
    if (
        column_utils.table_exists(conn, SCHEMA, NEW_TABLE)
        and column_utils.index_exists(conn, SCHEMA, "ix_ges_tep_price_conv_coeff_id_year")
        and not column_utils.index_exists(conn, SCHEMA, "ix_tep_price_conv_coeff_id_year")
    ):
        op.execute(
            f'ALTER INDEX "{SCHEMA}".ix_ges_tep_price_conv_coeff_id_year '
            "RENAME TO ix_tep_price_conv_coeff_id_year"
        )
    if (
        column_utils.table_exists(conn, SCHEMA, NEW_TABLE)
        and column_utils.index_exists(conn, SCHEMA, "ix_ges_tep_price_conv_coeff_database_version_id")
        and not column_utils.index_exists(conn, SCHEMA, "ix_tep_price_conv_coeff_database_version_id")
    ):
        op.execute(
            f'ALTER INDEX "{SCHEMA}".ix_ges_tep_price_conv_coeff_database_version_id '
            "RENAME TO ix_tep_price_conv_coeff_database_version_id"
        )
    if (
        column_utils.table_exists(conn, SCHEMA, NEW_TABLE)
        and column_utils.constraint_exists(conn, SCHEMA, "uq_ges_tep_price_conv_coeff_version_year")
        and not column_utils.constraint_exists(conn, SCHEMA, "uq_tep_price_conv_coeff_version_year")
    ):
        op.execute(
            f'ALTER TABLE "{SCHEMA}"."{NEW_TABLE}" RENAME CONSTRAINT '
            "uq_ges_tep_price_conv_coeff_version_year TO uq_tep_price_conv_coeff_version_year"
        )


def downgrade():
    conn = op.get_bind()
    if (
        column_utils.table_exists(conn, SCHEMA, NEW_TABLE)
        and column_utils.constraint_exists(conn, SCHEMA, "uq_tep_price_conv_coeff_version_year")
        and not column_utils.constraint_exists(conn, SCHEMA, "uq_ges_tep_price_conv_coeff_version_year")
    ):
        op.execute(
            f'ALTER TABLE "{SCHEMA}"."{NEW_TABLE}" RENAME CONSTRAINT '
            "uq_tep_price_conv_coeff_version_year TO uq_ges_tep_price_conv_coeff_version_year"
        )
    if (
        column_utils.table_exists(conn, SCHEMA, NEW_TABLE)
        and column_utils.index_exists(conn, SCHEMA, "ix_tep_price_conv_coeff_database_version_id")
        and not column_utils.index_exists(conn, SCHEMA, "ix_ges_tep_price_conv_coeff_database_version_id")
    ):
        op.execute(
            f'ALTER INDEX "{SCHEMA}".ix_tep_price_conv_coeff_database_version_id '
            "RENAME TO ix_ges_tep_price_conv_coeff_database_version_id"
        )
    if (
        column_utils.table_exists(conn, SCHEMA, NEW_TABLE)
        and column_utils.index_exists(conn, SCHEMA, "ix_tep_price_conv_coeff_id_year")
        and not column_utils.index_exists(conn, SCHEMA, "ix_ges_tep_price_conv_coeff_id_year")
    ):
        op.execute(
            f'ALTER INDEX "{SCHEMA}".ix_tep_price_conv_coeff_id_year '
            "RENAME TO ix_ges_tep_price_conv_coeff_id_year"
        )
    if column_utils.table_exists(conn, SCHEMA, NEW_TABLE) and not column_utils.table_exists(conn, SCHEMA, OLD_TABLE):
        op.rename_table(NEW_TABLE, OLD_TABLE, schema=SCHEMA)

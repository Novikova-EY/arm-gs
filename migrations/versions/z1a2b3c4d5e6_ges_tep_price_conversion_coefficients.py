# -*- coding: utf-8 -*-
"""ges_tep_price_conversion_coefficients: коэффициенты перевода цен ТЭП ГЭС.

Revision ID: z1a2b3c4d5e6
Revises: y0z1a2b3c4d5
Create Date: 2026-04-13
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402


revision = "z1a2b3c4d5e6"
down_revision = "y0z1a2b3c4d5"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REFDATA = "gs_sys"
TABLE = "ges_tep_price_conversion_coefficients"


def upgrade():
    conn = op.get_bind()
    ref_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REFDATA)
    table_years = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_years")
    if ref_versions is None:
        raise RuntimeError(
            f"Не найдена таблица версий БД в {SCHEMA_REFDATA} "
            "(gs_sys_database_versions или gs_database_versions как BASE TABLE)"
        )
    if table_years is None:
        return
    # Если следующая миграция z2 уже успела переименовать таблицу, повторно создавать ничего не нужно.
    if not (
        column_utils.table_exists(conn, SCHEMA_GEN, TABLE)
        or column_utils.table_exists(conn, SCHEMA_GEN, "tep_price_conversion_coefficients")
    ):
        op.create_table(
            TABLE,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("id_year", sa.Integer(), nullable=False),
            sa.Column("coefficient", sa.Numeric(24, 10), nullable=True),
            sa.Column("database_version_id", sa.Integer(), nullable=False),
            sa.Column("created_by", sa.String(length=255), nullable=True),
            sa.Column("modified_by", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["id_year"], [f"{SCHEMA_REFDATA}.{table_years}.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(
                ["database_version_id"],
                [f"{SCHEMA_REFDATA}.{ref_versions}.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "database_version_id",
                "id_year",
                name="uq_ges_tep_price_conv_coeff_version_year",
            ),
            schema=SCHEMA_GEN,
        )
    if column_utils.table_exists(conn, SCHEMA_GEN, TABLE):
        if not column_utils.index_exists(conn, SCHEMA_GEN, "ix_ges_tep_price_conv_coeff_id_year"):
            op.create_index(
                "ix_ges_tep_price_conv_coeff_id_year",
                TABLE,
                ["id_year"],
                unique=False,
                schema=SCHEMA_GEN,
            )
        if not column_utils.index_exists(conn, SCHEMA_GEN, "ix_ges_tep_price_conv_coeff_database_version_id"):
            op.create_index(
                "ix_ges_tep_price_conv_coeff_database_version_id",
                TABLE,
                ["database_version_id"],
                unique=False,
                schema=SCHEMA_GEN,
            )


def downgrade():
    op.drop_index(
        "ix_ges_tep_price_conv_coeff_database_version_id",
        table_name=TABLE,
        schema=SCHEMA_GEN,
    )
    op.drop_index("ix_ges_tep_price_conv_coeff_id_year", table_name=TABLE, schema=SCHEMA_GEN)
    op.drop_table(TABLE, schema=SCHEMA_GEN)

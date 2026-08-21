# -*- coding: utf-8 -*-
"""Ручной ввод «Экспорт мощности» на страницах баланса мощности.

Revision ID: z7a8b9c0d1e2
Revises: z6a7b8c9d0e1
Create Date: 2026-08-20
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

revision = "z7a8b9c0d1e2"
down_revision = "z6a7b8c9d0e1"
branch_labels = None
depends_on = None

SCHEMA = "gs_bem"
SCHEMA_REFDATA = "gs_sys"
TABLE = "gs_bem_power_balance_export_values"


def _schema_exists(connection, schema: str) -> bool:
    row = connection.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema"),
        {"schema": schema},
    ).fetchone()
    return row is not None


def upgrade():
    conn = op.get_bind()
    if column_utils.table_exists(conn, SCHEMA, TABLE):
        return
    if not _schema_exists(conn, SCHEMA):
        op.execute(sa.text(f'CREATE SCHEMA "{SCHEMA}"'))
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sheet_slug", sa.String(length=128), nullable=False),
        sa.Column("year_number", sa.Integer(), nullable=False),
        sa.Column("value_mw", sa.Numeric(25, 16), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_bem_pb_exp_sheet",
        TABLE,
        ["sheet_slug"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_bem_pb_exp_year",
        TABLE,
        ["year_number"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_bem_pb_exp_dbver",
        TABLE,
        ["database_version_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.execute(
        sa.text(
            f'CREATE UNIQUE INDEX uq_gs_bem_pb_exp_sheet_year_ver '
            f'ON "{SCHEMA}"."{TABLE}" '
            f"(sheet_slug, year_number, COALESCE(database_version_id, -1))"
        )
    )
    ref_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REFDATA)
    if ref_versions is not None:
        op.create_foreign_key(
            "fk_gs_bem_pb_exp_dbver",
            TABLE,
            ref_versions,
            ["database_version_id"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA_REFDATA,
            ondelete="SET NULL",
        )


def downgrade():
    conn = op.get_bind()
    if column_utils.table_exists(conn, SCHEMA, TABLE):
        op.execute(sa.text(f'DROP TABLE IF EXISTS "{SCHEMA}"."{TABLE}" CASCADE'))

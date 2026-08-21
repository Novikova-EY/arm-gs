# -*- coding: utf-8 -*-
"""Таблицы ручного ввода баланса электрической энергии (gs_bem).

Revision ID: b0c1d2e3f4a6
Revises: a9c8b7d6e5f4
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

revision = "b0c1d2e3f4a6"
down_revision = "a9c8b7d6e5f4"
branch_labels = None
depends_on = None

SCHEMA = "gs_bem"
SCHEMA_REFDATA = "gs_sys"
EXPORT_TABLE = "gs_bem_ee_balance_export_values"
ROWS_TABLE = "gs_bem_ee_balance_custom_flow_rows"
VALUES_TABLE = "gs_bem_ee_balance_custom_flow_values"


def _schema_exists(connection, schema: str) -> bool:
    row = connection.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema"),
        {"schema": schema},
    ).fetchone()
    return row is not None


def upgrade():
    conn = op.get_bind()
    if not _schema_exists(conn, SCHEMA):
        op.execute(sa.text(f'CREATE SCHEMA "{SCHEMA}"'))
    ref_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REFDATA)

    if not column_utils.table_exists(conn, SCHEMA, EXPORT_TABLE):
        op.create_table(
            EXPORT_TABLE,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("sheet_slug", sa.String(length=128), nullable=False),
            sa.Column("year_number", sa.Integer(), nullable=False),
            sa.Column("value_mln_kvtch", sa.Numeric(25, 16), nullable=True),
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
            "ix_gs_bem_eb_exp_sheet",
            EXPORT_TABLE,
            ["sheet_slug"],
            unique=False,
            schema=SCHEMA,
        )
        op.create_index(
            "ix_gs_bem_eb_exp_year",
            EXPORT_TABLE,
            ["year_number"],
            unique=False,
            schema=SCHEMA,
        )
        op.create_index(
            "ix_gs_bem_eb_exp_dbver",
            EXPORT_TABLE,
            ["database_version_id"],
            unique=False,
            schema=SCHEMA,
        )
        op.execute(
            sa.text(
                f'CREATE UNIQUE INDEX uq_gs_bem_eb_exp_sheet_year_ver '
                f'ON "{SCHEMA}"."{EXPORT_TABLE}" '
                f"(sheet_slug, year_number, COALESCE(database_version_id, -1))"
            )
        )
        if ref_versions is not None:
            op.create_foreign_key(
                "fk_gs_bem_eb_exp_dbver",
                EXPORT_TABLE,
                ref_versions,
                ["database_version_id"],
                ["id"],
                source_schema=SCHEMA,
                referent_schema=SCHEMA_REFDATA,
                ondelete="SET NULL",
            )

    if not column_utils.table_exists(conn, SCHEMA, ROWS_TABLE):
        op.create_table(
            ROWS_TABLE,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("sheet_slug", sa.String(length=128), nullable=False),
            sa.Column("direction", sa.String(length=16), nullable=False),
            sa.Column("parent_key", sa.String(length=128), nullable=True),
            sa.Column("label", sa.String(length=500), nullable=False, server_default=""),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
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
            "ix_gs_bem_eb_cfr_sheet",
            ROWS_TABLE,
            ["sheet_slug"],
            unique=False,
            schema=SCHEMA,
        )
        op.create_index(
            "ix_gs_bem_eb_cfr_direction",
            ROWS_TABLE,
            ["direction"],
            unique=False,
            schema=SCHEMA,
        )
        op.create_index(
            "ix_gs_bem_eb_cfr_dbver",
            ROWS_TABLE,
            ["database_version_id"],
            unique=False,
            schema=SCHEMA,
        )
        op.create_index(
            "ix_gs_bem_eb_cfr_parent_key",
            ROWS_TABLE,
            ["parent_key"],
            unique=False,
            schema=SCHEMA,
        )
        op.create_index(
            "ix_gs_bem_eb_cfr_sheet_dir_ord",
            ROWS_TABLE,
            ["sheet_slug", "direction", "sort_order"],
            unique=False,
            schema=SCHEMA,
        )
        if ref_versions is not None:
            op.create_foreign_key(
                "fk_gs_bem_eb_cfr_dbver",
                ROWS_TABLE,
                ref_versions,
                ["database_version_id"],
                ["id"],
                source_schema=SCHEMA,
                referent_schema=SCHEMA_REFDATA,
                ondelete="SET NULL",
            )

    if column_utils.table_exists(conn, SCHEMA, VALUES_TABLE):
        return

    op.create_table(
        VALUES_TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_row", sa.Integer(), nullable=False),
        sa.Column("year_number", sa.Integer(), nullable=False),
        sa.Column("value_mln_kvtch", sa.Numeric(25, 16), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["id_row"],
            [f"{SCHEMA}.{ROWS_TABLE}.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_bem_eb_cfv_row",
        VALUES_TABLE,
        ["id_row"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_bem_eb_cfv_year",
        VALUES_TABLE,
        ["year_number"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_bem_eb_cfv_dbver",
        VALUES_TABLE,
        ["database_version_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.execute(
        sa.text(
            f'CREATE UNIQUE INDEX uq_gs_bem_eb_cfv_row_year_ver '
            f'ON "{SCHEMA}"."{VALUES_TABLE}" '
            f"(id_row, year_number, COALESCE(database_version_id, -1))"
        )
    )
    if ref_versions is not None:
        op.create_foreign_key(
            "fk_gs_bem_eb_cfv_dbver",
            VALUES_TABLE,
            ref_versions,
            ["database_version_id"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA_REFDATA,
            ondelete="SET NULL",
        )


def downgrade():
    conn = op.get_bind()
    if column_utils.table_exists(conn, SCHEMA, VALUES_TABLE):
        op.execute(sa.text(f'DROP TABLE IF EXISTS "{SCHEMA}"."{VALUES_TABLE}" CASCADE'))
    if column_utils.table_exists(conn, SCHEMA, ROWS_TABLE):
        op.execute(sa.text(f'DROP TABLE IF EXISTS "{SCHEMA}"."{ROWS_TABLE}" CASCADE'))
    if column_utils.table_exists(conn, SCHEMA, EXPORT_TABLE):
        op.execute(sa.text(f'DROP TABLE IF EXISTS "{SCHEMA}"."{EXPORT_TABLE}" CASCADE'))

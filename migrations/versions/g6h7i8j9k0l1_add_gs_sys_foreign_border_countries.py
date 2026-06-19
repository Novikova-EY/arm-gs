# -*- coding: utf-8 -*-
"""Справочник зарубежных стран, имеющих общие границы с РФ.

Revision ID: g6h7i8j9k0l1
Revises: f5a6b7c8d9e0
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

revision = "g6h7i8j9k0l1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None

SCHEMA_REF = "gs_sys"
TABLE = "gs_sys_foreign_border_countries"


def _table_exists(conn, schema: str, table: str) -> bool:
    r = conn.execute(
        text(
            "SELECT 1 FROM pg_tables "
            "WHERE schemaname = :schema AND tablename = :table"
        ),
        {"schema": schema, "table": table},
    )
    return r.fetchone() is not None


def upgrade():
    conn = op.get_bind()
    if _table_exists(conn, SCHEMA_REF, TABLE):
        return

    ref_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REF)
    if ref_versions is None:
        raise RuntimeError(
            f"Не найдена таблица версий БД в {SCHEMA_REF} "
            "(gs_sys_database_versions или gs_database_versions)"
        )

    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("ref_uuid", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "database_version_id",
            "name",
            name="uq_gs_sys_foreign_border_countries_ver_name",
        ),
        schema=SCHEMA_REF,
    )
    op.create_index(
        "ix_gs_sys_foreign_border_countries_name",
        TABLE,
        ["name"],
        unique=False,
        schema=SCHEMA_REF,
    )
    op.create_index(
        "ix_gs_sys_foreign_border_countries_ref_uuid",
        TABLE,
        ["ref_uuid"],
        unique=False,
        schema=SCHEMA_REF,
    )
    op.create_index(
        "ix_gs_sys_foreign_border_countries_database_version_id",
        TABLE,
        ["database_version_id"],
        unique=False,
        schema=SCHEMA_REF,
    )
    op.create_foreign_key(
        "fk_gs_sys_foreign_border_countries_database_version",
        TABLE,
        ref_versions,
        ["database_version_id"],
        ["id"],
        source_schema=SCHEMA_REF,
        referent_schema=SCHEMA_REF,
        ondelete="SET NULL",
    )


def downgrade():
    conn = op.get_bind()
    if _table_exists(conn, SCHEMA_REF, TABLE):
        op.drop_table(TABLE, schema=SCHEMA_REF)

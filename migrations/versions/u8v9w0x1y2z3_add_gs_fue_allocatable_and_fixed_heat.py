# -*- coding: utf-8 -*-
"""Таблицы распределяемого и фиксированного тепла (Access «Распределяемое_тепло», «Фиксированное_тепло»).

Revision ID: u8v9w0x1y2z3
Revises: t7u8v9w0x1y2
Create Date: 2026-08-17
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


revision = "u8v9w0x1y2z3"
down_revision = "t7u8v9w0x1y2"
branch_labels = None
depends_on = None

SCHEMA = "gs_fue"
ALLOC_TABLE = "gs_fue_allocatable_heat"
FIXED_TABLE = "gs_fue_fixed_heat"


def _table_exists(connection, table: str) -> bool:
    result = connection.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :table"
        ),
        {"schema": SCHEMA, "table": table},
    )
    return result.fetchone() is not None


def upgrade():
    conn = op.get_bind()
    ref_versions = column_utils.database_versions_physical_table_name(conn, "gs_sys")
    if ref_versions is None:
        raise RuntimeError(
            "Не найдена таблица версий БД в gs_sys "
            "(gs_sys_database_versions или gs_database_versions как BASE TABLE)"
        )
    version_fk = f"gs_sys.{ref_versions}.id"

    if not _table_exists(conn, ALLOC_TABLE):
        op.create_table(
            ALLOC_TABLE,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("scope", sa.String(length=8), nullable=False, server_default="oes"),
            sa.Column("code", sa.Integer(), nullable=False),
            sa.Column("year_number", sa.Integer(), nullable=False),
            sa.Column("q_ras", sa.Numeric(precision=36, scale=16), nullable=True),
            sa.Column("prirost", sa.Numeric(precision=36, scale=16), nullable=True),
            sa.Column("hs", sa.Numeric(precision=36, scale=16), nullable=True),
            sa.Column("ri", sa.Numeric(precision=36, scale=16), nullable=True),
            sa.Column("database_version_id", sa.Integer(), nullable=True),
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
            sa.ForeignKeyConstraint(
                ["database_version_id"],
                [version_fk],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "scope",
                "code",
                "year_number",
                "database_version_id",
                name="uq_fue_allocatable_heat_scope_code_year_ver",
            ),
            schema=SCHEMA,
        )
        op.create_index(
            f"ix_{ALLOC_TABLE}_scope", ALLOC_TABLE, ["scope"], unique=False, schema=SCHEMA
        )
        op.create_index(
            f"ix_{ALLOC_TABLE}_code", ALLOC_TABLE, ["code"], unique=False, schema=SCHEMA
        )
        op.create_index(
            f"ix_{ALLOC_TABLE}_year_number",
            ALLOC_TABLE,
            ["year_number"],
            unique=False,
            schema=SCHEMA,
        )
        op.create_index(
            f"ix_{ALLOC_TABLE}_database_version_id",
            ALLOC_TABLE,
            ["database_version_id"],
            unique=False,
            schema=SCHEMA,
        )

    if not _table_exists(conn, FIXED_TABLE):
        op.create_table(
            FIXED_TABLE,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("numb1120", sa.Integer(), nullable=False),
            sa.Column("database_version_id", sa.Integer(), nullable=True),
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
            sa.ForeignKeyConstraint(
                ["database_version_id"],
                [version_fk],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "numb1120",
                "database_version_id",
                name="uq_fue_fixed_heat_numb_ver",
            ),
            schema=SCHEMA,
        )
        op.create_index(
            f"ix_{FIXED_TABLE}_numb1120",
            FIXED_TABLE,
            ["numb1120"],
            unique=False,
            schema=SCHEMA,
        )
        op.create_index(
            f"ix_{FIXED_TABLE}_database_version_id",
            FIXED_TABLE,
            ["database_version_id"],
            unique=False,
            schema=SCHEMA,
        )


def downgrade():
    conn = op.get_bind()
    if _table_exists(conn, FIXED_TABLE):
        op.drop_table(FIXED_TABLE, schema=SCHEMA)
    if _table_exists(conn, ALLOC_TABLE):
        op.drop_table(ALLOC_TABLE, schema=SCHEMA)

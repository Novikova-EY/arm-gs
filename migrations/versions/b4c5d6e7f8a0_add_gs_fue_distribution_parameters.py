# -*- coding: utf-8 -*-
"""Таблица gs_fue_distribution_parameters (Параметры-распределения).

Revision ID: b4c5d6e7f8a0
Revises: a2b3c4d5e6f8
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "b4c5d6e7f8a0"
down_revision = "a2b3c4d5e6f8"
branch_labels = None
depends_on = None

SCHEMA = "gs_fue"
TABLE = "gs_fue_distribution_parameters"


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
    if _table_exists(conn, TABLE):
        return

    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("year_number", sa.Integer(), nullable=False),
        sa.Column("filter_text", sa.Text(), nullable=True),
        sa.Column("e", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("kplus", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("kmin", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("k", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("bkl", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("wname", sa.String(length=255), nullable=True),
        sa.Column("uname", sa.String(length=255), nullable=True),
        sa.Column("toplname", sa.String(length=255), nullable=True),
        sa.Column("dopname", sa.String(length=255), nullable=True),
        sa.Column("byear", sa.Integer(), nullable=True),
        sa.Column("kn", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("knps", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("kngt", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("knpg", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("hnps", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("hngt", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("hnpg", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("numb", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("doptim", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("lim", sa.Integer(), nullable=True),
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
            ["gs_sys.gs_database_versions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        f"ix_{TABLE}_name",
        TABLE,
        ["name"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        f"ix_{TABLE}_year_number",
        TABLE,
        ["year_number"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        f"ix_{TABLE}_byear",
        TABLE,
        ["byear"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        f"ix_{TABLE}_database_version_id",
        TABLE,
        ["database_version_id"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade():
    op.drop_table(TABLE, schema=SCHEMA)

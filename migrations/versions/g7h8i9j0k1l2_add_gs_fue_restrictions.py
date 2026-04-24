# -*- coding: utf-8 -*-
"""Таблица gs_fue_restrictions («Ограничения», Access / Ограничения.xsd).

Revision ID: g7h8i9j0k1l2
Revises: f3e4d5c6b7a9
Create Date: 2026-04-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "g7h8i9j0k1l2"
down_revision = "f3e4d5c6b7a9"
branch_labels = None
depends_on = None

SCHEMA = "gs_fue"
TABLE = "gs_fue_restrictions"


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
        sa.Column("year", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("oes", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("name", sa.String(length=50), nullable=True),
        sa.Column("obl", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("emin", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("emax", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("ecur", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("h", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("ecurdis", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("hdis", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("etp", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("kobl", sa.Numeric(precision=36, scale=16), nullable=True),
        sa.Column("kcur", sa.String(length=50), nullable=True),
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
        f"ix_{TABLE}_database_version_id",
        TABLE,
        ["database_version_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        f"ix_{TABLE}_obl",
        TABLE,
        ["obl"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade():
    op.drop_table(TABLE, schema=SCHEMA)

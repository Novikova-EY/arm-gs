# -*- coding: utf-8 -*-
"""ref_uuid для gs_fue_distribution_parameters (синхронизация во всех версиях БД).

Revision ID: l5m6n7o8p9q0
Revises: k4l5m6n7o8p9
Create Date: 2026-08-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "l5m6n7o8p9q0"
down_revision = "k4l5m6n7o8p9"
branch_labels = None
depends_on = None

SCHEMA = "gs_fue"
TABLE = "gs_fue_distribution_parameters"


def _column_exists(connection, schema, table, column) -> bool:
    row = connection.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :column"
        ),
        {"schema": schema, "table": table, "column": column},
    ).fetchone()
    return row is not None


def _index_exists(connection, schema, index_name) -> bool:
    row = connection.execute(
        text(
            "SELECT 1 FROM pg_indexes "
            "WHERE schemaname = :schema AND indexname = :index_name"
        ),
        {"schema": schema, "index_name": index_name},
    ).fetchone()
    return row is not None


def upgrade():
    conn = op.get_bind()
    if not _column_exists(conn, SCHEMA, TABLE, "ref_uuid"):
        op.add_column(
            TABLE,
            sa.Column("ref_uuid", sa.String(length=36), nullable=True),
            schema=SCHEMA,
        )
    idx = f"ix_{TABLE}_ref_uuid"
    if not _index_exists(conn, SCHEMA, idx):
        op.create_index(idx, TABLE, ["ref_uuid"], unique=False, schema=SCHEMA)

    # Каждой существующей строке — свой ref_uuid (копии по версиям появятся при импорте/сохранении).
    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA}.{TABLE}
            SET ref_uuid = gen_random_uuid()::text
            WHERE ref_uuid IS NULL OR btrim(ref_uuid) = ''
            """
        )
    )


def downgrade():
    conn = op.get_bind()
    idx = f"ix_{TABLE}_ref_uuid"
    if _index_exists(conn, SCHEMA, idx):
        op.drop_index(idx, table_name=TABLE, schema=SCHEMA)
    if _column_exists(conn, SCHEMA, TABLE, "ref_uuid"):
        op.drop_column(TABLE, "ref_uuid", schema=SCHEMA)

# -*- coding: utf-8 -*-
"""Схема gs_ter и таблица перетоков энергоузлов.

Revision ID: t8u9v0w1x2y3
Revises: r1s2t3u4v5x7
Create Date: 2026-05-29
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

revision = "t8u9v0w1x2y3"
down_revision = "r1s2t3u4v5x7"
branch_labels = None
depends_on = None

SCHEMA_TER = "gs_ter"
SCHEMA_REFDATA = "gs_sys"
TABLE = "gs_ter_energy_unit_power_transfers"


def _schema_exists(connection, schema: str) -> bool:
    r = connection.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema"),
        {"schema": schema},
    )
    return r.fetchone() is not None


def _table_exists(connection, schema: str, table: str) -> bool:
    return column_utils.table_exists(connection, schema, table)


def upgrade():
    conn = op.get_bind()
    ref_db_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REFDATA)
    if ref_db_versions is None:
        raise RuntimeError(
            f"Не найдена таблица версий БД в {SCHEMA_REFDATA} "
            "(ожидались gs_sys_database_versions или gs_database_versions как BASE TABLE)"
        )

    energy_units = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_energy_units")
    regional_districts = column_utils.refdata_table_name(
        conn, SCHEMA_REFDATA, "gs_regional_districts"
    )
    if energy_units is None or regional_districts is None:
        raise RuntimeError(
            f"Не найдены справочники энергоузлов или субъектов РФ в {SCHEMA_REFDATA}"
        )

    if not _schema_exists(conn, SCHEMA_TER):
        op.execute(sa.text(f'CREATE SCHEMA "{SCHEMA_TER}"'))

    if _table_exists(conn, SCHEMA_TER, TABLE):
        return

    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_energy_unit", sa.Integer(), nullable=False),
        sa.Column("id_regional_district", sa.Integer(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=True),
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
            ["id_energy_unit"],
            [f"{SCHEMA_REFDATA}.{energy_units}.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["id_regional_district"],
            [f"{SCHEMA_REFDATA}.{regional_districts}.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            [f"{SCHEMA_REFDATA}.{ref_db_versions}.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA_TER,
    )

    op.create_index(
        "ix_gs_ter_eu_pt_energy_unit",
        TABLE,
        ["id_energy_unit"],
        unique=False,
        schema=SCHEMA_TER,
    )
    op.create_index(
        "ix_gs_ter_eu_pt_regional_district",
        TABLE,
        ["id_regional_district"],
        unique=False,
        schema=SCHEMA_TER,
    )
    op.create_index(
        "ix_gs_ter_eu_pt_dbver",
        TABLE,
        ["database_version_id"],
        unique=False,
        schema=SCHEMA_TER,
    )


def downgrade():
    conn = op.get_bind()
    if _table_exists(conn, SCHEMA_TER, TABLE):
        op.execute(sa.text(f'DROP TABLE IF EXISTS "{SCHEMA_TER}"."{TABLE}" CASCADE'))

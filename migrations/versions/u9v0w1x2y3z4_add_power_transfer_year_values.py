# -*- coding: utf-8 -*-
"""Значения перетоков по годам (млн кВтч).

Revision ID: u9v0w1x2y3z4
Revises: t8u9v0w1x2y3
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

revision = "u9v0w1x2y3z4"
down_revision = "t8u9v0w1x2y3"
branch_labels = None
depends_on = None

SCHEMA_TER = "gs_ter"
SCHEMA_REFDATA = "gs_sys"
TABLE = "gs_ter_energy_unit_power_transfer_values"
PARENT = "gs_ter_energy_unit_power_transfers"


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

    if not _table_exists(conn, SCHEMA_TER, PARENT):
        raise RuntimeError(f"Не найдена таблица {SCHEMA_TER}.{PARENT}")

    if _table_exists(conn, SCHEMA_TER, TABLE):
        return

    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_energy_unit_power_transfer", sa.Integer(), nullable=False),
        sa.Column("year_number", sa.Integer(), nullable=False),
        sa.Column("transfer_mln_kvt_ch", sa.Numeric(25, 16), nullable=True),
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
            ["id_energy_unit_power_transfer"],
            [f"{SCHEMA_TER}.{PARENT}.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            [f"{SCHEMA_REFDATA}.{ref_db_versions}.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id_energy_unit_power_transfer",
            "year_number",
            "database_version_id",
            name="uq_gs_ter_eu_pt_val_transfer_year_ver",
        ),
        schema=SCHEMA_TER,
    )
    op.create_index(
        "ix_gs_ter_eu_pt_val_transfer",
        TABLE,
        ["id_energy_unit_power_transfer"],
        unique=False,
        schema=SCHEMA_TER,
    )
    op.create_index(
        "ix_gs_ter_eu_pt_val_year",
        TABLE,
        ["year_number"],
        unique=False,
        schema=SCHEMA_TER,
    )
    op.create_index(
        "ix_gs_ter_eu_pt_val_dbver",
        TABLE,
        ["database_version_id"],
        unique=False,
        schema=SCHEMA_TER,
    )


def downgrade():
    conn = op.get_bind()
    if _table_exists(conn, SCHEMA_TER, TABLE):
        op.execute(sa.text(f'DROP TABLE IF EXISTS "{SCHEMA_TER}"."{TABLE}" CASCADE'))

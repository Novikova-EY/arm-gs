# -*- coding: utf-8 -*-
"""Таблица перетоков ЭЭ между энергосистемами (gs_bem).

Revision ID: f5a6b7c8d9e0
Revises: b1c2d3e4f5b6
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

revision = "f5a6b7c8d9e0"
down_revision = "b1c2d3e4f5b6"
branch_labels = None
depends_on = None

SCHEMA = "gs_bem"
TABLE = "gs_bem_regional_energy_system_transfers"
PERIOD_YEAR = 0


def _schema_exists(connection, schema: str) -> bool:
    r = connection.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema"),
        {"schema": schema},
    )
    return r.fetchone() is not None


def upgrade():
    conn = op.get_bind()
    ref_versions = column_utils.database_versions_physical_table_name(conn, "gs_sys")
    if ref_versions is None:
        raise RuntimeError(
            "Не найдена таблица версий БД в gs_sys "
            "(gs_sys_database_versions или gs_database_versions как BASE TABLE)"
        )
    if not _schema_exists(conn, SCHEMA):
        op.execute(sa.text(f'CREATE SCHEMA "{SCHEMA}"'))
    if column_utils.table_exists(conn, SCHEMA, TABLE):
        return

    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("year_number", sa.Integer(), nullable=True),
        sa.Column(
            "month_number",
            sa.Integer(),
            nullable=False,
            server_default=sa.text(str(PERIOD_YEAR)),
        ),
        sa.Column("from_energy_system_name", sa.String(length=500), nullable=False),
        sa.Column("to_energy_system_name", sa.String(length=500), nullable=False),
        sa.Column("id_from_regional_energy_system", sa.Integer(), nullable=True),
        sa.Column("id_to_regional_energy_system", sa.Integer(), nullable=True),
        sa.Column("id_union_energy_system", sa.Integer(), nullable=True),
        sa.Column("source_oes_name", sa.String(length=500), nullable=True),
        sa.Column("transfer_value", sa.Numeric(25, 16), nullable=True),
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
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )

    op.create_index(
        "ix_ee_transfer_from_res",
        TABLE,
        ["id_from_regional_energy_system"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_ee_transfer_to_res",
        TABLE,
        ["id_to_regional_energy_system"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_ee_transfer_ues",
        TABLE,
        ["id_union_energy_system"],
        schema=SCHEMA,
    )
    op.create_index("ix_ee_transfer_year_number", TABLE, ["year_number"], schema=SCHEMA)
    op.create_index("ix_ee_transfer_month_number", TABLE, ["month_number"], schema=SCHEMA)
    op.create_index(
        "ix_ee_transfer_from_to_year_month",
        TABLE,
        [
            "from_energy_system_name",
            "to_energy_system_name",
            "year_number",
            "month_number",
        ],
        schema=SCHEMA,
    )
    op.execute(
        text(
            f"""
            CREATE UNIQUE INDEX uq_ee_transfer_from_to_ues_year_month_ver
            ON "{SCHEMA}"."{TABLE}" (
                from_energy_system_name,
                to_energy_system_name,
                id_union_energy_system,
                year_number,
                month_number,
                COALESCE(database_version_id, -1)
            )
            """
        )
    )

    years_table = column_utils.refdata_table_name(conn, "gs_sys", "gs_sys_years")
    if years_table:
        op.create_foreign_key(
            "fk_ee_transfer_year_ver",
            TABLE,
            years_table,
            ["year_number", "database_version_id"],
            ["number", "database_version_id"],
            source_schema=SCHEMA,
            referent_schema="gs_sys",
            ondelete="RESTRICT",
        )

    res_table = column_utils.refdata_table_name(conn, "gs_sys", "gs_sys_regional_energy_systems")
    if res_table:
        op.create_foreign_key(
            "fk_ee_transfer_from_res",
            TABLE,
            res_table,
            ["id_from_regional_energy_system"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema="gs_sys",
            ondelete="RESTRICT",
        )
        op.create_foreign_key(
            "fk_ee_transfer_to_res",
            TABLE,
            res_table,
            ["id_to_regional_energy_system"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema="gs_sys",
            ondelete="RESTRICT",
        )

    ues_table = column_utils.refdata_table_name(conn, "gs_sys", "gs_sys_union_energy_systems")
    if ues_table:
        op.create_foreign_key(
            "fk_ee_transfer_ues",
            TABLE,
            ues_table,
            ["id_union_energy_system"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema="gs_sys",
            ondelete="RESTRICT",
        )

    op.create_foreign_key(
        "fk_ee_transfer_db_version",
        TABLE,
        ref_versions,
        ["database_version_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema="gs_sys",
        ondelete="SET NULL",
    )


def downgrade():
    conn = op.get_bind()
    if column_utils.table_exists(conn, SCHEMA, TABLE):
        op.drop_table(TABLE, schema=SCHEMA)

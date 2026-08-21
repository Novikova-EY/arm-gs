# -*- coding: utf-8 -*-
"""Таблицы экспорта ЭЭ и ЭМ (gs_bem).

Revision ID: z6a7b8c9d0e1
Revises: x1y2z3a4b5c6
Create Date: 2026-08-19
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

revision = "z6a7b8c9d0e1"
down_revision = "x1y2z3a4b5c6"
branch_labels = None
depends_on = None

SCHEMA = "gs_bem"
SCHEMA_REFDATA = "gs_sys"
PERIOD_YEAR = 0
EE_TABLE = "gs_bem_regional_energy_system_ee_exports"
EM_TABLE = "gs_bem_regional_energy_system_em_exports"


def _schema_exists(connection, schema: str) -> bool:
    row = connection.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema"),
        {"schema": schema},
    ).fetchone()
    return row is not None


def _create_export_table(conn, table: str, prefix: str) -> None:
    if column_utils.table_exists(conn, SCHEMA, table):
        return

    op.create_table(
        table,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("year_number", sa.Integer(), nullable=True),
        sa.Column(
            "month_number",
            sa.Integer(),
            nullable=False,
            server_default=sa.text(str(PERIOD_YEAR)),
        ),
        sa.Column("id_from_regional_energy_system", sa.Integer(), nullable=True),
        sa.Column("id_from_regional_district", sa.Integer(), nullable=True),
        sa.Column("id_to_regional_energy_system", sa.Integer(), nullable=True),
        sa.Column("id_to_foreign_border_country", sa.Integer(), nullable=True),
        sa.Column("id_to_regional_district", sa.Integer(), nullable=True),
        sa.Column("id_to_energy_unit", sa.Integer(), nullable=True),
        sa.Column("id_union_energy_system", sa.Integer(), nullable=True),
        sa.Column("source_oes_name", sa.String(length=500), nullable=True),
        sa.Column("export_value", sa.Numeric(25, 16), nullable=True),
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
        sa.CheckConstraint(
            "(id_from_regional_energy_system IS NOT NULL AND id_from_regional_district IS NULL) OR "
            "(id_from_regional_energy_system IS NULL AND id_from_regional_district IS NOT NULL)",
            name=f"ck_{prefix}_from_source",
        ),
        sa.CheckConstraint(
            "("
            "id_to_regional_energy_system IS NOT NULL AND "
            "id_to_foreign_border_country IS NULL AND "
            "id_to_regional_district IS NULL AND "
            "id_to_energy_unit IS NULL"
            ") OR ("
            "id_to_regional_energy_system IS NULL AND "
            "id_to_foreign_border_country IS NOT NULL AND "
            "id_to_regional_district IS NULL AND "
            "id_to_energy_unit IS NULL"
            ") OR ("
            "id_to_regional_energy_system IS NULL AND "
            "id_to_foreign_border_country IS NULL AND "
            "id_to_regional_district IS NOT NULL AND "
            "id_to_energy_unit IS NULL"
            ") OR ("
            "id_to_regional_energy_system IS NULL AND "
            "id_to_foreign_border_country IS NULL AND "
            "id_to_regional_district IS NULL AND "
            "id_to_energy_unit IS NOT NULL"
            ")",
            name=f"ck_{prefix}_to_target",
        ),
        schema=SCHEMA,
    )

    for index_name, columns in (
        (f"ix_{prefix}_from_res", ["id_from_regional_energy_system"]),
        (f"ix_{prefix}_from_rd", ["id_from_regional_district"]),
        (f"ix_{prefix}_to_res", ["id_to_regional_energy_system"]),
        (f"ix_{prefix}_to_country", ["id_to_foreign_border_country"]),
        (f"ix_{prefix}_to_rd", ["id_to_regional_district"]),
        (f"ix_{prefix}_to_eu", ["id_to_energy_unit"]),
        (f"ix_{prefix}_ues", ["id_union_energy_system"]),
        (f"ix_{prefix}_year_number", ["year_number"]),
        (f"ix_{prefix}_month_number", ["month_number"]),
        (
            f"ix_{prefix}_from_to_year_month",
            [
                "id_from_regional_energy_system",
                "id_from_regional_district",
                "id_to_regional_energy_system",
                "id_to_foreign_border_country",
                "id_to_regional_district",
                "id_to_energy_unit",
                "year_number",
                "month_number",
            ],
        ),
    ):
        op.create_index(index_name, table, columns, schema=SCHEMA)

    op.execute(
        text(
            f"""
            CREATE UNIQUE INDEX uq_{prefix}_from_to_ues_year_month_ver
            ON "{SCHEMA}"."{table}" (
                COALESCE(id_from_regional_energy_system, -1),
                COALESCE(id_from_regional_district, -1),
                COALESCE(id_to_regional_energy_system, -1),
                COALESCE(id_to_foreign_border_country, -1),
                COALESCE(id_to_regional_district, -1),
                COALESCE(id_to_energy_unit, -1),
                id_union_energy_system,
                year_number,
                month_number,
                COALESCE(database_version_id, -1)
            )
            """
        )
    )

    years_table = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_sys_years")
    if years_table:
        op.create_foreign_key(
            f"fk_{prefix}_year_ver",
            table,
            years_table,
            ["year_number", "database_version_id"],
            ["number", "database_version_id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA_REFDATA,
            ondelete="RESTRICT",
        )

    res_table = column_utils.refdata_table_name(
        conn, SCHEMA_REFDATA, "gs_sys_regional_energy_systems"
    )
    if res_table:
        op.create_foreign_key(
            f"fk_{prefix}_from_res",
            table,
            res_table,
            ["id_from_regional_energy_system"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA_REFDATA,
            ondelete="RESTRICT",
        )
        op.create_foreign_key(
            f"fk_{prefix}_to_res",
            table,
            res_table,
            ["id_to_regional_energy_system"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA_REFDATA,
            ondelete="RESTRICT",
        )

    rd_table = column_utils.refdata_table_name(
        conn, SCHEMA_REFDATA, "gs_sys_regional_districts"
    )
    if rd_table:
        op.create_foreign_key(
            f"fk_{prefix}_from_rd",
            table,
            rd_table,
            ["id_from_regional_district"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA_REFDATA,
            ondelete="RESTRICT",
        )
        op.create_foreign_key(
            f"fk_{prefix}_to_rd",
            table,
            rd_table,
            ["id_to_regional_district"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA_REFDATA,
            ondelete="RESTRICT",
        )

    country_table = column_utils.refdata_table_name(
        conn, SCHEMA_REFDATA, "gs_sys_foreign_border_countries"
    )
    if country_table:
        op.create_foreign_key(
            f"fk_{prefix}_to_country",
            table,
            country_table,
            ["id_to_foreign_border_country"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA_REFDATA,
            ondelete="RESTRICT",
        )

    eu_table = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_sys_energy_units")
    if eu_table:
        op.create_foreign_key(
            f"fk_{prefix}_to_eu",
            table,
            eu_table,
            ["id_to_energy_unit"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA_REFDATA,
            ondelete="RESTRICT",
        )

    ues_table = column_utils.refdata_table_name(
        conn, SCHEMA_REFDATA, "gs_sys_union_energy_systems"
    )
    if ues_table:
        op.create_foreign_key(
            f"fk_{prefix}_ues",
            table,
            ues_table,
            ["id_union_energy_system"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA_REFDATA,
            ondelete="RESTRICT",
        )

    ref_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REFDATA)
    if ref_versions:
        op.create_foreign_key(
            f"fk_{prefix}_db_version",
            table,
            ref_versions,
            ["database_version_id"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA_REFDATA,
            ondelete="SET NULL",
        )


def upgrade():
    conn = op.get_bind()
    if not _schema_exists(conn, SCHEMA):
        op.execute(sa.text(f'CREATE SCHEMA "{SCHEMA}"'))
    _create_export_table(conn, EE_TABLE, "ee_export")
    _create_export_table(conn, EM_TABLE, "em_export")


def downgrade():
    conn = op.get_bind()
    for table in (EM_TABLE, EE_TABLE):
        if column_utils.table_exists(conn, SCHEMA, table):
            op.execute(sa.text(f'DROP TABLE IF EXISTS "{SCHEMA}"."{table}" CASCADE'))

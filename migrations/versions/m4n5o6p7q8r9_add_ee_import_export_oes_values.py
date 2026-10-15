# -*- coding: utf-8 -*-
"""Сохраняемые годовые агрегаты импорта/экспорта ЭЭ по ОЭС.

Revision ID: m4n5o6p7q8r9
Revises: h4y5d6r7o8s9
Create Date: 2026-10-12
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

revision = "m4n5o6p7q8r9"
down_revision = "h4y5d6r7o8s9"
branch_labels = None
depends_on = None

SCHEMA = "gs_bem"
SCHEMA_REFDATA = "gs_sys"
TABLE = "gs_bem_ee_import_export_oes_values"


def _quoted(schema, table):
    return f'"{schema}"."{table}"'


def upgrade():
    conn = op.get_bind()
    if column_utils.table_exists(conn, SCHEMA, TABLE):
        return

    ref_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REFDATA)
    year_table = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_sys_years")
    oes_table = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_sys_union_energy_systems")
    country_table = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_sys_foreign_border_countries")
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_union_energy_system", sa.Integer(), nullable=False),
        sa.Column("id_foreign_border_country", sa.Integer(), nullable=False),
        sa.Column("year_number", sa.Integer(), nullable=False),
        sa.Column("transfer_value", sa.Numeric(25, 16), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index("ix_ee_import_export_oes_year", TABLE, ["year_number"], schema=SCHEMA)
    op.create_index("ix_ee_import_export_oes_ues", TABLE, ["id_union_energy_system"], schema=SCHEMA)
    op.create_index("ix_ee_import_export_oes_country", TABLE, ["id_foreign_border_country"], schema=SCHEMA)
    op.execute(text(
        f'CREATE UNIQUE INDEX uq_ee_import_export_oes_country_year_ver '
        f'ON {_quoted(SCHEMA, TABLE)} '
        '(id_union_energy_system, id_foreign_border_country, year_number, '
        'COALESCE(database_version_id, -1))'
    ))

    for name, target_table, local_cols, remote_cols, ondelete in (
        ("fk_ee_import_export_oes_ues", oes_table, ["id_union_energy_system"], ["id"], "RESTRICT"),
        ("fk_ee_import_export_oes_country", country_table, ["id_foreign_border_country"], ["id"], "RESTRICT"),
        ("fk_ee_import_export_oes_year_ver", year_table,
         ["year_number", "database_version_id"], ["number", "database_version_id"], "RESTRICT"),
        ("fk_ee_import_export_oes_db_version", ref_versions, ["database_version_id"], ["id"], "SET NULL"),
    ):
        if target_table:
            op.create_foreign_key(
                name, TABLE, target_table, local_cols, remote_cols,
                source_schema=SCHEMA, referent_schema=SCHEMA_REFDATA, ondelete=ondelete,
            )

    transfers = "gs_bem_regional_energy_system_transfers"
    res = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_sys_regional_energy_systems")
    rd_res = column_utils.refdata_table_name(
        conn, SCHEMA_REFDATA, "gs_sys_regional_district_regional_energy_system"
    )
    if column_utils.table_exists(conn, SCHEMA, transfers) and res:
        source_ues = f"COALESCE(t.id_union_energy_system, src.id_union_energy_system)"
        joins = f"LEFT JOIN {_quoted(SCHEMA_REFDATA, res)} src " \
                "ON src.id = t.id_from_regional_energy_system"
        if rd_res:
            joins += (
                f" LEFT JOIN (SELECT regional_district_id, MIN(regional_energy_system_id) AS res_id "
                f"FROM {_quoted(SCHEMA_REFDATA, rd_res)} GROUP BY regional_district_id) rd "
                "ON rd.regional_district_id = t.id_from_regional_district "
                f"LEFT JOIN {_quoted(SCHEMA_REFDATA, res)} rd_src ON rd_src.id = rd.res_id"
            )
            source_ues = "COALESCE(t.id_union_energy_system, src.id_union_energy_system, rd_src.id_union_energy_system)"
        op.execute(text(
            f"INSERT INTO {_quoted(SCHEMA, TABLE)} "
            "(id_union_energy_system, id_foreign_border_country, year_number, transfer_value, database_version_id) "
            f"SELECT {source_ues}, t.id_to_foreign_border_country, t.year_number, SUM(t.transfer_value), t.database_version_id "
            f"FROM {_quoted(SCHEMA, transfers)} t {joins} "
            "WHERE t.month_number = 0 AND t.id_to_foreign_border_country IS NOT NULL "
            f"AND {source_ues} IS NOT NULL "
            f"GROUP BY {source_ues}, t.id_to_foreign_border_country, t.year_number, t.database_version_id"
        ))


def downgrade():
    conn = op.get_bind()
    if column_utils.table_exists(conn, SCHEMA, TABLE):
        op.execute(text(f'DROP TABLE IF EXISTS {_quoted(SCHEMA, TABLE)} CASCADE'))

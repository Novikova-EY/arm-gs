# -*- coding: utf-8 -*-
"""Перетоки ЭЭ: субъект РФ (источник/получатель) и энергорайон (получатель).

Revision ID: i8j9k0l1m2n3
Revises: h7i8j9k0l1m2
Create Date: 2026-06-10
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

revision = "i8j9k0l1m2n3"
down_revision = "h7i8j9k0l1m2"
branch_labels = None
depends_on = None

SCHEMA = "gs_bem"
TABLE = "gs_bem_regional_energy_system_transfers"


def upgrade():
    conn = op.get_bind()
    if not column_utils.table_exists(conn, SCHEMA, TABLE):
        return

    if column_utils.index_exists(conn, SCHEMA, "uq_ee_transfer_from_to_ues_year_month_ver"):
        op.drop_index("uq_ee_transfer_from_to_ues_year_month_ver", table_name=TABLE, schema=SCHEMA)
    if column_utils.index_exists(conn, SCHEMA, "ix_ee_transfer_from_to_year_month"):
        op.drop_index("ix_ee_transfer_from_to_year_month", table_name=TABLE, schema=SCHEMA)
    if column_utils.constraint_exists(conn, SCHEMA, "ck_ee_transfer_to_target"):
        op.drop_constraint("ck_ee_transfer_to_target", TABLE, schema=SCHEMA, type_="check")

    rd_table = column_utils.refdata_table_name(conn, "gs_sys", "gs_sys_regional_districts")
    eu_table = column_utils.refdata_table_name(conn, "gs_sys", "gs_sys_energy_units")

    if not column_utils.table_has_column(conn, SCHEMA, TABLE, "id_from_regional_district"):
        op.add_column(
            TABLE,
            sa.Column("id_from_regional_district", sa.Integer(), nullable=True),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_ee_transfer_from_rd",
            TABLE,
            ["id_from_regional_district"],
            schema=SCHEMA,
        )
    if not column_utils.table_has_column(conn, SCHEMA, TABLE, "id_to_regional_district"):
        op.add_column(
            TABLE,
            sa.Column("id_to_regional_district", sa.Integer(), nullable=True),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_ee_transfer_to_rd",
            TABLE,
            ["id_to_regional_district"],
            schema=SCHEMA,
        )
    if not column_utils.table_has_column(conn, SCHEMA, TABLE, "id_to_energy_unit"):
        op.add_column(
            TABLE,
            sa.Column("id_to_energy_unit", sa.Integer(), nullable=True),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_ee_transfer_to_eu",
            TABLE,
            ["id_to_energy_unit"],
            schema=SCHEMA,
        )

    if rd_table and not column_utils.constraint_exists(conn, SCHEMA, "fk_ee_transfer_from_rd"):
        op.create_foreign_key(
            "fk_ee_transfer_from_rd",
            TABLE,
            rd_table,
            ["id_from_regional_district"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema="gs_sys",
            ondelete="RESTRICT",
        )
    if rd_table and not column_utils.constraint_exists(conn, SCHEMA, "fk_ee_transfer_to_rd"):
        op.create_foreign_key(
            "fk_ee_transfer_to_rd",
            TABLE,
            rd_table,
            ["id_to_regional_district"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema="gs_sys",
            ondelete="RESTRICT",
        )
    if eu_table and not column_utils.constraint_exists(conn, SCHEMA, "fk_ee_transfer_to_eu"):
        op.create_foreign_key(
            "fk_ee_transfer_to_eu",
            TABLE,
            eu_table,
            ["id_to_energy_unit"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema="gs_sys",
            ondelete="RESTRICT",
        )

    op.alter_column(
        TABLE,
        "id_from_regional_energy_system",
        existing_type=sa.Integer(),
        nullable=True,
        schema=SCHEMA,
    )

    if not column_utils.constraint_exists(conn, SCHEMA, "ck_ee_transfer_from_source"):
        op.create_check_constraint(
            "ck_ee_transfer_from_source",
            TABLE,
            "(id_from_regional_energy_system IS NOT NULL AND id_from_regional_district IS NULL) OR "
            "(id_from_regional_energy_system IS NULL AND id_from_regional_district IS NOT NULL)",
            schema=SCHEMA,
        )
    if not column_utils.constraint_exists(conn, SCHEMA, "ck_ee_transfer_to_target"):
        op.create_check_constraint(
            "ck_ee_transfer_to_target",
            TABLE,
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
            schema=SCHEMA,
        )

    op.create_index(
        "ix_ee_transfer_from_to_year_month",
        TABLE,
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
        schema=SCHEMA,
    )
    op.execute(
        text(
            f"""
            CREATE UNIQUE INDEX uq_ee_transfer_from_to_ues_year_month_ver
            ON "{SCHEMA}"."{TABLE}" (
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


def downgrade():
    conn = op.get_bind()
    if not column_utils.table_exists(conn, SCHEMA, TABLE):
        return

    if column_utils.index_exists(conn, SCHEMA, "uq_ee_transfer_from_to_ues_year_month_ver"):
        op.drop_index("uq_ee_transfer_from_to_ues_year_month_ver", table_name=TABLE, schema=SCHEMA)
    if column_utils.index_exists(conn, SCHEMA, "ix_ee_transfer_from_to_year_month"):
        op.drop_index("ix_ee_transfer_from_to_year_month", table_name=TABLE, schema=SCHEMA)
    if column_utils.constraint_exists(conn, SCHEMA, "ck_ee_transfer_from_source"):
        op.drop_constraint("ck_ee_transfer_from_source", TABLE, schema=SCHEMA, type_="check")
    if column_utils.constraint_exists(conn, SCHEMA, "ck_ee_transfer_to_target"):
        op.drop_constraint("ck_ee_transfer_to_target", TABLE, schema=SCHEMA, type_="check")

    conn.execute(
        text(
            f"""
            DELETE FROM "{SCHEMA}"."{TABLE}"
            WHERE id_from_regional_district IS NOT NULL
               OR id_to_regional_district IS NOT NULL
               OR id_to_energy_unit IS NOT NULL
            """
        )
    )

    if column_utils.constraint_exists(conn, SCHEMA, "fk_ee_transfer_to_eu"):
        op.drop_constraint("fk_ee_transfer_to_eu", TABLE, schema=SCHEMA, type_="foreignkey")
    if column_utils.constraint_exists(conn, SCHEMA, "fk_ee_transfer_to_rd"):
        op.drop_constraint("fk_ee_transfer_to_rd", TABLE, schema=SCHEMA, type_="foreignkey")
    if column_utils.constraint_exists(conn, SCHEMA, "fk_ee_transfer_from_rd"):
        op.drop_constraint("fk_ee_transfer_from_rd", TABLE, schema=SCHEMA, type_="foreignkey")

    for idx in ("ix_ee_transfer_to_eu", "ix_ee_transfer_to_rd", "ix_ee_transfer_from_rd"):
        if column_utils.index_exists(conn, SCHEMA, idx):
            op.drop_index(idx, table_name=TABLE, schema=SCHEMA)

    for col in ("id_to_energy_unit", "id_to_regional_district", "id_from_regional_district"):
        if column_utils.table_has_column(conn, SCHEMA, TABLE, col):
            op.drop_column(TABLE, col, schema=SCHEMA)

    op.alter_column(
        TABLE,
        "id_from_regional_energy_system",
        existing_type=sa.Integer(),
        nullable=False,
        schema=SCHEMA,
    )

    if not column_utils.constraint_exists(conn, SCHEMA, "ck_ee_transfer_to_target"):
        op.create_check_constraint(
            "ck_ee_transfer_to_target",
            TABLE,
            "(id_to_regional_energy_system IS NOT NULL AND id_to_foreign_border_country IS NULL) OR "
            "(id_to_regional_energy_system IS NULL AND id_to_foreign_border_country IS NOT NULL)",
            schema=SCHEMA,
        )

    op.create_index(
        "ix_ee_transfer_from_to_year_month",
        TABLE,
        [
            "id_from_regional_energy_system",
            "id_to_regional_energy_system",
            "id_to_foreign_border_country",
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
                id_from_regional_energy_system,
                COALESCE(id_to_regional_energy_system, -1),
                COALESCE(id_to_foreign_border_country, -1),
                id_union_energy_system,
                year_number,
                month_number,
                COALESCE(database_version_id, -1)
            )
            """
        )
    )

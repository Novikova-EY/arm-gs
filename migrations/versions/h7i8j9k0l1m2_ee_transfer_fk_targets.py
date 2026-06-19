# -*- coding: utf-8 -*-
"""Перетоки ЭЭ: FK на РЭС (из) и РЭС/зарубежную страну (в), удаление текстовых имён.

Revision ID: h7i8j9k0l1m2
Revises: g6h7i8j9k0l1
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

revision = "h7i8j9k0l1m2"
down_revision = "g6h7i8j9k0l1"
branch_labels = None
depends_on = None

SCHEMA = "gs_bem"
TABLE = "gs_bem_regional_energy_system_transfers"


def _backfill_fk_from_names(conn) -> None:
    if not column_utils.table_exists(conn, SCHEMA, TABLE):
        return
    if not column_utils.table_has_column(conn, SCHEMA, TABLE, "from_energy_system_name"):
        return

    res_table = column_utils.refdata_table_name(conn, "gs_sys", "gs_sys_regional_energy_systems")
    country_table = column_utils.refdata_table_name(conn, "gs_sys", "gs_sys_foreign_border_countries")
    if not res_table:
        return

    conn.execute(
        text(
            f"""
            UPDATE "{SCHEMA}"."{TABLE}" AS t
            SET id_from_regional_energy_system = r.id
            FROM "gs_sys"."{res_table}" AS r
            WHERE t.id_from_regional_energy_system IS NULL
              AND lower(trim(t.from_energy_system_name)) IN (
                  lower(trim(r.name)),
                  lower(trim(r.name_full)),
                  lower(trim(r.name_rp))
              )
              AND r.database_version_id IS NOT DISTINCT FROM t.database_version_id
            """
        )
    )

    conn.execute(
        text(
            f"""
            UPDATE "{SCHEMA}"."{TABLE}" AS t
            SET id_to_regional_energy_system = r.id
            FROM "gs_sys"."{res_table}" AS r
            WHERE t.id_to_regional_energy_system IS NULL
              AND t.id_to_foreign_border_country IS NULL
              AND lower(trim(t.to_energy_system_name)) IN (
                  lower(trim(r.name)),
                  lower(trim(r.name_full)),
                  lower(trim(r.name_rp))
              )
              AND r.database_version_id IS NOT DISTINCT FROM t.database_version_id
            """
        )
    )

    if country_table:
        conn.execute(
            text(
                f"""
                UPDATE "{SCHEMA}"."{TABLE}" AS t
                SET id_to_foreign_border_country = c.id
                FROM "gs_sys"."{country_table}" AS c
                WHERE t.id_to_regional_energy_system IS NULL
                  AND t.id_to_foreign_border_country IS NULL
                  AND lower(trim(t.to_energy_system_name)) = lower(trim(c.name))
                  AND c.database_version_id IS NOT DISTINCT FROM t.database_version_id
                """
            )
        )

    conn.execute(
        text(
            f"""
            DELETE FROM "{SCHEMA}"."{TABLE}"
            WHERE id_from_regional_energy_system IS NULL
               OR (
                    id_to_regional_energy_system IS NULL
                    AND id_to_foreign_border_country IS NULL
                  )
            """
        )
    )


def upgrade():
    conn = op.get_bind()
    if not column_utils.table_exists(conn, SCHEMA, TABLE):
        return

    if not column_utils.table_has_column(conn, SCHEMA, TABLE, "id_to_foreign_border_country"):
        op.add_column(
            TABLE,
            sa.Column("id_to_foreign_border_country", sa.Integer(), nullable=True),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_ee_transfer_to_country",
            TABLE,
            ["id_to_foreign_border_country"],
            schema=SCHEMA,
        )

    _backfill_fk_from_names(conn)

    if column_utils.index_exists(conn, SCHEMA, "uq_ee_transfer_from_to_ues_year_month_ver"):
        op.drop_index("uq_ee_transfer_from_to_ues_year_month_ver", table_name=TABLE, schema=SCHEMA)
    if column_utils.index_exists(conn, SCHEMA, "ix_ee_transfer_from_to_year_month"):
        op.drop_index("ix_ee_transfer_from_to_year_month", table_name=TABLE, schema=SCHEMA)

    if column_utils.table_has_column(conn, SCHEMA, TABLE, "from_energy_system_name"):
        op.drop_column(TABLE, "from_energy_system_name", schema=SCHEMA)
    if column_utils.table_has_column(conn, SCHEMA, TABLE, "to_energy_system_name"):
        op.drop_column(TABLE, "to_energy_system_name", schema=SCHEMA)

    op.alter_column(
        TABLE,
        "id_from_regional_energy_system",
        existing_type=sa.Integer(),
        nullable=False,
        schema=SCHEMA,
    )

    country_table = column_utils.refdata_table_name(conn, "gs_sys", "gs_sys_foreign_border_countries")
    if country_table and not column_utils.constraint_exists(conn, SCHEMA, "fk_ee_transfer_to_country"):
        op.create_foreign_key(
            "fk_ee_transfer_to_country",
            TABLE,
            country_table,
            ["id_to_foreign_border_country"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema="gs_sys",
            ondelete="RESTRICT",
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


def downgrade():
    conn = op.get_bind()
    if not column_utils.table_exists(conn, SCHEMA, TABLE):
        return

    if column_utils.index_exists(conn, SCHEMA, "uq_ee_transfer_from_to_ues_year_month_ver"):
        op.drop_index("uq_ee_transfer_from_to_ues_year_month_ver", table_name=TABLE, schema=SCHEMA)
    if column_utils.index_exists(conn, SCHEMA, "ix_ee_transfer_from_to_year_month"):
        op.drop_index("ix_ee_transfer_from_to_year_month", table_name=TABLE, schema=SCHEMA)
    if column_utils.constraint_exists(conn, SCHEMA, "ck_ee_transfer_to_target"):
        op.drop_constraint("ck_ee_transfer_to_target", TABLE, schema=SCHEMA, type_="check")
    if column_utils.constraint_exists(conn, SCHEMA, "fk_ee_transfer_to_country"):
        op.drop_constraint("fk_ee_transfer_to_country", TABLE, schema=SCHEMA, type_="foreignkey")

    if not column_utils.table_has_column(conn, SCHEMA, TABLE, "from_energy_system_name"):
        op.add_column(
            TABLE,
            sa.Column("from_energy_system_name", sa.String(length=500), nullable=True),
            schema=SCHEMA,
        )
    if not column_utils.table_has_column(conn, SCHEMA, TABLE, "to_energy_system_name"):
        op.add_column(
            TABLE,
            sa.Column("to_energy_system_name", sa.String(length=500), nullable=True),
            schema=SCHEMA,
        )

    res_table = column_utils.refdata_table_name(conn, "gs_sys", "gs_sys_regional_energy_systems")
    if res_table:
        conn.execute(
            text(
                f"""
                UPDATE "{SCHEMA}"."{TABLE}" AS t
                SET from_energy_system_name = r.name_full
                FROM "gs_sys"."{res_table}" AS r
                WHERE t.id_from_regional_energy_system = r.id
                """
            )
        )
        conn.execute(
            text(
                f"""
                UPDATE "{SCHEMA}"."{TABLE}" AS t
                SET to_energy_system_name = COALESCE(r.name_full, c.name)
                FROM "gs_sys"."{res_table}" AS r
                FULL OUTER JOIN "gs_sys"."gs_sys_foreign_border_countries" AS c
                    ON FALSE
                WHERE t.id_to_regional_energy_system = r.id
                   OR t.id_to_foreign_border_country = c.id
                """
            )
        )

    op.alter_column(
        TABLE,
        "id_from_regional_energy_system",
        existing_type=sa.Integer(),
        nullable=True,
        schema=SCHEMA,
    )

    if column_utils.table_has_column(conn, SCHEMA, TABLE, "id_to_foreign_border_country"):
        if column_utils.index_exists(conn, SCHEMA, "ix_ee_transfer_to_country"):
            op.drop_index("ix_ee_transfer_to_country", table_name=TABLE, schema=SCHEMA)
        op.drop_column(TABLE, "id_to_foreign_border_country", schema=SCHEMA)

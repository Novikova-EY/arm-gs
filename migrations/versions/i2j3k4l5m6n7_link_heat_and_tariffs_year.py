# -*- coding: utf-8 -*-
"""FK year_number+database_version_id → Year для heat_and_tariffs.

Revision ID: i2j3k4l5m6n7
Revises: h1e2a3t4s5t6
Create Date: 2026-07-27
"""
from alembic import op
from sqlalchemy import text


revision = "i2j3k4l5m6n7"
down_revision = "h1e2a3t4s5t6"
branch_labels = None
depends_on = None

SCHEMA = "gs_fue"
TABLE = "gs_fue_equipment_group_heat_and_tariffs"
FK_YEAR = "fk_equipment_group_heat_and_tariffs_year_ver"


def _fk_exists(connection) -> bool:
    row = connection.execute(
        text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE table_schema = :schema AND table_name = :table "
            "AND constraint_name = :name AND constraint_type = 'FOREIGN KEY'"
        ),
        {"schema": SCHEMA, "table": TABLE, "name": FK_YEAR},
    ).fetchone()
    return row is not None


def upgrade():
    conn = op.get_bind()

    if not _fk_exists(conn):
        orphans = conn.execute(
            text(
                f"""
                SELECT COUNT(*) FROM {SCHEMA}.{TABLE} t
                WHERE t.year_number IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM gs_sys.gs_sys_years y
                    WHERE y.number = t.year_number
                      AND y.database_version_id IS NOT DISTINCT FROM t.database_version_id
                  )
                """
            )
        ).scalar()
        if orphans:
            raise RuntimeError(
                f"Нельзя добавить FK на Year: {orphans} строк в {TABLE} "
                "без пары (year_number, database_version_id) в gs_sys_years."
            )
        op.create_foreign_key(
            FK_YEAR,
            TABLE,
            "gs_sys_years",
            ["year_number", "database_version_id"],
            ["number", "database_version_id"],
            source_schema=SCHEMA,
            referent_schema="gs_sys",
            ondelete="RESTRICT",
        )


def downgrade():
    conn = op.get_bind()
    if _fk_exists(conn):
        op.drop_constraint(FK_YEAR, TABLE, schema=SCHEMA, type_="foreignkey")

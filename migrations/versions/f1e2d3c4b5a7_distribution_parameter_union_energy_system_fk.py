# -*- coding: utf-8 -*-
"""Параметры распределения: name -> FK на gs_union_energy_systems.

Revision ID: f1e2d3c4b5a7
Revises: d6e7f8a9b0c2
Create Date: 2026-04-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "f1e2d3c4b5a7"
down_revision = "d6e7f8a9b0c2"
branch_labels = None
depends_on = None

SCHEMA_FUEL = "gs_fue"
SCHEMA_REFDATA = "gs_sys"
TABLE = "gs_fue_distribution_parameters"
COL = "id_union_energy_system"


def _column_exists(connection, column: str) -> bool:
    r = connection.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :col"
        ),
        {"schema": SCHEMA_FUEL, "table": TABLE, "col": column},
    )
    return r.fetchone() is not None


def upgrade():
    conn = op.get_bind()
    if not _column_exists(conn, COL):
        op.add_column(
            TABLE,
            sa.Column(COL, sa.Integer(), nullable=True),
            schema=SCHEMA_FUEL,
        )
        op.create_foreign_key(
            f"fk_{TABLE}_{COL}",
            TABLE,
            "gs_union_energy_systems",
            [COL],
            ["id"],
            source_schema=SCHEMA_FUEL,
            referent_schema=SCHEMA_REFDATA,
            ondelete="SET NULL",
        )
        op.create_index(
            f"ix_{TABLE}_{COL}",
            TABLE,
            [COL],
            unique=False,
            schema=SCHEMA_FUEL,
        )

    if _column_exists(conn, "name"):
        # Перенос: совпадение текстового name с UnionEnergySystem.name и версии БД
        conn.execute(
            text(
                f"""
                UPDATE {SCHEMA_FUEL}.{TABLE} AS dp
                SET {COL} = ues.id
                FROM {SCHEMA_REFDATA}.gs_union_energy_systems AS ues
                WHERE dp.name IS NOT NULL
                  AND TRIM(dp.name) = TRIM(ues.name)
                  AND (
                    (dp.database_version_id IS NULL AND ues.database_version_id IS NULL)
                    OR (dp.database_version_id = ues.database_version_id)
                  )
                """
            )
        )
        op.drop_index(f"ix_{TABLE}_name", table_name=TABLE, schema=SCHEMA_FUEL)
        op.drop_column(TABLE, "name", schema=SCHEMA_FUEL)


def downgrade():
    op.add_column(
        TABLE,
        sa.Column("name", sa.String(length=255), nullable=True),
        schema=SCHEMA_FUEL,
    )
    conn = op.get_bind()
    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA_FUEL}.{TABLE} AS dp
            SET name = ues.name
            FROM {SCHEMA_REFDATA}.gs_union_energy_systems AS ues
            WHERE dp.{COL} = ues.id
            """
        )
    )
    op.drop_constraint(
        f"fk_{TABLE}_{COL}",
        TABLE,
        schema=SCHEMA_FUEL,
        type_="foreignkey",
    )
    op.drop_index(f"ix_{TABLE}_{COL}", table_name=TABLE, schema=SCHEMA_FUEL)
    op.drop_column(TABLE, COL, schema=SCHEMA_FUEL)
    op.create_index(
        f"ix_{TABLE}_name",
        TABLE,
        ["name"],
        unique=False,
        schema=SCHEMA_FUEL,
    )

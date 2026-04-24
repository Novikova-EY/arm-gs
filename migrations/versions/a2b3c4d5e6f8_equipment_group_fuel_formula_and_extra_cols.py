# -*- coding: utf-8 -*-
"""equipment_group_fuel_formula table; extra fuel param sosv, luch, tal

Revision ID: a2b3c4d5e6f8
Revises: g2h3i4j5k6l7
Create Date: 2026-03-31

Таблица формул топлива (EquipmentGroupFuelFormula) и колонки детализации углей
в gs_fue_equipment_group_extra_fuel_param.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "a2b3c4d5e6f8"
down_revision = "g2h3i4j5k6l7"
branch_labels = None
depends_on = None

SCHEMA = "gs_fue"
TABLE_FORMULA = "gs_fue_equipment_group_fuel_formula"
TABLE_EXTRA = "gs_fue_equipment_group_extra_fuel_param"


def _table_exists(connection, table: str) -> bool:
    result = connection.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :table"
        ),
        {"schema": SCHEMA, "table": table},
    )
    return result.fetchone() is not None


def _column_exists(connection, table: str, column: str) -> bool:
    result = connection.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :col"
        ),
        {"schema": SCHEMA, "table": table, "col": column},
    )
    return result.fetchone() is not None


def upgrade():
    conn = op.get_bind()

    if not _table_exists(conn, TABLE_FORMULA):
        op.create_table(
            TABLE_FORMULA,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("equipment_group_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=512), nullable=True),
            sa.Column("year_number", sa.Integer(), nullable=False),
            sa.Column("variant_number", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("numb1120", sa.Integer(), nullable=True),
            sa.Column("numb1", sa.Numeric(precision=36, scale=16), nullable=True),
            sa.Column("formtxt", sa.Text(), nullable=True),
            sa.Column("database_version_id", sa.Integer(), nullable=True),
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
            sa.ForeignKeyConstraint(
                ["database_version_id"],
                ["gs_sys.gs_database_versions.id"],
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["equipment_group_id"],
                ["gs_fue.gs_fue_equipment_groups.id"],
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "equipment_group_id",
                "year_number",
                "variant_number",
                "database_version_id",
                name="uq_eq_group_fuel_formula_group_year_variant_version",
            ),
            schema=SCHEMA,
        )
        op.create_index(
            f"ix_{TABLE_FORMULA}_equipment_group_id",
            TABLE_FORMULA,
            ["equipment_group_id"],
            unique=False,
            schema=SCHEMA,
        )
        op.create_index(
            f"ix_{TABLE_FORMULA}_year_number",
            TABLE_FORMULA,
            ["year_number"],
            unique=False,
            schema=SCHEMA,
        )
        op.create_index(
            f"ix_{TABLE_FORMULA}_variant_number",
            TABLE_FORMULA,
            ["variant_number"],
            unique=False,
            schema=SCHEMA,
        )
        op.create_index(
            f"ix_{TABLE_FORMULA}_numb1120",
            TABLE_FORMULA,
            ["numb1120"],
            unique=False,
            schema=SCHEMA,
        )
        op.create_index(
            f"ix_{TABLE_FORMULA}_numb1",
            TABLE_FORMULA,
            ["numb1"],
            unique=False,
            schema=SCHEMA,
        )
        op.create_index(
            f"ix_{TABLE_FORMULA}_database_version_id",
            TABLE_FORMULA,
            ["database_version_id"],
            unique=False,
            schema=SCHEMA,
        )

    for col in ("sosv", "luch", "tal"):
        if _table_exists(conn, TABLE_EXTRA) and not _column_exists(conn, TABLE_EXTRA, col):
            op.add_column(
                TABLE_EXTRA,
                sa.Column(col, sa.Numeric(precision=36, scale=16), nullable=True),
                schema=SCHEMA,
            )


def downgrade():
    conn = op.get_bind()
    for col in ("tal", "luch", "sosv"):
        if _table_exists(conn, TABLE_EXTRA) and _column_exists(conn, TABLE_EXTRA, col):
            op.drop_column(TABLE_EXTRA, col, schema=SCHEMA)

    if _table_exists(conn, TABLE_FORMULA):
        op.drop_table(TABLE_FORMULA, schema=SCHEMA)

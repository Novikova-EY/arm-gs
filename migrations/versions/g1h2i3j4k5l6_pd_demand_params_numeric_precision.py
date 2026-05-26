# -*- coding: utf-8 -*-
"""gs_pd: точность Numeric для параметров нагрузки — МВт (3), coeff_k (6).

Revision ID: g1h2i3j4k5l6
Revises: f0e1d2c3b4a5
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "g1h2i3j4k5l6"
down_revision = "f0e1d2c3b4a5"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
OLD_TYPE = sa.Numeric(precision=25, scale=16)
MW_TYPE = sa.Numeric(precision=25, scale=3)
COEFF_K_TYPE = sa.Numeric(precision=25, scale=6)


def _target_scale(column_name: str) -> int | None:
    if column_name.startswith("coeff_k_"):
        return 6
    if column_name == "max_power_consumption_mw":
        return 3
    if column_name.startswith("combined_on_"):
        return 3
    if column_name in ("calculated_max_power_mw", "calculated_combined_on_ees_mw"):
        return 3
    return None


def _demand_param_numeric_columns(connection, *, current_scale: int) -> list[tuple[str, str, int]]:
    rows = connection.execute(
        text(
            """
            SELECT table_name, column_name, numeric_scale
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name LIKE 'gs_pd_%_demand_params'
              AND data_type = 'numeric'
              AND numeric_scale = :scale
            ORDER BY table_name, column_name
            """
        ),
        {"schema": SCHEMA_PD, "scale": current_scale},
    ).fetchall()
    result: list[tuple[str, str, int]] = []
    for table_name, column_name, _scale in rows:
        target = _target_scale(column_name)
        if target is not None:
            result.append((table_name, column_name, target))
    return result


def _alter_column_type(table: str, column: str, scale: int, *, reverse: bool = False) -> None:
    if reverse:
        existing_type = MW_TYPE if scale == 3 else COEFF_K_TYPE
        new_type = OLD_TYPE
        using_scale = 16
    else:
        existing_type = OLD_TYPE
        new_type = MW_TYPE if scale == 3 else COEFF_K_TYPE
        using_scale = scale

    op.alter_column(
        table,
        column,
        existing_type=existing_type,
        type_=new_type,
        existing_nullable=True,
        schema=SCHEMA_PD,
        postgresql_using=f"ROUND({column}::numeric, {using_scale})",
    )


def upgrade():
    conn = op.get_bind()
    for table, column, scale in _demand_param_numeric_columns(conn, current_scale=16):
        _alter_column_type(table, column, scale)


def downgrade():
    conn = op.get_bind()
    columns_to_revert: list[tuple[str, str, int]] = []
    for current_scale in (3, 6):
        columns_to_revert.extend(
            _demand_param_numeric_columns(conn, current_scale=current_scale)
        )
    for table, column, scale in reversed(columns_to_revert):
        _alter_column_type(table, column, scale, reverse=True)

"""ges_tep_average_multiyear_generation

Revision ID: c4d5e6f7a8b0
Revises: b3c4d5e6f7a9
Create Date: 2026-03-30

Среднемноголетняя выработка электроэнергии, млрд кВт·ч в ges_tep_source_project_indicators.
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402


revision = "c4d5e6f7a8b0"
down_revision = "b3c4d5e6f7a9"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE_TEP = "ges_tep_source_project_indicators"


def upgrade():
    conn = op.get_bind()
    table_tep = column_utils.ges_tep_source_project_indicators_table_name(conn, SCHEMA_GEN)
    if table_tep is not None and not column_utils.table_has_column(
        conn, SCHEMA_GEN, table_tep, "generation_average_multiyear_billion_kwh"
    ):
        op.add_column(
            table_tep,
            sa.Column(
                "generation_average_multiyear_billion_kwh",
                sa.String(length=100),
                nullable=True,
            ),
            schema=SCHEMA_GEN,
        )


def downgrade():
    conn = op.get_bind()
    table_tep = column_utils.ges_tep_source_project_indicators_table_name(conn, SCHEMA_GEN)
    if table_tep is not None and column_utils.table_has_column(
        conn, SCHEMA_GEN, table_tep, "generation_average_multiyear_billion_kwh"
    ):
        op.drop_column(
            table_tep,
            "generation_average_multiyear_billion_kwh",
            schema=SCHEMA_GEN,
        )

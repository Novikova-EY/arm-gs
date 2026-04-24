# -*- coding: utf-8 -*-
"""gs_gen: date_modernization_expected -> date_modernization_power_change_expected, add date_modernization_no_power_change_expected

Revision ID: r1s2t3u4v5w6
Revises: c7d8e9f0a1b2
Create Date: 2026-04-24
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

revision = "r1s2t3u4v5w6"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None

SCHEMA = "gs_gen"
OLD_COL = "date_modernization_expected"
NEW_POWER_COL = "date_modernization_power_change_expected"
NO_POWER_COL = "date_modernization_no_power_change_expected"
MACHINES_OLD_MODERN_INDEX = "ix_machine_date_modernization_expected"
MACHINES_POWER_INDEX = "ix_machine_date_modernization_power_change_expected"
MACHINES_NO_POWER_INDEX = "ix_machine_date_modernization_no_power_change_expected"


def _rename_column(table: str, old: str, new: str) -> None:
    op.execute(
        text(
            f'ALTER TABLE "{SCHEMA}"."{table}" '
            f'RENAME COLUMN "{old}" TO "{new}"'
        )
    )


def upgrade():
    conn = op.get_bind()

    if column_utils.table_has_column(conn, SCHEMA, "machines", OLD_COL) and not column_utils.table_has_column(
        conn, SCHEMA, "machines", NEW_POWER_COL
    ):
        if column_utils.index_exists(conn, SCHEMA, MACHINES_OLD_MODERN_INDEX):
            op.drop_index(
                MACHINES_OLD_MODERN_INDEX,
                table_name="machines",
                schema=SCHEMA,
            )
        _rename_column("machines", OLD_COL, NEW_POWER_COL)
        if not column_utils.index_exists(conn, SCHEMA, MACHINES_POWER_INDEX):
            op.create_index(
                MACHINES_POWER_INDEX,
                "machines",
                [NEW_POWER_COL],
                unique=False,
                schema=SCHEMA,
            )
    else:
        if (
            column_utils.table_has_column(conn, SCHEMA, "machines", NEW_POWER_COL)
            and not column_utils.index_exists(conn, SCHEMA, MACHINES_POWER_INDEX)
        ):
            op.create_index(
                MACHINES_POWER_INDEX,
                "machines",
                [NEW_POWER_COL],
                unique=False,
                schema=SCHEMA,
            )

    if column_utils.table_has_column(
        conn, SCHEMA, "pgu_machines", OLD_COL
    ) and not column_utils.table_has_column(
        conn, SCHEMA, "pgu_machines", NEW_POWER_COL
    ):
        _rename_column("pgu_machines", OLD_COL, NEW_POWER_COL)

    for table in ("machines", "pgu_machines"):
        if not column_utils.table_has_column(conn, SCHEMA, table, NO_POWER_COL):
            op.add_column(
                table,
                sa.Column(NO_POWER_COL, sa.Integer(), nullable=True),
                schema=SCHEMA,
            )

    if (
        column_utils.table_has_column(conn, SCHEMA, "machines", NO_POWER_COL)
        and not column_utils.index_exists(conn, SCHEMA, MACHINES_NO_POWER_INDEX)
    ):
        op.create_index(
            MACHINES_NO_POWER_INDEX,
            "machines",
            [NO_POWER_COL],
            unique=False,
            schema=SCHEMA,
        )


def downgrade():
    conn = op.get_bind()

    if column_utils.index_exists(conn, SCHEMA, MACHINES_NO_POWER_INDEX):
        op.drop_index(
            MACHINES_NO_POWER_INDEX,
            table_name="machines",
            schema=SCHEMA,
        )
    for table in ("pgu_machines", "machines"):
        if column_utils.table_has_column(conn, SCHEMA, table, NO_POWER_COL):
            op.drop_column(table, NO_POWER_COL, schema=SCHEMA)

    if column_utils.table_has_column(
        conn, SCHEMA, "pgu_machines", NEW_POWER_COL
    ) and not column_utils.table_has_column(
        conn, SCHEMA, "pgu_machines", OLD_COL
    ):
        _rename_column("pgu_machines", NEW_POWER_COL, OLD_COL)

    if column_utils.table_has_column(
        conn, SCHEMA, "machines", NEW_POWER_COL
    ) and not column_utils.table_has_column(
        conn, SCHEMA, "machines", OLD_COL
    ):
        if column_utils.index_exists(conn, SCHEMA, MACHINES_POWER_INDEX):
            op.drop_index(
                MACHINES_POWER_INDEX,
                table_name="machines",
                schema=SCHEMA,
            )
        _rename_column("machines", NEW_POWER_COL, OLD_COL)
        if not column_utils.index_exists(conn, SCHEMA, MACHINES_OLD_MODERN_INDEX):
            op.create_index(
                MACHINES_OLD_MODERN_INDEX,
                "machines",
                [OLD_COL],
                unique=False,
                schema=SCHEMA,
            )

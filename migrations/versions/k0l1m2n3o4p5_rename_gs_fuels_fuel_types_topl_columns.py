"""rename gs_fuels and gs_fuel_types topl_nazvl/topl_kmbur to short names

Revision ID: k0l1m2n3o4p5
Revises: j9k0l1m2n3o4
Create Date: 2026-02-27

Переименовывает в gs_sys.gs_fuels: topl_nazvl->nazvl, topl_kmbur->kmbur.
Переименовывает в gs_sys.gs_fuel_types: topl_nazvl->nazvl.
Идемпотентно: выполняется только если старые колонки существуют.
"""

from alembic import op
from sqlalchemy import inspect
from config import SCHEMA_REFDATA


revision = "k0l1m2n3o4p5"
down_revision = "j9k0l1m2n3o4"
branch_labels = None
depends_on = None

SCHEMA = SCHEMA_REFDATA


def _column_exists(conn, table, col):
    inspector = inspect(conn)
    cols = [c["name"] for c in inspector.get_columns(table, schema=SCHEMA)]
    return col in cols


def upgrade():
    conn = op.get_bind()

    # gs_fuels: topl_nazvl -> nazvl, topl_kmbur -> kmbur
    if _column_exists(conn, "gs_fuels", "topl_nazvl") and not _column_exists(conn, "gs_fuels", "nazvl"):
        op.alter_column(
            "gs_fuels",
            "topl_nazvl",
            new_column_name="nazvl",
            schema=SCHEMA,
        )
    if _column_exists(conn, "gs_fuels", "topl_kmbur") and not _column_exists(conn, "gs_fuels", "kmbur"):
        op.alter_column(
            "gs_fuels",
            "topl_kmbur",
            new_column_name="kmbur",
            schema=SCHEMA,
        )

    # gs_fuel_types: topl_nazvl -> nazvl
    if _column_exists(conn, "gs_fuel_types", "topl_nazvl") and not _column_exists(conn, "gs_fuel_types", "nazvl"):
        op.alter_column(
            "gs_fuel_types",
            "topl_nazvl",
            new_column_name="nazvl",
            schema=SCHEMA,
        )


def downgrade():
    conn = op.get_bind()

    if _column_exists(conn, "gs_fuels", "nazvl") and not _column_exists(conn, "gs_fuels", "topl_nazvl"):
        op.alter_column(
            "gs_fuels",
            "nazvl",
            new_column_name="topl_nazvl",
            schema=SCHEMA,
        )
    if _column_exists(conn, "gs_fuels", "kmbur") and not _column_exists(conn, "gs_fuels", "topl_kmbur"):
        op.alter_column(
            "gs_fuels",
            "kmbur",
            new_column_name="topl_kmbur",
            schema=SCHEMA,
        )
    if _column_exists(conn, "gs_fuel_types", "nazvl") and not _column_exists(conn, "gs_fuel_types", "topl_nazvl"):
        op.alter_column(
            "gs_fuel_types",
            "nazvl",
            new_column_name="topl_nazvl",
            schema=SCHEMA,
        )

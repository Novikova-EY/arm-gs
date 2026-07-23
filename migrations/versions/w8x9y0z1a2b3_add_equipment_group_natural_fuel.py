"""add_equipment_group_natural_fuel

Revision ID: w8x9y0z1a2b3
Revises: v7w8x9y0z1a2
Create Date: 2026-07-23 11:20:00.000000

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


revision = "w8x9y0z1a2b3"
down_revision = "v7w8x9y0z1a2"
branch_labels = None
depends_on = None

SCHEMA = "gs_fue"
TABLE = "gs_fue_equipment_group_natural_fuel"

_FUEL_COLS = [
    "gaz", "gazpp", "gaz_prir", "isk_gaz", "domen_g", "koks_g", "prochgaz",
    "mazut", "disel", "maztop", "gtt", "nft_proch", "torf", "gtd", "slan",
    "proch", "tvproch", "szh_gaz", "inoe", "ugol", "don", "podm", "vork",
    "intin", "pech", "arkt", "kuzn", "kuzngd", "kuznt", "kuznss", "kuznun",
    "ural", "sver", "chel", "kizel", "bashk", "kazah", "ekib", "maikub",
    "karag", "karajyra", "teniz", "kan", "nazar", "ibor", "berez", "per",
    "irbei", "kansk", "irkut", "azey", "mug", "cher", "tung", "jer", "karab",
    "hak", "tuv", "bur", "gusin", "tugn", "okino", "chit", "har", "urt",
    "tataur", "tarbag", "zab_kam", "yakut", "neru", "zyryan", "pyak", "amur",
    "rai", "erk", "ogodj", "svo", "urg", "ushum", "prim", "bikin", "razdol",
    "hankai", "mag", "chukot", "bering", "anad", "kamch", "sah",
]


def _table_exists(connection):
    result = connection.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :table"
        ),
        {"schema": SCHEMA, "table": TABLE},
    )
    return result.fetchone() is not None


def upgrade():
    conn = op.get_bind()
    if _table_exists(conn):
        return
    ref_versions = column_utils.database_versions_physical_table_name(conn, "gs_sys")
    if ref_versions is None:
        raise RuntimeError(
            "Не найдена таблица версий БД в gs_sys "
            "(gs_sys_database_versions или gs_database_versions как BASE TABLE)"
        )
    cols = [
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("equipment_group_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=512), nullable=True),
        sa.Column("year_number", sa.Integer(), nullable=True),
    ]
    for name in _FUEL_COLS:
        cols.append(sa.Column(name, sa.Numeric(precision=36, scale=16), nullable=True))
    cols.extend(
        [
            sa.Column("obl", sa.String(length=80), nullable=True),
            sa.Column("dep", sa.String(length=80), nullable=True),
            sa.Column("oes", sa.String(length=80), nullable=True),
            sa.Column("er", sa.String(length=80), nullable=True),
            sa.Column("numb1120", sa.Integer(), nullable=True),
            sa.Column("numb1", sa.Integer(), nullable=True),
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
                [f"gs_sys.{ref_versions}.id"],
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
                name="uq_equipment_group_natural_fuel_group_year",
            ),
        ]
    )
    op.create_table(TABLE, *cols, schema=SCHEMA)
    op.create_index(
        "ix_gs_fue_equipment_group_natural_fuel_equipment_group_id",
        TABLE,
        ["equipment_group_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_fue_equipment_group_natural_fuel_year_number",
        TABLE,
        ["year_number"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_fue_equipment_group_natural_fuel_numb1120",
        TABLE,
        ["numb1120"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_fue_equipment_group_natural_fuel_database_version_id",
        TABLE,
        ["database_version_id"],
        schema=SCHEMA,
    )


def downgrade():
    op.drop_table(TABLE, schema=SCHEMA)

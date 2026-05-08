"""add_station_prospective_place_aes

Revision ID: o7p8q9r0s1t2
Revises: n6o7p8q9r0s1
Create Date: 2026-03-19

Создает таблицу station_prospective_place_aes (перспективные площадки размещения АЭС).
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402


revision = "o7p8q9r0s1t2"
down_revision = "n6o7p8q9r0s1"
branch_labels = None
depends_on = None

SCHEMA = "gs_gen"
SCHEMA_REF = "gs_sys"
TABLE = "station_prospective_place_aes"


def upgrade():
    conn = op.get_bind()
    # Уже есть под старым или новым именем (в т.ч. после c2d3e4f5a6b7).
    if column_utils.station_prospective_place_aes_table_name(conn, SCHEMA) is not None:
        return
    ref_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REF)
    if ref_versions is None:
        raise RuntimeError(
            f"Не найдена таблица версий БД в {SCHEMA_REF} "
            "(gs_sys_database_versions или gs_database_versions как BASE TABLE)"
        )
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_name", sa.String(length=255), nullable=True),
        sa.Column("subject_rf", sa.String(length=255), nullable=True),
        sa.Column("geo_location", sa.String(length=500), nullable=True),
        sa.Column("planned_capacity_mw", sa.String(length=100), nullable=True),
        sa.Column("service_life_years", sa.Integer(), nullable=True),
        sa.Column("construction_period_years", sa.Integer(), nullable=True),
        sa.Column("commissioning_year", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_station_prospective_place_aes_site_name",
        TABLE,
        ["site_name"],
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_station_prospective_place_aes_database_version",
        TABLE,
        ref_versions,
        ["database_version_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA_REF,
        ondelete="SET NULL",
    )


def downgrade():
    conn = op.get_bind()
    tbl = column_utils.station_prospective_place_aes_table_name(conn, SCHEMA)
    if tbl is None:
        return
    op.drop_constraint(
        "fk_station_prospective_place_aes_database_version",
        tbl,
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_index("ix_station_prospective_place_aes_site_name", table_name=tbl, schema=SCHEMA)
    op.drop_table(tbl, schema=SCHEMA)

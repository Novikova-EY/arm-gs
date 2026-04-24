"""add_station_prospective_place_aes

Revision ID: o7p8q9r0s1t2
Revises: n6o7p8q9r0s1
Create Date: 2026-03-19

Создает таблицу station_prospective_place_aes (перспективные площадки размещения АЭС).
"""
from alembic import op
import sqlalchemy as sa


revision = "o7p8q9r0s1t2"
down_revision = "n6o7p8q9r0s1"
branch_labels = None
depends_on = None

SCHEMA = "gs_gen"
SCHEMA_REF = "gs_sys"
TABLE = "station_prospective_place_aes"


def upgrade():
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
        "gs_database_versions",
        ["database_version_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA_REF,
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint(
        "fk_station_prospective_place_aes_database_version",
        TABLE,
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_index("ix_station_prospective_place_aes_site_name", table_name=TABLE, schema=SCHEMA)
    op.drop_table(TABLE, schema=SCHEMA)

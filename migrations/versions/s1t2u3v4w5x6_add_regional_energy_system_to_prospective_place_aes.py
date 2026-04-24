"""add_regional_energy_system_to_prospective_place_aes

Revision ID: s1t2u3v4w5x6
Revises: r0s1t2u3v4w5
Create Date: 2026-03-19

Добавляет FK id_regional_energy_system -> gs_regional_energy_systems в station_prospective_place_aes.
"""
from alembic import op
import sqlalchemy as sa


revision = "s1t2u3v4w5x6"
down_revision = "r0s1t2u3v4w5"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REF = "gs_sys"
TABLE = "station_prospective_place_aes"
TABLE_RES = "gs_regional_energy_systems"


def upgrade():
    op.add_column(
        TABLE,
        sa.Column("id_regional_energy_system", sa.Integer(), nullable=True),
        schema=SCHEMA_GEN,
    )
    op.create_index(
        "ix_station_prospective_place_aes_id_regional_energy_system",
        TABLE,
        ["id_regional_energy_system"],
        schema=SCHEMA_GEN,
    )
    op.create_foreign_key(
        "fk_station_prospective_place_aes_regional_energy_system",
        TABLE,
        TABLE_RES,
        ["id_regional_energy_system"],
        ["id"],
        source_schema=SCHEMA_GEN,
        referent_schema=SCHEMA_REF,
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint(
        "fk_station_prospective_place_aes_regional_energy_system",
        TABLE,
        schema=SCHEMA_GEN,
        type_="foreignkey",
    )
    op.drop_index(
        "ix_station_prospective_place_aes_id_regional_energy_system",
        table_name=TABLE,
        schema=SCHEMA_GEN,
    )
    op.drop_column(TABLE, "id_regional_energy_system", schema=SCHEMA_GEN)

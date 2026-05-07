"""Таблица выработки электроэнергии по электростанции (млн кВт·ч по годам).

Revision ID: a1b2c3d4e5z9
Revises: w4x5y6z7a8b9
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5z9"
down_revision = "w4x5y6z7a8b9"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REF = "gs_sys"
TABLE = "gs_gen_station_energy_generations"


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if TABLE in inspector.get_table_names(schema=SCHEMA_GEN):
        op.drop_table(TABLE, schema=SCHEMA_GEN)

    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("year_number", sa.Integer(), nullable=True),
        sa.Column("id_station", sa.Integer(), nullable=True),
        sa.Column("electricity_generation", sa.Numeric(25, 16), nullable=True),
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
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA_GEN,
    )
    op.create_index(
        "ix_station_energy_gen_id_station",
        TABLE,
        ["id_station"],
        schema=SCHEMA_GEN,
    )
    op.create_index(
        "ix_station_energy_gen_year_number",
        TABLE,
        ["year_number"],
        schema=SCHEMA_GEN,
    )
    op.create_index(
        "ix_station_energy_gen_station_year",
        TABLE,
        ["id_station", "year_number"],
        schema=SCHEMA_GEN,
    )
    # FK на gs_sys_years(number) не создаём: у годов уникальность (number, database_version_id), не number.
    op.create_foreign_key(
        "fk_station_energy_gen_station",
        TABLE,
        "gs_gen_stations",
        ["id_station"],
        ["id"],
        source_schema=SCHEMA_GEN,
        referent_schema=SCHEMA_GEN,
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_station_energy_gen_database_version",
        TABLE,
        "gs_database_versions",
        ["database_version_id"],
        ["id"],
        source_schema=SCHEMA_GEN,
        referent_schema=SCHEMA_REF,
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint(
        "fk_station_energy_gen_database_version",
        TABLE,
        schema=SCHEMA_GEN,
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_station_energy_gen_station",
        TABLE,
        schema=SCHEMA_GEN,
        type_="foreignkey",
    )
    op.drop_index(
        "ix_station_energy_gen_station_year",
        table_name=TABLE,
        schema=SCHEMA_GEN,
    )
    op.drop_index(
        "ix_station_energy_gen_year_number",
        table_name=TABLE,
        schema=SCHEMA_GEN,
    )
    op.drop_index(
        "ix_station_energy_gen_id_station",
        table_name=TABLE,
        schema=SCHEMA_GEN,
    )
    op.drop_table(TABLE, schema=SCHEMA_GEN)

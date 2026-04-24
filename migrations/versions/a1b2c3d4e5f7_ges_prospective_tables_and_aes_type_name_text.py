"""ges_prospective_tables_and_aes_type_name_text

Revision ID: a1b2c3d4e5f7
Revises: z8a9b0c1d2e3
Create Date: 2026-03-30

- gs_prospective_place_types (АЭС): name VARCHAR(80) -> TEXT для длинных наименований
- gs_prospective_place_types_ges: новый справочник типов площадок ГЭС
- station_prospective_place_ges: перспективные площадки ГЭС
- ges_tep_source_project_indicators: перечень исходных ТЭП новых ГЭС
"""
from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f7"
down_revision = "z8a9b0c1d2e3"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REF = "gs_sys"

TABLE_AES_TYPES = "gs_prospective_place_types"
TABLE_GES_TYPES = "gs_prospective_place_types_ges"
TABLE_STATION_GES = "station_prospective_place_ges"
TABLE_TEP_GES = "ges_tep_source_project_indicators"


def upgrade():
    # --- 1. ProspectivePlaceTypeAES: name -> TEXT ---
    op.drop_index(
        "ix_gs_prospective_place_types_name",
        table_name=TABLE_AES_TYPES,
        schema=SCHEMA_REF,
    )
    op.alter_column(
        TABLE_AES_TYPES,
        "name",
        existing_type=sa.String(length=80),
        type_=sa.Text(),
        existing_nullable=False,
        schema=SCHEMA_REF,
    )
    op.create_index(
        "ix_gs_prospective_place_types_name",
        TABLE_AES_TYPES,
        ["name"],
        unique=True,
        schema=SCHEMA_REF,
    )

    # --- 2. Справочник типов площадок ГЭС ---
    op.create_table(
        TABLE_GES_TYPES,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
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
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_gs_prospective_place_types_ges_name"),
        schema=SCHEMA_REF,
    )

    # --- 3. Площадки ГЭС ---
    op.create_table(
        TABLE_STATION_GES,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_name", sa.String(length=255), nullable=True),
        sa.Column("id_regional_district", sa.Integer(), nullable=True),
        sa.Column("id_regional_energy_system", sa.Integer(), nullable=True),
        sa.Column("geo_location", sa.String(length=500), nullable=True),
        sa.Column("planned_capacity_mw", sa.Integer(), nullable=True),
        sa.Column("project_initiator", sa.String(length=500), nullable=True),
        sa.Column("water_body", sa.String(length=500), nullable=True),
        sa.Column("general_scheme_commissioning_period", sa.String(length=255), nullable=True),
        sa.Column("construction_period_years", sa.Integer(), nullable=True),
        sa.Column("regional_subject_name", sa.String(length=255), nullable=True),
        sa.Column("planned_unit_capacity_mw", sa.Integer(), nullable=True),
        sa.Column("selection_factor", sa.Text(), nullable=True),
        sa.Column("construction_period_years_minenergo_protocol", sa.Integer(), nullable=True),
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
        "ix_station_prospective_place_ges_site_name",
        TABLE_STATION_GES,
        ["site_name"],
        schema=SCHEMA_GEN,
    )
    op.create_index(
        "ix_station_prospective_place_ges_id_regional_district",
        TABLE_STATION_GES,
        ["id_regional_district"],
        schema=SCHEMA_GEN,
    )
    op.create_index(
        "ix_station_prospective_place_ges_id_regional_energy_system",
        TABLE_STATION_GES,
        ["id_regional_energy_system"],
        schema=SCHEMA_GEN,
    )
    op.create_index(
        "ix_station_prospective_place_ges_database_version_id",
        TABLE_STATION_GES,
        ["database_version_id"],
        schema=SCHEMA_GEN,
    )
    op.create_foreign_key(
        "fk_station_prospective_place_ges_regional_district",
        TABLE_STATION_GES,
        "gs_regional_districts",
        ["id_regional_district"],
        ["id"],
        source_schema=SCHEMA_GEN,
        referent_schema=SCHEMA_REF,
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_station_prospective_place_ges_regional_energy_system",
        TABLE_STATION_GES,
        "gs_regional_energy_systems",
        ["id_regional_energy_system"],
        ["id"],
        source_schema=SCHEMA_GEN,
        referent_schema=SCHEMA_REF,
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_station_prospective_place_ges_database_version",
        TABLE_STATION_GES,
        "gs_database_versions",
        ["database_version_id"],
        ["id"],
        source_schema=SCHEMA_GEN,
        referent_schema=SCHEMA_REF,
        ondelete="SET NULL",
    )

    # --- 4. ТЭП ГЭС ---
    op.create_table(
        TABLE_TEP_GES,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_station_prospective_place_ges", sa.Integer(), nullable=False),
        sa.Column("id_prospective_place_type_ges", sa.Integer(), nullable=True),
        sa.Column("installed_capacity_mw", sa.String(length=100), nullable=True),
        sa.Column("stage_1_capacity_mw", sa.String(length=100), nullable=True),
        sa.Column("stage_2_capacity_mw", sa.String(length=100), nullable=True),
        sa.Column("startup_complex_capacity_mw", sa.String(length=100), nullable=True),
        sa.Column("units_count", sa.Integer(), nullable=True),
        sa.Column("unit_capacity_mw", sa.String(length=100), nullable=True),
        sa.Column("hydro_turbine_type", sa.String(length=500), nullable=True),
        sa.Column("construction_period_years", sa.Integer(), nullable=True),
        sa.Column("construction_increment_year_01_mw", sa.String(length=100), nullable=True),
        sa.Column("construction_increment_year_02_mw", sa.String(length=100), nullable=True),
        sa.Column("construction_increment_year_03_mw", sa.String(length=100), nullable=True),
        sa.Column("construction_increment_year_04_mw", sa.String(length=100), nullable=True),
        sa.Column("construction_increment_year_05_mw", sa.String(length=100), nullable=True),
        sa.Column("construction_increment_year_06_mw", sa.String(length=100), nullable=True),
        sa.Column("construction_increment_year_07_mw", sa.String(length=100), nullable=True),
        sa.Column("construction_increment_year_08_mw", sa.String(length=100), nullable=True),
        sa.Column("construction_increment_year_09_mw", sa.String(length=100), nullable=True),
        sa.Column("construction_increment_year_10_mw", sa.String(length=100), nullable=True),
        sa.Column("construction_increment_year_11_mw", sa.String(length=100), nullable=True),
        sa.Column("specific_semifixed_operating_costs_thous_rub_per_kw", sa.String(length=100), nullable=True),
        sa.Column("generation_medium_water_50pct_billion_kwh", sa.String(length=100), nullable=True),
        sa.Column("generation_medium_water_management_year", sa.String(length=255), nullable=True),
        sa.Column("generation_low_water_95pct_billion_kwh", sa.String(length=100), nullable=True),
        sa.Column("generation_low_water_management_year", sa.String(length=255), nullable=True),
        sa.Column("specific_capital_investment_thous_rub_per_kw", sa.String(length=100), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
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
        "ix_ges_tep_source_id_station",
        TABLE_TEP_GES,
        ["id_station_prospective_place_ges"],
        schema=SCHEMA_GEN,
    )
    op.create_index(
        "ix_ges_tep_source_id_prospective_place_type_ges",
        TABLE_TEP_GES,
        ["id_prospective_place_type_ges"],
        schema=SCHEMA_GEN,
    )
    op.create_index(
        "ix_ges_tep_source_project_indicators_database_version_id",
        TABLE_TEP_GES,
        ["database_version_id"],
        schema=SCHEMA_GEN,
    )
    op.create_foreign_key(
        "fk_ges_tep_station_prospective_place_ges",
        TABLE_TEP_GES,
        TABLE_STATION_GES,
        ["id_station_prospective_place_ges"],
        ["id"],
        source_schema=SCHEMA_GEN,
        referent_schema=SCHEMA_GEN,
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_ges_tep_prospective_place_type_ges",
        TABLE_TEP_GES,
        TABLE_GES_TYPES,
        ["id_prospective_place_type_ges"],
        ["id"],
        source_schema=SCHEMA_GEN,
        referent_schema=SCHEMA_REF,
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_ges_tep_database_version",
        TABLE_TEP_GES,
        "gs_database_versions",
        ["database_version_id"],
        ["id"],
        source_schema=SCHEMA_GEN,
        referent_schema=SCHEMA_REF,
        ondelete="SET NULL",
    )

    # --- 5. Три канонических типа площадки ГЭС ---
    op.execute(
        sa.text(
            f"""
            INSERT INTO {SCHEMA_REF}.{TABLE_GES_TYPES} (name) VALUES
            ('Перечень ГЭС в соответствии с Генеральной схемой до 2042 года. Распоряжение Правительства от 30.12.2024 №4153-р'),
            ('Перечень дополнительных ГЭС, необходимость и целесообразность реализация которых в настоящее время прорабатывается рабочей группой по вопросам подготовки плана-графика реализации механизмов привлечения инвестиций и строительства ГЭС на территории РФ'),
            ('Площадки размещения новых ГЭС')
            ON CONFLICT (name) DO NOTHING
            """
        )
    )


def downgrade():
    op.drop_constraint("fk_ges_tep_database_version", TABLE_TEP_GES, schema=SCHEMA_GEN, type_="foreignkey")
    op.drop_constraint("fk_ges_tep_prospective_place_type_ges", TABLE_TEP_GES, schema=SCHEMA_GEN, type_="foreignkey")
    op.drop_constraint("fk_ges_tep_station_prospective_place_ges", TABLE_TEP_GES, schema=SCHEMA_GEN, type_="foreignkey")
    op.drop_index("ix_ges_tep_source_project_indicators_database_version_id", table_name=TABLE_TEP_GES, schema=SCHEMA_GEN)
    op.drop_index("ix_ges_tep_source_id_prospective_place_type_ges", table_name=TABLE_TEP_GES, schema=SCHEMA_GEN)
    op.drop_index("ix_ges_tep_source_id_station", table_name=TABLE_TEP_GES, schema=SCHEMA_GEN)
    op.drop_table(TABLE_TEP_GES, schema=SCHEMA_GEN)

    op.drop_constraint("fk_station_prospective_place_ges_database_version", TABLE_STATION_GES, schema=SCHEMA_GEN, type_="foreignkey")
    op.drop_constraint("fk_station_prospective_place_ges_regional_energy_system", TABLE_STATION_GES, schema=SCHEMA_GEN, type_="foreignkey")
    op.drop_constraint("fk_station_prospective_place_ges_regional_district", TABLE_STATION_GES, schema=SCHEMA_GEN, type_="foreignkey")
    op.drop_index("ix_station_prospective_place_ges_database_version_id", table_name=TABLE_STATION_GES, schema=SCHEMA_GEN)
    op.drop_index("ix_station_prospective_place_ges_id_regional_energy_system", table_name=TABLE_STATION_GES, schema=SCHEMA_GEN)
    op.drop_index("ix_station_prospective_place_ges_id_regional_district", table_name=TABLE_STATION_GES, schema=SCHEMA_GEN)
    op.drop_index("ix_station_prospective_place_ges_site_name", table_name=TABLE_STATION_GES, schema=SCHEMA_GEN)
    op.drop_table(TABLE_STATION_GES, schema=SCHEMA_GEN)

    op.drop_table(TABLE_GES_TYPES, schema=SCHEMA_REF)

    op.drop_index("ix_gs_prospective_place_types_name", table_name=TABLE_AES_TYPES, schema=SCHEMA_REF)
    op.execute(
        sa.text(
            f"ALTER TABLE {SCHEMA_REF}.{TABLE_AES_TYPES} "
            "ALTER COLUMN name TYPE VARCHAR(80) USING left(name::text, 80)"
        )
    )
    op.create_index(
        "ix_gs_prospective_place_types_name",
        TABLE_AES_TYPES,
        ["name"],
        unique=True,
        schema=SCHEMA_REF,
    )

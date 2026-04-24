# -*- coding: utf-8 -*-
"""add_gaes_prospective_place_tables

Revision ID: f1e2d3c4b5a6
Revises: e7f8a9b0c1d2
Create Date: 2026-03-31

Таблицы справочника типов площадки ГАЭС (ProspectivePlaceTypeGAES) и
площадок (StationProspectivePlaceGAES). Отдельно от таблиц ГЭС (ges / без «a»).
"""
from alembic import op
import sqlalchemy as sa


revision = "f1e2d3c4b5a6"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REF = "gs_sys"

TABLE_TYPES_GAES = "gs_prospective_place_types_gaes"
TABLE_STATION_GAES = "station_prospective_place_gaes"

CANONICAL_TYPE_NAMES = (
    "Перечень ГАЭС в соответствии с Генеральной схемой до 2042 года. Распоряжение Правительства от 30.12.2024 №4153-р",
    "Перечень дополнительных ГАЭС, необходимость и целесообразность реализация которых в настоящее время прорабатывается рабочей группой по вопросам подготовки плана-графика реализации механизмов привлечения инвестиций и определения механизмов и площадок реализации проектов сооружения ГАЭС на территории РФ",
)


def _has_table(bind, schema: str, table: str) -> bool:
    insp = sa.inspect(bind)
    try:
        return table in insp.get_table_names(schema=schema)
    except Exception:
        return False


def upgrade():
    bind = op.get_bind()

    if not _has_table(bind, SCHEMA_REF, TABLE_TYPES_GAES):
        op.create_table(
            TABLE_TYPES_GAES,
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
            sa.UniqueConstraint("name", name="uq_gs_prospective_place_types_gaes_name"),
            schema=SCHEMA_REF,
        )

        bind = op.get_bind()
        ins = sa.text(
            f'INSERT INTO "{SCHEMA_REF}"."{TABLE_TYPES_GAES}" (name, created_at, updated_at) '
            "VALUES (:n, now(), now()) ON CONFLICT (name) DO NOTHING"
        )
        for name in CANONICAL_TYPE_NAMES:
            bind.execute(ins, {"n": name})

    if not _has_table(bind, SCHEMA_GEN, TABLE_STATION_GAES):
        op.create_table(
            TABLE_STATION_GAES,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("site_name", sa.String(length=255), nullable=True),
            sa.Column("id_regional_district", sa.Integer(), nullable=True),
            sa.Column("id_regional_energy_system", sa.Integer(), nullable=True),
            sa.Column("geo_location", sa.String(length=500), nullable=True),
            sa.Column("planned_capacity_mw", sa.String(length=500), nullable=True),
            sa.Column("project_initiator", sa.String(length=500), nullable=True),
            sa.Column("water_body", sa.String(length=500), nullable=True),
            sa.Column("general_scheme_commissioning_period", sa.String(length=255), nullable=True),
            sa.Column("construction_period_years", sa.Integer(), nullable=True),
            sa.Column("id_prospective_place_type_gaes", sa.Integer(), nullable=True),
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
            "ix_station_prospective_place_gaes_site_name",
            TABLE_STATION_GAES,
            ["site_name"],
            schema=SCHEMA_GEN,
        )
        op.create_index(
            "ix_station_prospective_place_gaes_id_regional_district",
            TABLE_STATION_GAES,
            ["id_regional_district"],
            schema=SCHEMA_GEN,
        )
        op.create_index(
            "ix_station_prospective_place_gaes_id_regional_energy_system",
            TABLE_STATION_GAES,
            ["id_regional_energy_system"],
            schema=SCHEMA_GEN,
        )
        op.create_index(
            "ix_station_pp_gaes_id_place_type_gaes",
            TABLE_STATION_GAES,
            ["id_prospective_place_type_gaes"],
            schema=SCHEMA_GEN,
        )
        op.create_index(
            "ix_station_prospective_place_gaes_database_version_id",
            TABLE_STATION_GAES,
            ["database_version_id"],
            schema=SCHEMA_GEN,
        )
        op.create_foreign_key(
            "fk_station_prospective_place_gaes_regional_district",
            TABLE_STATION_GAES,
            "gs_regional_districts",
            ["id_regional_district"],
            ["id"],
            source_schema=SCHEMA_GEN,
            referent_schema=SCHEMA_REF,
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_station_prospective_place_gaes_regional_energy_system",
            TABLE_STATION_GAES,
            "gs_regional_energy_systems",
            ["id_regional_energy_system"],
            ["id"],
            source_schema=SCHEMA_GEN,
            referent_schema=SCHEMA_REF,
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_station_prospective_place_gaes_prospective_place_type_gaes",
            TABLE_STATION_GAES,
            TABLE_TYPES_GAES,
            ["id_prospective_place_type_gaes"],
            ["id"],
            source_schema=SCHEMA_GEN,
            referent_schema=SCHEMA_REF,
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_station_prospective_place_gaes_database_version",
            TABLE_STATION_GAES,
            "gs_database_versions",
            ["database_version_id"],
            ["id"],
            source_schema=SCHEMA_GEN,
            referent_schema=SCHEMA_REF,
            ondelete="SET NULL",
        )


def downgrade():
    bind = op.get_bind()
    if _has_table(bind, SCHEMA_GEN, TABLE_STATION_GAES):
        op.drop_table(TABLE_STATION_GAES, schema=SCHEMA_GEN)
    if _has_table(bind, SCHEMA_REF, TABLE_TYPES_GAES):
        op.drop_table(TABLE_TYPES_GAES, schema=SCHEMA_REF)

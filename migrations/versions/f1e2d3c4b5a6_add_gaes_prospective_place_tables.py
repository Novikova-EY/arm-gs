# -*- coding: utf-8 -*-
"""add_gaes_prospective_place_tables

Revision ID: f1e2d3c4b5a6
Revises: e7f8a9b0c1d2
Create Date: 2026-03-31

Таблицы справочника типов площадки ГАЭС (ProspectivePlaceTypeGAES) и
площадок (StationProspectivePlaceGAES). Отдельно от таблиц ГЭС (ges / без «a»).
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402


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
    ref_versions = column_utils.database_versions_physical_table_name(bind, SCHEMA_REF)
    table_rd = column_utils.refdata_table_name(bind, SCHEMA_REF, "gs_regional_districts")
    table_res = column_utils.refdata_table_name(bind, SCHEMA_REF, "gs_regional_energy_systems")
    if ref_versions is None:
        raise RuntimeError(
            f"Не найдена таблица версий БД в {SCHEMA_REF} "
            "(gs_sys_database_versions или gs_database_versions как BASE TABLE)"
        )

    table_types_gaes = column_utils.prospective_place_types_gaes_table_name(bind, SCHEMA_REF)
    table_station_gaes = column_utils.station_prospective_place_gaes_table_name(bind, SCHEMA_GEN)
    if table_rd is None or table_res is None:
        return

    if table_types_gaes is None:
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
        table_types_gaes = TABLE_TYPES_GAES

        bind = op.get_bind()
        ins = sa.text(
            f'INSERT INTO "{SCHEMA_REF}"."{table_types_gaes}" (name, created_at, updated_at) '
            "VALUES (:n, now(), now()) ON CONFLICT (name) DO NOTHING"
        )
        for name in CANONICAL_TYPE_NAMES:
            bind.execute(ins, {"n": name})

    if table_station_gaes is None:
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
        table_station_gaes = TABLE_STATION_GAES
        for index_name, cols in (
            ("ix_station_prospective_place_gaes_site_name", ["site_name"]),
            ("ix_station_prospective_place_gaes_id_regional_district", ["id_regional_district"]),
            ("ix_station_prospective_place_gaes_id_regional_energy_system", ["id_regional_energy_system"]),
            ("ix_station_pp_gaes_id_place_type_gaes", ["id_prospective_place_type_gaes"]),
            ("ix_station_prospective_place_gaes_database_version_id", ["database_version_id"]),
        ):
            if not column_utils.index_exists(bind, SCHEMA_GEN, index_name):
                op.create_index(index_name, table_station_gaes, cols, schema=SCHEMA_GEN)
        if not column_utils.constraint_exists(bind, SCHEMA_GEN, "fk_station_prospective_place_gaes_regional_district"):
            op.create_foreign_key(
                "fk_station_prospective_place_gaes_regional_district",
                table_station_gaes,
                table_rd,
                ["id_regional_district"],
                ["id"],
                source_schema=SCHEMA_GEN,
                referent_schema=SCHEMA_REF,
                ondelete="SET NULL",
            )
        if not column_utils.constraint_exists(bind, SCHEMA_GEN, "fk_station_prospective_place_gaes_regional_energy_system"):
            op.create_foreign_key(
                "fk_station_prospective_place_gaes_regional_energy_system",
                table_station_gaes,
                table_res,
                ["id_regional_energy_system"],
                ["id"],
                source_schema=SCHEMA_GEN,
                referent_schema=SCHEMA_REF,
                ondelete="SET NULL",
            )
        if not column_utils.constraint_exists(bind, SCHEMA_GEN, "fk_station_prospective_place_gaes_prospective_place_type_gaes"):
            op.create_foreign_key(
                "fk_station_prospective_place_gaes_prospective_place_type_gaes",
                table_station_gaes,
                table_types_gaes,
                ["id_prospective_place_type_gaes"],
                ["id"],
                source_schema=SCHEMA_GEN,
                referent_schema=SCHEMA_REF,
                ondelete="SET NULL",
            )
        if not column_utils.constraint_exists(bind, SCHEMA_GEN, "fk_station_prospective_place_gaes_database_version"):
            op.create_foreign_key(
                "fk_station_prospective_place_gaes_database_version",
                table_station_gaes,
                ref_versions,
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

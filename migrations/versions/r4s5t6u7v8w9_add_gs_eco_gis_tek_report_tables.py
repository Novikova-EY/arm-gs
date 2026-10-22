# -*- coding: utf-8 -*-
"""Схема gs_eco и таблицы отчетных данных ГИС ТЭК (ПГ, ЗВ).

Revision ID: r4s5t6u7v8w9
Revises: q3r4s5t6u7v8
Create Date: 2026-08-31
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

revision = "r4s5t6u7v8w9"
down_revision = "q3r4s5t6u7v8"
branch_labels = None
depends_on = None

SCHEMA_ECO = "gs_eco"
SCHEMA_REFDATA = "gs_sys"
SCHEMA_FUEL = "gs_fue"
TABLE_PG = "gs_eco_gis_tek_greenhouse_gas_params"
TABLE_ZV = "gs_eco_gis_tek_pollutant_params"

_COMMON_COLUMNS = {
    "id": "Уникальный идентификатор записи",
    "created_by": "Пользователь, создавший запись",
    "modified_by": "Пользователь, последним изменивший запись",
    "created_at": "Дата и время создания записи",
    "updated_at": "Дата и время последнего изменения записи",
    "database_version_id": "Версия базы данных (FK -> gs_sys.gs_database_versions)",
    "note": "Примечание",
    "station_numb": "№_станции из ГИС ТЭК; связь с группой оборудования (Топливо) по numb",
    "gis_tek_station_name": "Электростанция (ГИС ТЭК) – наименование из файла",
    "station_type": "Тип станции из файла ГИС ТЭК",
    "equipment_group_id": "Группа оборудования (Топливо), FK -> gs_fue.gs_fue_equipment_groups",
    "year_number": "Год (связь с gs_sys.gs_sys_years по number и database_version_id)",
}


def _schema_exists(connection, schema: str) -> bool:
    r = connection.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema"),
        {"schema": schema},
    )
    return r.fetchone() is not None


def _comment_on_table(conn, schema: str, table: str, comment: str) -> None:
    conn.execute(
        text(f'COMMENT ON TABLE "{schema}"."{table}" IS :comment'),
        {"comment": comment},
    )


def _comment_on_column(conn, schema: str, table: str, column: str, comment: str) -> None:
    conn.execute(
        text(f'COMMENT ON COLUMN "{schema}"."{table}"."{column}" IS :comment'),
        {"comment": comment},
    )


def _identity_columns(equipment_groups: str, ref_db_versions: str):
    return [
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("station_numb", sa.Integer(), nullable=False),
        sa.Column("gis_tek_station_name", sa.Text(), nullable=True),
        sa.Column("station_type", sa.String(length=80), nullable=True),
        sa.Column("equipment_group_id", sa.Integer(), nullable=True),
        sa.Column("year_number", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["equipment_group_id"],
            [f"{SCHEMA_FUEL}.{equipment_groups}.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["year_number", "database_version_id"],
            [
                f"{SCHEMA_REFDATA}.gs_sys_years.number",
                f"{SCHEMA_REFDATA}.gs_sys_years.database_version_id",
            ],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            [f"{SCHEMA_REFDATA}.{ref_db_versions}.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    ]


def upgrade():
    conn = op.get_bind()
    ref_db_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REFDATA)
    if ref_db_versions is None:
        raise RuntimeError(
            f"Не найдена таблица версий БД в {SCHEMA_REFDATA}"
        )
    years = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_years")
    if years is None:
        raise RuntimeError(f"Не найдена таблица годов в {SCHEMA_REFDATA}")
    equipment_groups = "gs_fue_equipment_groups"
    if not column_utils.table_exists(conn, SCHEMA_FUEL, equipment_groups):
        raise RuntimeError(f"Не найдена таблица {SCHEMA_FUEL}.{equipment_groups}")

    if not _schema_exists(conn, SCHEMA_ECO):
        op.execute(sa.text(f'CREATE SCHEMA "{SCHEMA_ECO}"'))

    if not column_utils.table_exists(conn, SCHEMA_ECO, TABLE_PG):
        op.create_table(
            TABLE_PG,
            *_identity_columns(equipment_groups, ref_db_versions),
            sa.Column("gas_consumption_tce", sa.Numeric(36, 16), nullable=True),
            sa.Column("co2_from_gas_t", sa.Numeric(36, 16), nullable=True),
            sa.Column("oil_fuel_consumption_tce", sa.Numeric(36, 16), nullable=True),
            sa.Column("co2_from_oil_fuel_t", sa.Numeric(36, 16), nullable=True),
            sa.Column("solid_fuel_consumption_tce", sa.Numeric(36, 16), nullable=True),
            sa.Column("co2_from_solid_fuel_t", sa.Numeric(36, 16), nullable=True),
            sa.UniqueConstraint(
                "station_numb",
                "year_number",
                "database_version_id",
                name="uq_eco_gis_tek_pg_numb_year_ver",
            ),
            schema=SCHEMA_ECO,
        )
        op.create_index("ix_eco_gis_tek_pg_numb", TABLE_PG, ["station_numb"], schema=SCHEMA_ECO)
        op.create_index("ix_eco_gis_tek_pg_year", TABLE_PG, ["year_number"], schema=SCHEMA_ECO)
        op.create_index("ix_eco_gis_tek_pg_eg", TABLE_PG, ["equipment_group_id"], schema=SCHEMA_ECO)
        op.create_index("ix_eco_gis_tek_pg_dbver", TABLE_PG, ["database_version_id"], schema=SCHEMA_ECO)
        _comment_on_table(
            conn,
            SCHEMA_ECO,
            TABLE_PG,
            "Отчетные данные ГИС ТЭК: парниковые газы (ПГ)",
        )
        for col, comment in {
            **_COMMON_COLUMNS,
            "gas_consumption_tce": "Расход газа, тут",
            "co2_from_gas_t": "Выбросы СО2 от сжигания газа, т",
            "oil_fuel_consumption_tce": "Расход нефтетоплива, тут",
            "co2_from_oil_fuel_t": "Выбросы СО2 от сжигания нефтетоплива, т",
            "solid_fuel_consumption_tce": "Расход твердого топлива, тут",
            "co2_from_solid_fuel_t": "Выбросы СО2 от сжигания твердого топлива, т",
        }.items():
            _comment_on_column(conn, SCHEMA_ECO, TABLE_PG, col, comment)

    if not column_utils.table_exists(conn, SCHEMA_ECO, TABLE_ZV):
        op.create_table(
            TABLE_ZV,
            *_identity_columns(equipment_groups, ref_db_versions),
            sa.Column("solid_substances", sa.Numeric(36, 16), nullable=True),
            sa.Column("gaseous_and_liquid", sa.Numeric(36, 16), nullable=True),
            sa.Column("sulfur_dioxide", sa.Numeric(36, 16), nullable=True),
            sa.Column("carbon_monoxide", sa.Numeric(36, 16), nullable=True),
            sa.Column("nitrogen_oxides", sa.Numeric(36, 16), nullable=True),
            sa.Column("hydrocarbons", sa.Numeric(36, 16), nullable=True),
            sa.Column("voc", sa.Numeric(36, 16), nullable=True),
            sa.Column("other_gaseous_and_liquid", sa.Numeric(36, 16), nullable=True),
            sa.UniqueConstraint(
                "station_numb",
                "year_number",
                "database_version_id",
                name="uq_eco_gis_tek_zv_numb_year_ver",
            ),
            schema=SCHEMA_ECO,
        )
        op.create_index("ix_eco_gis_tek_zv_numb", TABLE_ZV, ["station_numb"], schema=SCHEMA_ECO)
        op.create_index("ix_eco_gis_tek_zv_year", TABLE_ZV, ["year_number"], schema=SCHEMA_ECO)
        op.create_index("ix_eco_gis_tek_zv_eg", TABLE_ZV, ["equipment_group_id"], schema=SCHEMA_ECO)
        op.create_index("ix_eco_gis_tek_zv_dbver", TABLE_ZV, ["database_version_id"], schema=SCHEMA_ECO)
        _comment_on_table(
            conn,
            SCHEMA_ECO,
            TABLE_ZV,
            "Отчетные данные ГИС ТЭК: загрязняющие вещества (ЗВ)",
        )
        for col, comment in {
            **_COMMON_COLUMNS,
            "solid_substances": "Твердые вещества",
            "gaseous_and_liquid": "Газообразные и жидкие вещества",
            "sulfur_dioxide": "диоксид серы",
            "carbon_monoxide": "оксид углерода [CO]",
            "nitrogen_oxides": "оксиды азота [в пересчете на NO2]",
            "hydrocarbons": "углеводороды [без летучих органических соединений]",
            "voc": "летучие органические соединения [ЛОС]",
            "other_gaseous_and_liquid": "прочие газообразные и жидкие",
        }.items():
            _comment_on_column(conn, SCHEMA_ECO, TABLE_ZV, col, comment)


def downgrade():
    conn = op.get_bind()
    if column_utils.table_exists(conn, SCHEMA_ECO, TABLE_ZV):
        op.drop_table(TABLE_ZV, schema=SCHEMA_ECO)
    if column_utils.table_exists(conn, SCHEMA_ECO, TABLE_PG):
        op.drop_table(TABLE_PG, schema=SCHEMA_ECO)

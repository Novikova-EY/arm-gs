# -*- coding: utf-8 -*-
"""Комментарии колонок gs_eco по актуальным моделям (мазут, единицы, связи).

Revision ID: w9x0y1z2a3b4
Revises: v8w9x0y1z2a3
Create Date: 2026-09-08
"""
import os
import sys

from alembic import op
from sqlalchemy import text

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "w9x0y1z2a3b4"
down_revision = "v8w9x0y1z2a3"
branch_labels = None
depends_on = None

SCHEMA_ECO = "gs_eco"

_COMMON = {
    "id": "Уникальный идентификатор записи",
    "created_by": "Пользователь, создавший запись",
    "modified_by": "Пользователь, последним изменивший запись",
    "created_at": "Дата и время создания записи",
    "updated_at": "Дата и время последнего изменения записи",
    "database_version_id": "Версия базы данных, FK -> gs_sys.gs_database_versions",
    "note": "Примечание",
}

_TABLE_COMMENTS = {
    "gs_eco_gis_tek_greenhouse_gas_params": (
        "Отчетные данные ГИС ТЭК: парниковые газы (ПГ)"
    ),
    "gs_eco_gis_tek_pollutant_params": (
        "Отчетные данные ГИС ТЭК: загрязняющие вещества (ЗВ)"
    ),
    "gs_eco_analysis_pg_params": (
        "Параметры анализа ПГ: выверенная копия отчетных данных ГИС ТЭК "
        "для страниц pg-vse / pg-bez-kot"
    ),
    "gs_eco_operating_tes_fuel_chars": (
        "Характеристики топлива для расчёта выбросов действующих ТЭС (лист «Хар.топл.»)"
    ),
    "gs_eco_operating_tes_coefficients": (
        "КПД очистки и коэффициенты подавления (лист «Коэфф.»)"
    ),
    "gs_eco_operating_tes_inputs": (
        "Сохранённые значения ввода расчёта по действующим ТЭС "
        "(топливо, выработка, тепло)"
    ),
    "gs_eco_operating_tes_formula_texts": (
        "Переопределения текстов формул (подсказки «i») расчёта по действующим ТЭС"
    ),
}

_COLUMN_COMMENTS: dict[str, dict[str, str]] = {
    "gs_eco_gis_tek_greenhouse_gas_params": {
        **_COMMON,
        "station_numb": (
            "Код группы оборудования: station_numb (numb1120) = EquipmentGroup.numb "
            "(без FK — numb не уникален)"
        ),
        "gis_tek_station_name": "Электростанция (ГИС ТЭК), наименование из файла",
        "station_type": "Тип станции (КЭС, ТЭЦ и т.п.)",
        "equipment_group_id": (
            "Группа оборудования (Топливо), FK -> gs_fue.gs_fue_equipment_groups"
        ),
        "year_number": "Год: Year.number + database_version_id (composite FK)",
        "gas_consumption_tce": "Расход газа, тут",
        "co2_from_gas_t": "Выбросы СО2 от сжигания газа, т",
        "oil_fuel_consumption_tce": "Расход мазута, тут",
        "co2_from_oil_fuel_t": "Выбросы СО2 от сжигания мазута, т",
        "solid_fuel_consumption_tce": "Расход твердого топлива, тут",
        "co2_from_solid_fuel_t": "Выбросы СО2 от сжигания твердого топлива, т",
    },
    "gs_eco_gis_tek_pollutant_params": {
        **_COMMON,
        "station_numb": (
            "Код группы оборудования: station_numb (numb1120) = EquipmentGroup.numb "
            "(без FK — numb не уникален)"
        ),
        "gis_tek_station_name": "Электростанция (ГИС ТЭК), наименование из файла",
        "station_type": "Тип станции (КЭС, ТЭЦ и т.п.)",
        "equipment_group_id": (
            "Группа оборудования (Топливо), FK -> gs_fue.gs_fue_equipment_groups"
        ),
        "year_number": "Год: Year.number + database_version_id (composite FK)",
        "solid_substances": "Твердые вещества, т",
        "gaseous_and_liquid": "Газообразные и жидкие вещества, т",
        "sulfur_dioxide": "Диоксид серы, т",
        "carbon_monoxide": "Оксид углерода [CO], т",
        "nitrogen_oxides": "Оксиды азота [в пересчете на NO2], т",
        "hydrocarbons": "Углеводороды [без летучих органических соединений], т",
        "voc": "Летучие органические соединения [ЛОС], т",
        "other_gaseous_and_liquid": "В т.ч. прочие газообразные и жидкие, т",
    },
    "gs_eco_analysis_pg_params": {
        **_COMMON,
        "sheet_slug": "Страница анализа: pg-vse или pg-bez-kot",
        "station_numb": (
            "Код группы оборудования: station_numb (numb1120) = EquipmentGroup.numb "
            "(без FK — numb не уникален)"
        ),
        "year_number": "Год: Year.number + database_version_id (composite FK)",
        "gas_consumption_tce": "Расход газа, тут (GAZ_ek)",
        "co2_from_gas_t": "Выбросы СО2 от сжигания газа, т (CO2_gaz)",
        "oil_fuel_consumption_tce": "Расход мазута, тут (MAZUT_ek)",
        "co2_from_oil_fuel_t": "Выбросы СО2 от сжигания мазута, т (CO2_mazut)",
        "solid_fuel_consumption_tce": "Расход твердого топлива, тут (TvTopl_ek)",
        "co2_from_solid_fuel_t": (
            "Выбросы СО2 от сжигания твердого топлива, т (CO2_ugol)"
        ),
    },
    "gs_eco_operating_tes_fuel_chars": {
        **_COMMON,
        "fuel_key": "Ключ вида топлива (gas_natural, mazut, donetsk, …)",
        "year_number": "Год: Year.number + database_version_id (composite FK)",
        "ash": "Зольность Ар, %",
        "ash_share": "Доля золы аун, д.ед.",
        "q_mech": "Потери тепла от механической неполноты сгорания qч, %",
        "sulfur": "Сернистость Sp, %",
        "sulfur_share": "Доля оксидов серы x, д.ед.",
        "qh_kj": "Низшая теплота сгорания QH, кДж/кг",
        "qh_kcal": "Низшая теплота сгорания QH, ккал/кг",
        "bj": "Удельный выброс оксидов азота bj, кг/тут",
        "k_co2": "Национальный коэффициент эмиссии CO2 (KCO2), т/тут",
        "r_chem": "Коэффициент доли потери тепла от химической неполноты сгорания R, %",
        "q_chem": "Потери тепла от химической неполноты сгорания q3, %",
        "tut_per_t": "Коэффициент перевода в условное топливо, тут/т",
        "tj_per_kt": "Энергосодержание, ТДж/тыс. т натур. топлива",
        "t_co2_per_tj": "Коэффициент эмиссии CO2, т СО2/ТДж",
        "k_natural": "Коэффициент перехода к натуральному топливу (ГИСТЭК 27-30), д.ед.",
    },
    "gs_eco_operating_tes_coefficients": {
        **_COMMON,
        "territory_slug": "Идентификатор территории (vsego, minen, severo-zapad, …)",
        "year_number": "Год: Year.number + database_version_id (composite FK)",
        "kind": (
            "Вид: ash_eta (КПД золоулавливания), sulfur_eta (КПД сероочистки), "
            "nox_n / co_k / pg_k (коэф. подавления)"
        ),
        "value": "Значение КПД или коэффициента подавления, д.ед. (0–1)",
    },
    "gs_eco_operating_tes_inputs": {
        **_COMMON,
        "territory_slug": "Идентификатор территории (vsego, minen, severo-zapad, …)",
        "year_number": "Год: Year.number + database_version_id (composite FK)",
        "row_key": "Ключ строки: вид топлива, ee_generation, heat_output, fuel_total",
        "value": (
            "Значение: топливо — тыс. тут; выработка ЭЭ — млрд.кВтч; "
            "отпуск тепла — тыс.Гкал"
        ),
    },
    "gs_eco_operating_tes_formula_texts": {
        "id": "Уникальный идентификатор записи",
        "formula_key": "Ключ формулы (иконка «i» на страницах расчёта)",
        "formula_text": "Текст формулы (подсказка; на расчёт ячеек не влияет)",
        "created_by": "Пользователь, создавший запись",
        "modified_by": "Пользователь, последним изменивший запись",
        "created_at": "Дата и время создания записи",
        "updated_at": "Дата и время последнего изменения записи",
    },
}

_DOWN_TABLE_COMMENTS = {
    "gs_eco_gis_tek_greenhouse_gas_params": (
        "Отчетные данные ГИС ТЭК: парниковые газы (ПГ)"
    ),
    "gs_eco_gis_tek_pollutant_params": (
        "Отчетные данные ГИС ТЭК: загрязняющие вещества (ЗВ)"
    ),
    "gs_eco_analysis_pg_params": (
        "Параметры анализа ПГ: выверенная копия отчетных данных ГИС ТЭК "
        "для страниц pg-vse / pg-bez-kot"
    ),
    "gs_eco_operating_tes_fuel_chars": (
        "Характеристики топлива расчёта по действующим ТЭС (Хар.топл.)"
    ),
    "gs_eco_operating_tes_coefficients": (
        "КПД очистки и коэффициенты подавления (лист Коэфф.)"
    ),
    "gs_eco_operating_tes_inputs": (
        "Переопределения ввода расчёта по действующим ТЭС (топливо, выработка, тепло)"
    ),
}

_DOWN_COLUMN_COMMENTS: dict[str, dict[str, str | None]] = {
    "gs_eco_gis_tek_greenhouse_gas_params": {
        **_COMMON,
        "database_version_id": "Версия базы данных (FK -> gs_sys.gs_database_versions)",
        "station_numb": (
            "№_станции из ГИС ТЭК; связь с группой оборудования (Топливо) по numb"
        ),
        "gis_tek_station_name": "Электростанция (ГИС ТЭК) — наименование из файла",
        "station_type": "Тип станции из файла ГИС ТЭК",
        "equipment_group_id": (
            "Группа оборудования (Топливо), FK -> gs_fue.gs_fue_equipment_groups"
        ),
        "year_number": "Год (связь с gs_sys.gs_sys_years по number и database_version_id)",
        "gas_consumption_tce": "Расход газа, тут",
        "co2_from_gas_t": "Выбросы СО2 от сжигания газа, т",
        "oil_fuel_consumption_tce": "Расход нефтетоплива, тут",
        "co2_from_oil_fuel_t": "Выбросы СО2 от сжигания нефтетоплива, т",
        "solid_fuel_consumption_tce": "Расход твердого топлива, тут",
        "co2_from_solid_fuel_t": "Выбросы СО2 от сжигания твердого топлива, т",
    },
    "gs_eco_gis_tek_pollutant_params": {
        **_COMMON,
        "database_version_id": "Версия базы данных (FK -> gs_sys.gs_database_versions)",
        "station_numb": (
            "№_станции из ГИС ТЭК; связь с группой оборудования (Топливо) по numb"
        ),
        "gis_tek_station_name": "Электростанция (ГИС ТЭК) — наименование из файла",
        "station_type": "Тип станции из файла ГИС ТЭК",
        "equipment_group_id": (
            "Группа оборудования (Топливо), FK -> gs_fue.gs_fue_equipment_groups"
        ),
        "year_number": "Год (связь с gs_sys.gs_sys_years по number и database_version_id)",
        "solid_substances": "Твердые вещества",
        "gaseous_and_liquid": "Газообразные и жидкие вещества",
        "sulfur_dioxide": "диоксид серы",
        "carbon_monoxide": "оксид углерода [CO]",
        "nitrogen_oxides": "оксиды азота [в пересчете на NO2]",
        "hydrocarbons": "углеводороды [без летучих органических соединений]",
        "voc": "летучие органические соединения [ЛОС]",
        "other_gaseous_and_liquid": "прочие газообразные и жидкие",
    },
    "gs_eco_analysis_pg_params": {
        **_COMMON,
        "database_version_id": "Версия базы данных (FK -> gs_sys.gs_database_versions)",
        "sheet_slug": "Страница анализа: pg-vse или pg-bez-kot",
        "station_numb": "Код группы оборудования (numb1120), связь с отчетными ПГ",
        "year_number": "Год (связь с gs_sys.gs_sys_years по number и database_version_id)",
        "gas_consumption_tce": "Израсходовано газа, тут (GAZ_ek ← Расход газа)",
        "co2_from_gas_t": "Выброшено ПГ от газа, т (CO2_gaz ← Выбросы СО2 от сжигания газа)",
        "oil_fuel_consumption_tce": "Израсходовано мазута, тут (MAZUT_ek ← Расход нефтетоплива)",
        "co2_from_oil_fuel_t": (
            "Выброшено ПГ от мазута, т (CO2_mazut ← Выбросы СО2 от сжигания нефтетоплива)"
        ),
        "solid_fuel_consumption_tce": (
            "Израсходовано твердого топлива, тут (TvTopl_ek ← Расход твердого топлива)"
        ),
        "co2_from_solid_fuel_t": (
            "Выброшено ПГ от твердого топлива, т "
            "(CO2_ugol ← Выбросы СО2 от сжигания твердого топлива)"
        ),
    },
    "gs_eco_operating_tes_fuel_chars": {
        col: None
        for col in (
            *_COMMON,
            "fuel_key",
            "year_number",
            "ash",
            "ash_share",
            "q_mech",
            "sulfur",
            "sulfur_share",
            "qh_kj",
            "qh_kcal",
            "bj",
            "k_co2",
            "r_chem",
            "q_chem",
            "tut_per_t",
            "tj_per_kt",
            "t_co2_per_tj",
            "k_natural",
        )
    },
    "gs_eco_operating_tes_coefficients": {
        col: None
        for col in (*_COMMON, "territory_slug", "year_number", "kind", "value")
    },
    "gs_eco_operating_tes_inputs": {
        col: None
        for col in (*_COMMON, "territory_slug", "year_number", "row_key", "value")
    },
    "gs_eco_operating_tes_formula_texts": {
        col: None
        for col in (
            "id",
            "formula_key",
            "formula_text",
            "created_by",
            "modified_by",
            "created_at",
            "updated_at",
        )
    },
}


def _comment_on_table(conn, schema: str, table: str, comment: str | None) -> None:
    if not column_utils.table_exists(conn, schema, table):
        return
    conn.execute(
        text(f'COMMENT ON TABLE "{schema}"."{table}" IS :comment'),
        {"comment": comment},
    )


def _comment_on_column(
    conn, schema: str, table: str, column: str, comment: str | None
) -> None:
    if not column_utils.table_has_column(conn, schema, table, column):
        return
    conn.execute(
        text(f'COMMENT ON COLUMN "{schema}"."{table}"."{column}" IS :comment'),
        {"comment": comment},
    )


def _apply(
    conn,
    table_comments: dict[str, str],
    column_comments: dict[str, dict[str, str | None]],
) -> None:
    for table, comment in table_comments.items():
        _comment_on_table(conn, SCHEMA_ECO, table, comment)
    for table, comments in column_comments.items():
        for column, comment in comments.items():
            _comment_on_column(conn, SCHEMA_ECO, table, column, comment)


def upgrade():
    _apply(op.get_bind(), _TABLE_COMMENTS, _COLUMN_COMMENTS)


def downgrade():
    _apply(op.get_bind(), _DOWN_TABLE_COMMENTS, _DOWN_COLUMN_COMMENTS)
    _comment_on_table(op.get_bind(), SCHEMA_ECO, "gs_eco_operating_tes_formula_texts", None)

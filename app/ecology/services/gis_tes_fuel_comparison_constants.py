# -*- coding: utf-8 -*-
"""Сопоставление данных ГИС ТЭС и Топливо (макет «Данные по ЗВ и ПГ»)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

SKIP_SHEET_NAME = "Лист1"
DEFAULT_SHEET_SLUG = "zv-vse"
COMPARISON_GROUP_ZV = "zv"
COMPARISON_GROUP_PG = "pg"
YEAR_COL_INDEX = 5
STICKY_COL_COUNT = 4
DEFAULT_PER_PAGE = 25
UNSPECIFIED_LEVEL_NAME = "Не указано"
HIDDEN_TABLE_COLUMN_KEYS = frozenset(
    {
        "Fed_okr",
        "nameoes",
        "oblname",
        "oblast",
        "SF6",
        "BLST",
        "Gen_komp",
        "c32",
        "OBOR",
        "obor",
    }
)
# Столбцы «отчитавшихся»: на /ecology/analysis/zv-vse/ скрыты, пока не нажата кнопка.
REPORTED_TABLE_COLUMN_KEYS = frozenset(
    {
        "nust_vibr",
        "W_en_vibr",
        "Teplo_vibr",
        "VIBR_cnt",
    }
)
STICKY_COLUMN_KEYS = frozenset({"NAME", "Stancia", "numb1120", "Year"})
TERRITORY_FILTER_KEYS = (
    "energy_system_type_filter",
    "union_energy_system_filter",
    "regional_energy_system_filter",
    "federal_district_filter",
    "regional_district_filter",
    "station_name_filter",
    "gen_company_filter",
)

# Фильтр VED (ТЭП): группы для страниц анализа.
VED_FILTER_INDUSTRY = "industry"  # станции отрасли: ved 1, 2
VED_FILTER_INDUSTRIAL = "industrial"  # станции промпредприятий: ved 3, 4
VED_FILTER_OPTIONS: tuple[tuple[str, str], ...] = (
    (VED_FILTER_INDUSTRY, "Станции отрасли"),
    (VED_FILTER_INDUSTRIAL, "Станции промпредприятий"),
)
VED_FILTER_TO_VALUES: dict[str, frozenset[int]] = {
    VED_FILTER_INDUSTRY: frozenset({1, 2}),
    VED_FILTER_INDUSTRIAL: frozenset({3, 4}),
}

BUNDLED_XLSX_NAME = "zv_pg_2017_2023.xlsx"
NETWORK_XLSX_PATH = Path(
    r"z:\НИО-10\АРМ ГС\Шаблоны для АРМ ГС\9. Экология\Макет"
    r"\Модуль анализа данных\Данные по ЗВ и ПГ 2017-2023 гг.xlsx"
)

COMPARISON_SHEETS: tuple[dict[str, Any], ...] = (
    {
        "slug": "zv-vse",
        "excel_name": "ЗВ_всё",
        "sheet_name": "ЗВ_всё",
        "nav_label": "С котельными",
        "page_title": "Загрязняющие вещества (с котельными)",
        "group": COMPARISON_GROUP_ZV,
    },
    {
        "slug": "pg-vse",
        "excel_name": "ПГ_всё",
        "sheet_name": "ПГ_всё",
        "nav_label": "С котельными",
        "page_title": "Парниковые газы (с котельными)",
        "group": COMPARISON_GROUP_PG,
    },
    {
        "slug": "zv-bez-kot",
        "excel_name": "ЗВ_без кот",
        "sheet_name": "ЗВ_без кот",
        "nav_label": "Без котельных",
        "page_title": "Загрязняющие вещества (без котельных)",
        "group": COMPARISON_GROUP_ZV,
    },
    {
        "slug": "pg-bez-kot",
        "excel_name": "ПГ_без кот",
        "sheet_name": "ПГ_без кот",
        "nav_label": "Без котельных",
        "page_title": "Парниковые газы (без котельных)",
        "group": COMPARISON_GROUP_PG,
    },
)

COMPARISON_GROUPS: tuple[dict[str, Any], ...] = (
    {
        "slug": COMPARISON_GROUP_PG,
        "title": "Сопоставление данных Парниковые газы (ПГ)",
        "default_sheet_slug": "pg-vse",
    },
    {
        "slug": COMPARISON_GROUP_ZV,
        "title": "Сопоставление данных Загрязняющие вещества (ЗВ)",
        "default_sheet_slug": "zv-vse",
    },
)

KEY_LABELS: dict[str, str] = {
    "Fed_okr": "Федеральный округ",
    "nameoes": "ОЭС",
    "oblname": "Субъект Федерации",
    "oblast": "Субъект Федерации",
    "NAME": "Электростанция",
    "Stancia": "Электростанция",
    "numb1120": "Код группы оборудования (numb1120)",
    "Year": "Год",
    "nust": "Установленная мощность, МВт",
    "NUST": "Установленная мощность, МВт",
    "nust_vibr": "Уст. мощность отчитавшихся, МВт",
    "W_en": "Выработка электроэнергии, млн. кВт.ч",
    "W_en_vibr": "Выработка отчитавшихся, млн. кВт.ч",
    "Teplo": "Отпущенно тепла, тыс. Гкалл",
    "Teplo_vibr": "Тепло отчитавшихся, тыс. Гкалл",
    "VIBROS_ekol": "всего",
    "VIBR_cnt": "Количество отчитавшихся",
    "TVERD_V": "Твердые вещества",
    "GAZ and ZHID": "всего",
    "SO2_gaz": "диоксид серы",
    "CO_gaz": "оксид углерода [CO]",
    "NOx_gaz": "оксиды азота [в пересчете на NO2]",
    "UGLEVOD": "углеводороды [без летучих органических соединений]",
    "LOS": "летучие органические соединения [ЛОС]",
    "PROCH_ekol": "прочие газообразные и жидкие",
    "BLST": "Принадлежность",
    "GAZ_6tp": "газ",
    "GAZ_All": "Расход газа, всего, т у.т.",
    "GAZ_estestv": "газ естественный",
    "GAZ_ESTEST": "в т.ч. расход газа естественного, т у.т.",
    "GAZ_ek": "Расход газа, т у.т.",
    "d_gaz": "Разность по газу, т у.т.",
    "CO2_gaz": "Выбросы СО2 от сжигания газа, т",
    "K_gaz_ek": "Коэффициент эмиссии (газ)",
    "MAZUT_6tp": "мазут",
    "MAZUT_ek": "Расход мазута, т у.т.",
    "d_mazut": "Разность по мазуту, т у.т.",
    "CO2_mazut": "Выбросы СО2 от сжигания мазута, т",
    "K_mazut_ek": "Коэффициент эмиссии (мазут)",
    "TVERD_TOPL_6tp": "твердое топливо",
    "TvTopl_6tp": "Расход твердого топлива, т у.т.",
    "TvTopl_ek": "Расход твердого топлива, т у.т.",
    "d_tv": "Разность по твердому топливу, т у.т.",
    "CO2_ugol": "Выбросы СО2 от сжигания твердого топлива, т",
    "K_ugol_ek": "Коэффициент эмиссии (твердое)",
    "PROCH_6tp": "Расход прочих видов топлива, т у.т.",
    "ZV_normir": "Итого ЗВ по нормируемым ингредиентам",
    "energy": "Приведенная энергия, млн. кВт.ч",
    "udel_tv": "Удельные твердое, кг/т у.т.",
    "udel_SO2": "Удельные сера, кг/т у.т.",
    "udel_NOx": "Удельные азот, кг/т у.т.",
    "udel_na_energ": "Удельные на приведенную, г/кВт.ч",
    "normir_ZV_na_ee": "на выработку электроэнергии",
    "normir_ZV_na_energ": "Нормируемые ЗВ на приведенную, г/кВт.ч",
    "normir_TVERD_na_energ": "Нормируемые твердые на приведенную, г/кВт.ч",
    "normir_SO2_na_energ": "Нормируемые сера на приведенную, г/кВт.ч",
    "normir_NOx_na_energ": "Нормируемые азот на приведенную, г/кВт.ч",
    "CO2": "Выброшено ПГ всего, т",
    "UD_CO2_ek": "Удельные выбросы ПГ на единицу топлива, кг/т у.т.",
    "UD_CO2_ener": "Удельные выбросы ПГ на единицу энергии, г/кВт.ч",
    "SF6": "SF6",
    "Gen_komp": "Генерирующая компания",
    "obor": "код оборудования",
    "OBOR": "код оборудования",
}

# Столбец таблицы → ключ текста формулы (иконка «i» и /ecology/formulas/).
COLUMN_FORMULA_KEYS: dict[str, str] = {
    "d_mazut": "d_mazut",
    "d_gaz": "d_gaz",
    "d_tv": "d_tv",
    "K_gaz_ek": "K_gaz_ek",
    "K_mazut_ek": "K_mazut_ek",
    "K_ugol_ek": "K_ugol_ek",
    "CO2": "CO2",
    "UD_CO2_ek": "UD_CO2_ek",
    "UD_CO2_ener": "UD_CO2_ener",
}
ZV_COLUMN_FORMULA_KEYS: dict[str, str] = {
    "VIBROS_ekol": "zv_total",
    "GAZ and ZHID": "gaseous_and_liquid",
    "energy": "zv_brought_energy",
    "ZV_normir": "zv_normir",
    "udel_na_energ": "zv_udel_na_energ",
    "normir_ZV_na_ee": "zv_normir_na_ee",
    "normir_ZV_na_energ": "zv_normir_na_energ",
    "normir_TVERD_na_energ": "zv_normir_tverd_na_energ",
    "normir_SO2_na_energ": "zv_normir_so2_na_energ",
    "normir_NOx_na_energ": "zv_normir_nox_na_energ",
    "udel_tv": "zv_udel_tv",
    "udel_SO2": "zv_udel_so2",
    "udel_NOx": "zv_udel_nox",
}
ZV_GAS_FUEL_KEYS = frozenset({"GAZ_6tp", "GAZ_All"})
ZV_MAZUT_FUEL_KEYS = frozenset({"MAZUT_6tp"})
ZV_SOLID_FUEL_KEYS = frozenset({"TVERD_TOPL_6tp", "TvTopl_6tp"})
ZV_EE_SPECIFIC_KEY = "normir_ZV_na_ee"
ZV_EE_SPECIFIC_AFTER_KEY = "udel_na_energ"
DIFF_HIGHLIGHT_COLUMN_KEYS = frozenset({"d_mazut", "d_gaz", "d_tv"})
# Расчётные столбцы: только на лету (не из Excel / не хранятся в PGParamCalc).
PG_DERIVED_COLUMN_KEYS = frozenset(COLUMN_FORMULA_KEYS)
# «Коэффициент эмиссии»: округляются отдельным селектором «Округл (k эмис)».
EMISSION_COEFFICIENT_COLUMN_KEYS = frozenset({"K_gaz_ek", "K_mazut_ek", "K_ugol_ek"})
# «Удельные» столбцы ЗВ: округляются отдельным селектором «Округл (удельные)».
ZV_SPECIFIC_ROUNDING_COLUMN_KEYS = frozenset(
    {
        # Удельные выбросы нормируемых ЗВ по ингредиентам, кг/т у.т.
        "udel_tv",
        "udel_SO2",
        "udel_NOx",
        # Удельные по электрической энергии, г/кВтч
        "udel_na_energ",
        "normir_ZV_na_ee",
        "normir_ZV_na_energ",
        "normir_TVERD_na_energ",
        "normir_SO2_na_energ",
        "normir_NOx_na_energ",
    }
)

# Поля макета, которые на странице берутся из ТЭП группы оборудования (numb1120 + Year).
FUEL_OVERLAY_BY_KEY: dict[str, str] = {
    "Fed_okr": "federal_district",
    "nameoes": "ues",
    "oblname": "regional_district",
    "oblast": "regional_district",
    "NAME": "station_name",
    "Stancia": "station_name",
    "nust": "nust",
    "NUST": "nust",
    "W_en": "e",
    "Teplo": "q",
}

# Расход топлива из ТЭП: в БД тыс. т у.т. → на странице т у.т. (×1000).
FUEL_TCE_OVERLAY_BY_KEY: dict[str, str] = {
    "TvTopl_6tp": "ugol_tce",
    "TVERD_TOPL_6tp": "solid_tce",
    "MAZUT_6tp": "mazut_tce",
    "GAZ_6tp": "gaz_all_tce",
    "GAZ_All": "gaz_all_tce",
    "GAZ_ESTEST": "gaz_estest_tce",
    "GAZ_estestv": "gaz_estest_tce",
    "PROCH_6tp": "proch_tce",
}

# Подписи столбцов расхода топлива из ТЭП (код Access — отдельно, как на fuel params).
FUEL_TCE_HEADER_META: dict[str, dict[str, str]] = {
    "GAZ_All": {"label": "Расход газа, всего, т у.т.", "access_code": "GAZ + ISK_GAZ"},
    "GAZ_6tp": {"label": "газ", "access_code": "GAZ + ISK_GAZ"},
    "GAZ_ESTEST": {"label": "в т.ч. расход газа естественного, т у.т.", "access_code": "GAZ"},
    "GAZ_estestv": {"label": "газ естественный", "access_code": "GAZ"},
    "MAZUT_6tp": {"label": "мазут", "access_code": "MAZUT"},
    "TvTopl_6tp": {"label": "Расход твердого топлива, т у.т.", "access_code": "UGOL"},
    "TVERD_TOPL_6tp": {"label": "твердое топливо", "access_code": "UGOL + TORF"},
    "PROCH_6tp": {"label": "Расход прочих видов топлива, т у.т.", "access_code": "PROCH"},
}
FUEL_TCE_HEADER_LABELS: dict[str, str] = {
    key: meta["label"] for key, meta in FUEL_TCE_HEADER_META.items()
}

# Nust / W_en / Teplo: подписи и серый фон шапки как на stations_equipment_group_fuel_params.
FUEL_TEP_HEADER_KEYS = frozenset({"nust", "NUST", "W_en", "Teplo"})

# Приведённая энергия: 1 кВт·ч ≈ 859,8 ккал → тыс. Гкал / 859,8 · 1000 = млн кВт·ч.
KCAL_PER_KWH = 859.8

# Страницы анализа ПГ: параметры (PGParamCalc) / отчётные ПГ (PGReportGisTek).
PG_ANALYSIS_SHEET_SLUGS = frozenset({"pg-vse", "pg-bez-kot"})
ZV_ANALYSIS_SHEET_SLUGS = frozenset({"zv-vse", "zv-bez-kot"})
ANALYSIS_SHEET_SLUGS = PG_ANALYSIS_SHEET_SLUGS | ZV_ANALYSIS_SHEET_SLUGS
BEZ_KOT_SHEET_SLUGS = frozenset({"pg-bez-kot", "zv-bez-kot"})
# Страницы «С котельными»: котельные показываем только в составе станции (main не пуст/0).
VSE_SHEET_SLUGS = frozenset({"pg-vse", "zv-vse"})
# Порядок витрины ЗВ: пары ключей Excel, которые меняются местами.
ZV_DISPLAY_COLUMN_SWAPS: tuple[tuple[str, str], ...] = (
    ("VIBROS_ekol", "VIBR_cnt"),
)

# Сверка с модулем «Генерация» на вкладках «С котельными»: станционные
# «Руст, МВт» и «Выработка ЭЭ, млн кВтч (Генерация)» из карточки станции.
STATION_GENERATION_SHEET_SLUGS = VSE_SHEET_SLUGS
STATION_RUST_COLUMN_KEY = "nust_generation"
STATION_GENERATION_COLUMN_KEY = "W_en_generation"
# (новый столбец, подпись, столбцы макета: после первого найденного вставляем и с ним сверяем)
STATION_GENERATION_COLUMNS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (STATION_RUST_COLUMN_KEY, "Руст, МВт", ("NUST", "nust")),
    (STATION_GENERATION_COLUMN_KEY, "Выработка ЭЭ, млн кВтч (Генерация)", ("W_en",)),
)
STATION_GENERATION_COLUMN_KEYS = frozenset(
    key for key, _header, _macro_keys in STATION_GENERATION_COLUMNS
)
STATION_GENERATION_COLUMN_LABELS: dict[str, str] = {
    key: header for key, header, _macro_keys in STATION_GENERATION_COLUMNS
}
# Станция группы оборудования не привязана в модуле «Генерация» (как на /ecology/gis_tek/).
GENERATION_STATION_UNKNOWN_NAME = "—"

# Столбец «Принадлежность» на вкладках «С котельными»: отрасль / промпредприятие
# по коду VED строки «Топливо» — те же значения, что на страницах ГИС ТЭК.
STATION_AFFILIATION_SHEET_SLUGS = VSE_SHEET_SLUGS
STATION_AFFILIATION_COLUMN_KEY = "station_affiliation"
STATION_AFFILIATION_LABEL = "Принадлежность"
# Вставляется сразу после «Отпуск ТЭ, тыс.Гкал» (Q).
STATION_AFFILIATION_AFTER_KEY = "Teplo"
# Нет данных ГИС ТЭК — то же значение, что в столбце на страницах ГИС ТЭК.
STATION_AFFILIATION_UNKNOWN = "—"

# Шапка ЗВ как на /ecology/gis_tek/pollutants/: группа + «всего» = сумма слагаемых.
ZV_GASEOUS_TOTAL_KEY = "GAZ and ZHID"
ZV_SOLID_KEY = "TVERD_V"
ZV_TOTAL_KEY = "VIBROS_ekol"
ZV_GASEOUS_PART_KEYS: tuple[str, ...] = (
    "SO2_gaz",
    "CO_gaz",
    "NOx_gaz",
    "UGLEVOD",
    "LOS",
    "PROCH_ekol",
)
ZV_EXCEL_KEY_BY_GIS_TEK_ATTR: dict[str, str] = {
    "gaseous_and_liquid": ZV_GASEOUS_TOTAL_KEY,
    "sulfur_dioxide": "SO2_gaz",
    "carbon_monoxide": "CO_gaz",
    "nitrogen_oxides": "NOx_gaz",
    "hydrocarbons": "UGLEVOD",
    "voc": "LOS",
    "other_gaseous_and_liquid": "PROCH_ekol",
}

# Отчётные ЗВ (ZVReportGisTek) → ключи Excel. Итоги «всего» считаются на странице.
ZV_ECOLOGY_OVERLAY_BY_KEY: dict[str, str] = {
    "TVERD_V": "solid_substances",
    "SO2_gaz": "sulfur_dioxide",
    "CO_gaz": "carbon_monoxide",
    "NOx_gaz": "nitrogen_oxides",
    "UGLEVOD": "hydrocarbons",
    "LOS": "voc",
    "PROCH_ekol": "other_gaseous_and_liquid",
}
ZV_ECOLOGY_VALUE_FIELDS: tuple[str, ...] = tuple(
    dict.fromkeys(ZV_ECOLOGY_OVERLAY_BY_KEY.values())
)
# Столбцы ЗВ, которые можно править на страницах анализа (ZVParamCalc).
ZV_ECOLOGY_EDITABLE_KEYS = frozenset(ZV_ECOLOGY_OVERLAY_BY_KEY)
# После правки столбца пересчитываем итоги и удельные (как на странице).
ZV_ECOLOGY_EDIT_RELATED_KEYS: dict[str, tuple[str, ...]] = {
    key: (key,) + tuple(ZV_COLUMN_FORMULA_KEYS)
    for key in ZV_ECOLOGY_OVERLAY_BY_KEY
}

# Верхняя строка шапки ПГ: объединение столбцов вместо «Отчет» / «Макет Экология».
# NUST / W_en / Teplo не группируются — ячейки тянутся на всю высоту шапки.
PG_FUEL_HEADER_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Газ", ("GAZ_All", "GAZ_ESTEST", "GAZ_ek", "d_gaz", "CO2_gaz", "K_gaz_ek")),
    ("Мазут", ("MAZUT_6tp", "MAZUT_ek", "d_mazut", "CO2_mazut", "K_mazut_ek")),
    ("Твердое топливо", ("TvTopl_6tp", "TvTopl_ek", "d_tv", "CO2_ugol", "K_ugol_ek")),
)
PG_FUEL_HEADER_GROUP_KEYS: frozenset[str] = frozenset(
    key for _title, keys in PG_FUEL_HEADER_GROUPS for key in keys
)
PG_DIFF_HEADER_KEYS = frozenset({"d_gaz", "d_mazut", "d_tv"})

# 2-я строка шапки ПГ: без привязки к виду топлива (вид — в 1-й строке групп).
PG_GENERIC_FUEL_LEAF_LABELS: dict[str, str] = {
    "GAZ_All": "Расход топлива, всего, т у.т.",
    "GAZ_6tp": "Расход топлива, всего, т у.т.",
    "GAZ_ESTEST": "в т.ч. расход газа естественного, т у.т.",
    "GAZ_ek": "Расход топлива, т у.т.",
    "d_gaz": "Разность по расходу топлива, т у.т.",
    "CO2_gaz": "Выбросы СО2 от сжигания топлива, т",
    "K_gaz_ek": "Коэффициент эмиссии",
    "MAZUT_6tp": "Расход топлива, т у.т.",
    "MAZUT_ek": "Расход топлива, т у.т.",
    "d_mazut": "Разность по расходу топлива, т у.т.",
    "CO2_mazut": "Выбросы СО2 от сжигания топлива, т",
    "K_mazut_ek": "Коэффициент эмиссии",
    "TvTopl_6tp": "Расход топлива, т у.т.",
    "TvTopl_ek": "Расход топлива, т у.т.",
    "d_tv": "Разность по расходу топлива, т у.т.",
    "CO2_ugol": "Выбросы СО2 от сжигания топлива, т",
    "K_ugol_ek": "Коэффициент эмиссии",
}

# Столбец макета ← поле отчета/параметра ПГ (те же семантики, что на /ecology/gis_tek/pg/).
PG_ECOLOGY_OVERLAY_BY_KEY: dict[str, str] = {
    "GAZ_ek": "gas_consumption_tce",
    "CO2_gaz": "co2_from_gas_t",
    "MAZUT_ek": "oil_fuel_consumption_tce",
    "CO2_mazut": "co2_from_oil_fuel_t",
    "TvTopl_ek": "solid_fuel_consumption_tce",
    "CO2_ugol": "co2_from_solid_fuel_t",
}
PG_ECOLOGY_EDITABLE_KEYS = frozenset(PG_ECOLOGY_OVERLAY_BY_KEY)
PG_ECOLOGY_VALUE_FIELDS: tuple[str, ...] = tuple(
    dict.fromkeys(PG_ECOLOGY_OVERLAY_BY_KEY.values())
)
# После правки столбца пересчитываем все расчётные ячейки (d_*/K_*/CO2/UD_*).
PG_ECOLOGY_EDIT_RELATED_KEYS: dict[str, tuple[str, ...]] = {
    key: (key,) + tuple(COLUMN_FORMULA_KEYS)
    for key in (
        "GAZ_ek",
        "CO2_gaz",
        "MAZUT_ek",
        "CO2_mazut",
        "TvTopl_ek",
        "CO2_ugol",
    )
}


def pg_ecology_header_labels() -> dict[str, str]:
    """Подписи 2-й строки шапки ПГ без привязки к виду топлива."""
    return dict(PG_GENERIC_FUEL_LEAF_LABELS)


def zv_gaseous_header_group() -> tuple[str, tuple[str, ...], dict[str, str]]:
    """Группа шапки ЗВ: заголовок, ключи Excel, подписи как на gis_tek/pollutants."""
    from app.ecology.services.gis_tek_constants import ZV_VALUE_COLUMN_GROUPS

    for title, cols in ZV_VALUE_COLUMN_GROUPS:
        if title != "Газообразные и жидкие вещества":
            continue
        keys: list[str] = []
        labels: dict[str, str] = {}
        for attr, label in cols:
            excel_key = ZV_EXCEL_KEY_BY_GIS_TEK_ATTR.get(attr)
            if excel_key is None:
                continue
            keys.append(excel_key)
            labels[excel_key] = label
        if keys:
            return str(title), tuple(keys), labels
    return (
        "Газообразные и жидкие вещества",
        (ZV_GASEOUS_TOTAL_KEY,) + ZV_GASEOUS_PART_KEYS,
        {
            key: KEY_LABELS[key]
            for key in (ZV_GASEOUS_TOTAL_KEY,) + ZV_GASEOUS_PART_KEYS
            if key in KEY_LABELS
        },
    )


def zv_specific_emission_header_group() -> tuple[str, tuple[str, ...], dict[str, str]]:
    """Группа шапки: удельные выбросы нормируемых ЗВ по ингредиентам."""
    return (
        "Удельные выбросы нормируемых ЗВ по ингредиентам, кг/т у.т.",
        ("udel_tv", "udel_SO2", "udel_NOx"),
        {
            "udel_tv": "твердое топливо",
            "udel_SO2": "сера",
            "udel_NOx": "азот",
        },
    )


def zv_normir_ingredient_header_group() -> tuple[str, tuple[str, ...], dict[str, str]]:
    """Группа шапки: нормируемые ЗВ на приведённую энергию по ингредиентам."""
    return (
        "в том числе по ингредиентам",
        ("normir_TVERD_na_energ", "normir_SO2_na_energ", "normir_NOx_na_energ"),
        {
            "normir_TVERD_na_energ": "твердое топливо",
            "normir_SO2_na_energ": "сера",
            "normir_NOx_na_energ": "азот",
        },
    )


ZV_FUEL_CONSUMPTION_BANNER_TITLE = "Расход топлива, т у.т."
ZV_FUEL_CONSUMPTION_KEYS: tuple[str, ...] = (
    "GAZ_6tp",
    "GAZ_estestv",
    "MAZUT_6tp",
    "TVERD_TOPL_6tp",
)
ZV_FUEL_CONSUMPTION_LEAF_LABELS: dict[str, str] = {
    "GAZ_6tp": "газ",
    "GAZ_estestv": "газ естественный",
    "MAZUT_6tp": "мазут",
    "TVERD_TOPL_6tp": "твердое топливо",
}


def zv_fuel_consumption_header_group() -> tuple[str, tuple[str, ...], dict[str, str]]:
    """Группа шапки ЗВ: расход топлива из ТЭП (газ / газ естественный / мазут / твердое)."""
    return (
        ZV_FUEL_CONSUMPTION_BANNER_TITLE,
        ZV_FUEL_CONSUMPTION_KEYS,
        dict(ZV_FUEL_CONSUMPTION_LEAF_LABELS),
    )


def zv_leaf_header_groups() -> tuple[tuple[str, tuple[str, ...], dict[str, str]], ...]:
    """Группы нижней шапки ЗВ: топливо, газообразные, удельные и нормируемые по ингредиентам."""
    return (
        zv_fuel_consumption_header_group(),
        zv_gaseous_header_group(),
        zv_specific_emission_header_group(),
        zv_normir_ingredient_header_group(),
    )


def zv_emissions_banner_keys() -> tuple[str, ...]:
    """Ключи столбцов под общей шапкой «Всего выброшено в атмосферу ЗВ за год, т»."""
    _title, gaseous_keys, _labels = zv_gaseous_header_group()
    return (ZV_TOTAL_KEY, ZV_SOLID_KEY) + gaseous_keys


ZV_ENERGY_SPECIFIC_BANNER_TITLE = "Удельные по электрической энергии, г/кВтч"
ZV_ENERGY_SPECIFIC_LEAF_LABELS: dict[str, str] = {
    "udel_na_energ": "на приведенную (с учетом перевода отпуска тепла)",
    "normir_ZV_na_ee": "на выработку электроэнергии",
    "normir_ZV_na_energ": "нормируемые ЗВ на приведенную (с учетом перевода отпуска тепла)",
}


def zv_energy_specific_banner_keys() -> tuple[str, ...]:
    """Ключи под шапкой «Удельные по электрической энергии, г/кВтч»."""
    _title, ingredient_keys, _labels = zv_normir_ingredient_header_group()
    return (
        "udel_na_energ",
        ZV_EE_SPECIFIC_KEY,
        "normir_ZV_na_energ",
    ) + ingredient_keys


def bundled_xlsx_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / BUNDLED_XLSX_NAME


def get_comparison_sheet(slug: str) -> dict[str, Any] | None:
    needle = str(slug or "").strip()
    for item in COMPARISON_SHEETS:
        if item["slug"] == needle:
            return item
    return None


def list_comparison_sheets_for_group(group: str) -> list[dict[str, Any]]:
    needle = str(group or "").strip()
    return [item for item in COMPARISON_SHEETS if item["group"] == needle]

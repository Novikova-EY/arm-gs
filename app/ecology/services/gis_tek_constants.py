# -*- coding: utf-8 -*-
"""Константы отчетных данных ГИС ТЭК (ПГ / ЗВ)."""

from __future__ import annotations

REPORT_PG = "pg"
REPORT_ZV = "zv"

# Колонка «Тип станции» страниц ГИС ТЭК: тип станции по коду VED строки «Топливо»
# (подписи – как у FUEL_PARAM_VED_LABELS для кодов 1–4, без номера кода).
VED_STATION_TYPE_BY_CODE: dict[int, str] = {
    1: "КЭС, отрасль",
    2: "ТЭЦ, отрасль",
    3: "ТЭЦ, промпредприятия",
    4: "КЭС, промпредприятия",
}

# Колонка «Принадлежность»: та же группировка VED (1, 2 – отрасль; 3, 4 – промпредприятия).
VED_AFFILIATION_BY_CODE: dict[int, str] = {
    1: "отрасль",
    2: "отрасль",
    3: "промпредприятие",
    4: "промпредприятие",
}

SHEET_NAMES = {
    REPORT_PG: "СБОРКА ПГ",
    REPORT_ZV: "СБОРКА ЗВ",
}

PAGE_TITLES = {
    REPORT_PG: "Парниковые газы (ПГ) - отчетные данные ГИС ТЭС",
    REPORT_ZV: "Загрязняющие вещества (ЗВ) - отчетные данные ГИС ТЭС",
}

# Столбцы значений из Excel (attr, заголовок).
# «Всего» и «Газообразные и жидкие вещества» считаются на странице.
PG_VALUE_COLUMNS: list[tuple[str, str]] = [
    ("gas_consumption_tce", "Расход газа, т у.т."),
    ("co2_from_gas_t", "Выбросы СО2 от сжигания газа, т"),
    ("oil_fuel_consumption_tce", "Расход мазута, т у.т."),
    ("co2_from_oil_fuel_t", "Выбросы СО2 от сжигания мазута, т"),
    ("solid_fuel_consumption_tce", "Расход твердого топлива, т у.т."),
    ("co2_from_solid_fuel_t", "Выбросы СО2 от сжигания твердого топлива, т"),
]

# Расчётные итоги не входят в PG_VALUE_COLUMNS: при импорте нужны только исходные поля.
PG_TOTAL_COLUMNS: list[tuple[str, str]] = [
    ("total_fuel_consumption_tce", "Расход топлива, т у.т."),
    ("total_co2_from_fuel_t", "Выбросы СО2 от сжигания топлива, т"),
]
PG_TOTAL_PARTS: dict[str, tuple[str, ...]] = {
    "total_fuel_consumption_tce": (
        "gas_consumption_tce",
        "oil_fuel_consumption_tce",
        "solid_fuel_consumption_tce",
    ),
    "total_co2_from_fuel_t": (
        "co2_from_gas_t",
        "co2_from_oil_fuel_t",
        "co2_from_solid_fuel_t",
    ),
}

# Двухрядная шапка страницы ПГ: вид топлива в 1-й строке, общие подписи во 2-й.
PG_VALUE_COLUMN_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Газ",
        [
            ("gas_consumption_tce", "Расход топлива, т у.т."),
            ("co2_from_gas_t", "Выбросы СО2 от сжигания топлива, т"),
        ],
    ),
    (
        "Мазут",
        [
            ("oil_fuel_consumption_tce", "Расход топлива, т у.т."),
            ("co2_from_oil_fuel_t", "Выбросы СО2 от сжигания топлива, т"),
        ],
    ),
    (
        "Твердое топливо",
        [
            ("solid_fuel_consumption_tce", "Расход топлива, т у.т."),
            ("co2_from_solid_fuel_t", "Выбросы СО2 от сжигания топлива, т"),
        ],
    ),
    ("Всего", PG_TOTAL_COLUMNS),
]

ZV_VALUE_COLUMNS: list[tuple[str, str]] = [
    ("total", "всего"),
    ("solid_substances", "Твердые вещества"),
    ("gaseous_and_liquid", "всего"),
    ("sulfur_dioxide", "диоксид серы"),
    ("carbon_monoxide", "оксид углерода [CO]"),
    ("nitrogen_oxides", "оксиды азота [в пересчете на NO2]"),
    ("hydrocarbons", "углеводороды [без летучих органических соединений]"),
    ("voc", "летучие органические соединения [ЛОС]"),
    ("other_gaseous_and_liquid", "прочие газообразные и жидкие"),
]

# Верхняя строка шапки ЗВ: объединяет «всего», твёрдые и газообразные/жидкие.
ZV_EMISSIONS_BANNER_TITLE = "Всего выброшено в атмосферу ЗВ за год, т"

# Двухрядная шапка ЗВ под баннером: пустая 2-я подпись – столбец на всю высоту группы.
ZV_VALUE_COLUMN_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    ("всего", [("total", "")]),
    ("Твердые вещества", [("solid_substances", "")]),
    (
        "Газообразные и жидкие вещества",
        [
            ("gaseous_and_liquid", "всего"),
            ("sulfur_dioxide", "диоксид серы"),
            ("carbon_monoxide", "оксид углерода [CO]"),
            ("nitrogen_oxides", "оксиды азота [в пересчете на NO2]"),
            ("hydrocarbons", "углеводороды [без летучих органических соединений]"),
            ("voc", "летучие органические соединения [ЛОС]"),
            ("other_gaseous_and_liquid", "прочие газообразные и жидкие"),
        ],
    ),
]

# «Газообразные и жидкие вещества» – сумма слагаемых, не берётся из Excel.
ZV_GASEOUS_AND_LIQUID_PARTS: tuple[str, ...] = (
    "sulfur_dioxide",
    "carbon_monoxide",
    "nitrogen_oxides",
    "hydrocarbons",
    "voc",
    "other_gaseous_and_liquid",
)
ZV_TOTAL_PARTS: tuple[str, ...] = (
    "solid_substances",
    "gaseous_and_liquid",
)
ZV_DERIVED_ATTRS = frozenset({"gaseous_and_liquid", "total"})
ZV_UNSTORED_ATTRS = frozenset({"total"})
ZV_GASEOUS_AND_LIQUID_FORMULA_KEY = "gaseous_and_liquid"
ZV_TOTAL_FORMULA_KEY = "zv_total"

# Столбец «Нормируемые ЗВ» – сумма выбранных в шапке слагаемых (кроме столбцов «всего»).
# Показывается справа от столбцов ЗВ; в Excel выгружается, при импорте игнорируется.
ZV_NORM_ATTR = "norm_zv"
ZV_NORM_PARAM = "norm_zv"
ZV_NORM_LABEL = "Нормируемые ЗВ"
ZV_NORM_PARTS: tuple[str, ...] = (
    "solid_substances",
    "sulfur_dioxide",
    "carbon_monoxide",
    "nitrogen_oxides",
    "hydrocarbons",
    "voc",
    "other_gaseous_and_liquid",
)
# Набор по умолчанию: твёрдые вещества + диоксид серы + оксид углерода + оксиды азота.
ZV_NORM_DEFAULT_PARTS: tuple[str, ...] = (
    "solid_substances",
    "sulfur_dioxide",
    "carbon_monoxide",
    "nitrogen_oxides",
)

VALUE_COLUMNS = {
    REPORT_PG: PG_VALUE_COLUMNS,
    REPORT_ZV: ZV_VALUE_COLUMNS,
}

VALUE_COLUMN_GROUPS = {
    REPORT_PG: PG_VALUE_COLUMN_GROUPS,
    REPORT_ZV: ZV_VALUE_COLUMN_GROUPS,
}

SKIP_IMPORT_HEADERS = frozenset(
    {
        "всего",
        "электростанциябаза",
        "электростанция_база",
        "газообразные_и_жидкие_вещества",
    }
)

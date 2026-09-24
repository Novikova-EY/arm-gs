# -*- coding: utf-8 -*-
"""Константы отчетных данных ГИС ТЭК (ПГ / ЗВ)."""

from __future__ import annotations

REPORT_PG = "pg"
REPORT_ZV = "zv"

SHEET_NAMES = {
    REPORT_PG: "СБОРКА ПГ",
    REPORT_ZV: "СБОРКА ЗВ",
}

PAGE_TITLES = {
    REPORT_PG: "Парниковые газы (ПГ) - отчетные данные",
    REPORT_ZV: "Загрязняющие вещества (ЗВ) - отчетные данные",
}

# Столбцы значений из Excel (attr, заголовок).
# «Всего» и «Газообразные и жидкие вещества» считаются на странице.
PG_VALUE_COLUMNS: list[tuple[str, str]] = [
    ("gas_consumption_tce", "Расход газа, тут"),
    ("co2_from_gas_t", "Выбросы СО2 от сжигания газа, т"),
    ("oil_fuel_consumption_tce", "Расход мазута, тут"),
    ("co2_from_oil_fuel_t", "Выбросы СО2 от сжигания мазута, т"),
    ("solid_fuel_consumption_tce", "Расход твердого топлива, тут"),
    ("co2_from_solid_fuel_t", "Выбросы СО2 от сжигания твердого топлива, т"),
]

# Двухрядная шапка страницы ПГ: вид топлива в 1-й строке, общие подписи во 2-й.
PG_VALUE_COLUMN_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Газ",
        [
            ("gas_consumption_tce", "Расход топлива, тут"),
            ("co2_from_gas_t", "Выбросы СО2 от сжигания топлива, т"),
        ],
    ),
    (
        "Мазут",
        [
            ("oil_fuel_consumption_tce", "Расход топлива, тут"),
            ("co2_from_oil_fuel_t", "Выбросы СО2 от сжигания топлива, т"),
        ],
    ),
    (
        "Твердое топливо",
        [
            ("solid_fuel_consumption_tce", "Расход топлива, тут"),
            ("co2_from_solid_fuel_t", "Выбросы СО2 от сжигания топлива, т"),
        ],
    ),
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

# Двухрядная шапка ЗВ под баннером: пустая 2-я подпись — столбец на всю высоту группы.
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

# «Газообразные и жидкие вещества» — сумма слагаемых, не берётся из Excel.
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

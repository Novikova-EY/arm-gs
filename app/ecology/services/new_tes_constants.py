# -*- coding: utf-8 -*-
"""Константы расчёта по новым ТЭС (макет «Воздух новые»: М = В × У)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.ecology.services.operating_tes_constants import (  # noqa: F401
    FUEL_ROWS,
    GCAL_TO_MWH,
    KIND_TOTAL,
    KIND_VALUE,
    PARENT_CHILDREN,
    ROUNDING_CHOICES,
    ROUNDING_DIGITS,
    TERRITORIES,
    TOP_INPUT_ROWS,
    VOLUME_ROWS,
    get_territory,
)

DEFAULT_TERRITORY_SLUG = "vsego"
DEFAULT_SHEET_SLUG = "obemy"

CAPACITY_LE100 = Decimal("100")
CAPACITY_LE100_KEY = "le100"
CAPACITY_GT100_KEY = "gt100"
CAPACITY_CLASSES = (CAPACITY_LE100_KEY, CAPACITY_GT100_KEY)

NORM_KINDS = ("ash", "so2", "nox", "co", "pg")

NEW_TES_CALC_SHEETS: tuple[dict[str, Any], ...] = (
    {
        "slug": "toplivo",
        "sheet_name": "Данные по модулю Топливо",
        "page_title": "Топливные показатели новых ТЭС (модуль Топливо)",
        "unit": "тыс.тут",
        "layout": "fuel",
    },
    {
        "slug": "spravochnik",
        "sheet_name": "Нормативы",
        "page_title": "Нормативы удельных выбросов загрязняющих веществ и парниковых газов",
        "unit": "",
        "layout": "chars",
    },
    {
        "slug": "zola",
        "sheet_name": "Зола",
        "page_title": "Выбросы твердых веществ в атмосферу",
        "unit": "тыс. т",
        "layout": "emission",
    },
    {
        "slug": "sera",
        "sheet_name": "Сера",
        "page_title": "Выбросы диоксидов серы, тыс.т/год",
        "unit": "тыс. т",
        "layout": "emission",
    },
    {
        "slug": "azot",
        "sheet_name": "Азот",
        "page_title": "Выбросы оксидов азота в атмосферу, тыс.т/год",
        "unit": "тыс. т",
        "layout": "emission",
    },
    {
        "slug": "co",
        "sheet_name": "CO",
        "page_title": "Выбросы монооксидов углерода в атмосферу, т/год",
        "unit": "т",
        "layout": "emission",
    },
    {
        "slug": "pg",
        "sheet_name": "ПГ",
        "page_title": "Выбросы парниковых газов (CO2) в атмосферу, тыс.т/год",
        "unit": "тыс. т",
        "layout": "emission",
    },
    {
        "slug": "obemy",
        "sheet_name": "Объемы",
        "page_title": "Ожидаемые объёмы выбросов от нового оборудования",
        "unit": "тыс. т",
        "layout": "volumes",
    },
    {
        "slug": "udel-e",
        "sheet_name": "Удельные по привед Э",
        "page_title": "Удельные выбросы на приведённую энергию",
        "unit": "г/кВт·ч",
        "layout": "specific_e",
    },
    {
        "slug": "udel-fuel",
        "sheet_name": "Удельные по топл",
        "page_title": "Удельные выбросы на топливо",
        "unit": "кг/тут",
        "layout": "specific_fuel",
    },
    {
        "slug": "udel-ee",
        "sheet_name": "Удельные только по ЭЭ",
        "page_title": "Удельные выбросы на выработку электроэнергии",
        "unit": "г/кВт·ч",
        "layout": "specific_ee",
    },
)

NEW_TES_EMISSION_VIEW: dict[str, dict[str, Any]] = {
    "zola": {
        "kind": "pair",
        "left_metric": "b",
        "right_metric": "ash",
        "left_title": "В, тыс.тут",
        "right_title": "М, тыс.т",
        "left_formula_key": "nt_fuel_b",
        "right_formula_key": "nt_zv_thous",
        "show_unit_column": False,
    },
    "sera": {
        "kind": "pair",
        "left_metric": "b",
        "right_metric": "so2",
        "left_title": "В, тыс.тут",
        "right_title": "М, тыс.т",
        "left_formula_key": "nt_fuel_b",
        "right_formula_key": "nt_zv_thous",
        "show_unit_column": False,
    },
    "azot": {
        "kind": "pair",
        "left_metric": "b",
        "right_metric": "nox",
        "left_title": "В, тыс.тут",
        "right_title": "М, тыс.т",
        "left_formula_key": "nt_fuel_b",
        "right_formula_key": "nt_zv_thous",
        "show_unit_column": False,
    },
    "co": {
        "kind": "pair",
        "left_metric": "b",
        "right_metric": "co",
        "left_title": "В, тыс.тут",
        "right_title": "М, т",
        "left_formula_key": "nt_fuel_b",
        "right_formula_key": "nt_zv_tonnes",
        "show_unit_column": False,
    },
    "pg": {
        "kind": "pair",
        "left_metric": "b",
        "right_metric": "pg",
        "left_title": "В, тыс.тут",
        "right_title": "М, тыс.т",
        "left_formula_key": "nt_fuel_b",
        "right_formula_key": "nt_pg_mass",
        "show_unit_column": False,
    },
}

NORM_COLUMNS: tuple[tuple[str, str], ...] = (
    ("ash_le100", "Зола"),
    ("so2_le100", "Сера"),
    ("nox_le100", "Азот"),
    ("co_le100", "CO"),
    ("pg_le100", "ПГ"),
    ("ash_gt100", "Зола"),
    ("so2_gt100", "Сера"),
    ("nox_gt100", "Азот"),
    ("co_gt100", "CO"),
    ("pg_gt100", "ПГ"),
)

NORM_HEADER_GROUPS: tuple[dict[str, Any], ...] = (
    {
        "title": "До 100 МВт, кг/тут (ПГ — т/тут)",
        "keys": ("ash_le100", "so2_le100", "nox_le100", "co_le100", "pg_le100"),
    },
    {
        "title": "Более 100 МВт, кг/тут (ПГ — т/тут)",
        "keys": ("ash_gt100", "so2_gt100", "nox_gt100", "co_gt100", "pg_gt100"),
    },
)

NORM_FIELD_KEYS = frozenset(key for key, _label in NORM_COLUMNS)

# (ash, so2, nox, co, pg) для le100 и gt100. Источник — лист «Нормативы уд.выборосов».
_N = {
    "gas_natural": ((0, 0, 1.26, 0, 1.59), (0, 0, 1.26, 0, 1.59)),
    "gas_associated": ((0, 0, 1.26, 0, 1.695), (0, 0, 1.26, 0, 1.695)),
    "mazut": ((1.76, 8.8, 2.52, 0, 2.27), (0.59, 8.8, 2.52, 0, 2.27)),
    "diesel": ((0, 8.8, 2.52, 0, 2.17), (0, 8.8, 2.52, 0, 2.17)),
    "other_oil": ((0, 8.8, 2.52, 0, 2.17), (0, 8.8, 2.52, 0, 2.17)),
    "peat": ((2.62, 8.8, 4.98, 0, 3.11), (0.59, 8.8, 3.81, 0, 3.11)),
    "blast_furnace_gas": ((0, 0, 1.26, 0, 4.46), (0, 0, 1.26, 0, 4.46)),
    "coke_oven_gas": ((0, 0, 1.26, 0, 4.46), (0, 0, 1.26, 0, 4.46)),
    "npz_gas": ((0, 0, 1.26, 0, 1.3), (0, 0, 1.26, 0, 1.3)),
    "other_solid": ((1.76, 8.8, 1.26, 0, 4.19), (0.59, 8.8, 1.26, 0, 4.19)),
    "donetsk": ((2.93, 17.6, 4.98, 0, 2.65), (1.76, 17.6, 3.81, 0, 2.65)),
    "moscow": ((2.93, 17.6, 3.2, 0, 2.79), (1.76, 17.6, 3.2, 0, 2.79)),
    "inta": ((2.93, 8.8, 4.98, 0, 2.73), (1.76, 8.8, 3.81, 0, 2.73)),
    "vorkuta": ((2.93, 17.6, 4.98, 0, 2.71), (1.76, 8.8, 3.81, 0, 2.71)),
    "kuzn_gd": ((2.47, 8.8, 4.98, 0, 2.69), (1.48, 8.8, 3.81, 0, 2.69)),
    "kuzn_t": ((2.14, 8.8, 4.98, 0, 2.69), (1.28, 8.8, 3.81, 0, 2.69)),
    "kuzn_ss": ((2.47, 8.8, 4.98, 0, 2.69), (1.45, 8.8, 3.81, 0, 2.69)),
    "kuzn_other": ((2.93, 17.6, 4.98, 0, 2.69), (1.76, 8.8, 3.81, 0, 2.69)),
    "sverdlovsk": ((2.93, 8.8, 3.2, 0, 2.76), (1.76, 8.8, 3.2, 0, 2.76)),
    "chelyabinsk": ((2.93, 8.8, 3.2, 0, 2.78), (1.76, 8.8, 3.2, 0, 2.78)),
    "kizel": ((2.93, 17.6, 4.98, 0, 2.77), (1.76, 8.8, 3.81, 0, 2.77)),
    "bashkir": ((2.14, 8.8, 3.2, 0, 2.76), (1.23, 8.8, 3.2, 0, 2.76)),
    "nazarov": ((1.76, 8.8, 3.2, 0, 2.87), (0.59, 8.8, 3.2, 0, 2.87)),
    "borodino": ((1.76, 8.8, 3.2, 0, 2.87), (0.59, 8.8, 3.2, 0, 2.87)),
    "berezovsky": ((1.76, 8.8, 3.2, 0, 2.87), (0.59, 8.8, 3.2, 0, 2.87)),
    "pereyaslav": ((1.76, 8.8, 3.2, 0, 2.87), (0.59, 8.8, 3.2, 0, 2.87)),
    "irbey": ((1.76, 8.8, 3.2, 0, 2.87), (0.59, 8.8, 3.2, 0, 2.87)),
    "kansk": ((1.76, 8.8, 3.2, 0, 2.87), (0.59, 8.8, 3.2, 0, 2.87)),
    "zheron": ((2.93, 8.8, 4.98, 0, 2.76), (1.79, 8.8, 3.81, 0, 2.76)),
    "karabul": ((2.23, 17.6, 4.98, 0, 2.76), (1.34, 8.8, 3.81, 0, 2.76)),
    "azey": ((2.47, 8.8, 3.2, 0, 2.75), (1.45, 8.8, 3.2, 0, 2.75)),
    "mugun": ((2.23, 17.6, 3.2, 0, 2.75), (1.37, 8.8, 3.2, 0, 2.75)),
    "cheremkhovo": ((2.93, 17.6, 4.98, 0, 2.75), (1.76, 8.8, 3.81, 0, 2.75)),
    "khakass": ((2.27, 8.8, 4.98, 0, 2.77), (1.36, 8.8, 3.81, 0, 2.77)),
    "tuva": ((2.1, 8.8, 4.98, 0, 2.76), (1.26, 8.8, 3.81, 0, 2.76)),
    "gusinoozersk": ((2.71, 8.8, 3.2, 0, 2.78), (1.63, 8.8, 3.2, 0, 2.78)),
    "tugnuy": ((2.71, 8.8, 4.98, 0, 2.76), (1.63, 8.8, 3.81, 0, 2.76)),
    "okino": ((2.93, 17.6, 3.2, 0, 2.78), (1.76, 8.8, 3.2, 0, 2.78)),
    "kharanor": ((1.76, 8.8, 3.2, 0, 2.9), (0.76, 8.8, 3.2, 0, 2.9)),
    "urtuy": ((1.76, 8.8, 3.2, 0, 2.9), (0.59, 8.8, 3.2, 0, 2.9)),
    "tataurovo": ((1.76, 8.8, 3.2, 0, 2.9), (0.94, 8.8, 3.2, 0, 2.9)),
    "tarbagatai": ((2.27, 17.6, 3.2, 0, 2.9), (1.36, 8.8, 3.2, 0, 2.9)),
    "zab_hard": ((2, 8.8, 4.98, 0, 2.9), (0.59, 8.8, 3.81, 0, 2.9)),
    "nerungri": ((1.86, 8.8, 4.98, 0, 2.76), (1.12, 8.8, 3.81, 0, 2.76)),
    "zyryan": ((1.76, 8.8, 4.98, 0, 2.76), (0.95, 8.8, 3.81, 0, 2.76)),
    "yakut_other": ((2.48, 8.8, 4.98, 0, 2.76), (1.49, 8.8, 3.81, 0, 2.76)),
    "raychikhinsk": ((1.76, 8.8, 3.2, 0, 2.76), (0.7, 8.8, 3.2, 0, 2.76)),
    "erkovets": ((1.82, 8.8, 3.2, 0, 2.76), (1.08, 8.8, 3.2, 0, 2.76)),
    "ogodzha": ((2.93, 8.8, 4.98, 0, 2.76), (1.76, 8.8, 3.81, 0, 2.76)),
    "urgal": ((2.93, 8.8, 4.98, 0, 2.77), (1.76, 8.8, 3.81, 0, 2.77)),
    "ushumun": ((2.93, 8.8, 3.2, 0, 2.96), (1.76, 8.8, 3.2, 0, 2.96)),
    "bikin": ((2.93, 8.8, 3.2, 0, 2.73), (1.76, 8.8, 3.2, 0, 2.73)),
    "razdolnensky": ((2.93, 8.8, 4.98, 0, 2.73), (1.76, 8.8, 3.81, 0, 2.73)),
    "khanka": ((2.17, 8.8, 3.2, 0, 2.73), (1.3, 8.8, 3.2, 0, 2.96)),
    "magadan": ((1.79, 8.8, 4.98, 0, 2.73), (0.68, 8.8, 3.81, 0, 2.73)),
    "sakhalin": ((2.93, 8.8, 4.98, 0, 2.73), (1.76, 8.8, 3.81, 0, 2.76)),
    "kamchatka": ((2.93, 8.8, 4.98, 0, 2.76), (1.76, 8.8, 3.81, 0, 2.73)),
    "anadyr": ((1.76, 8.8, 3.2, 0, 2.96), (1.05, 8.8, 3.2, 0, 2.96)),
    "beringovsky": ((2.34, 17.6, 4.98, 0, 2.77), (1.41, 8.8, 3.81, 0, 2.77)),
    "ekibastuz": ((2.93, 8.8, 4.98, 0, 2.77), (1.76, 8.8, 3.81, 0, 2.77)),
    "maikuben": ((2.93, 8.8, 3.2, 0, 2.96), (1.76, 8.8, 3.2, 0, 2.96)),
    "karaganda": ((2.93, 17.6, 4.98, 0, 2.76), (1.76, 8.8, 3.81, 0, 2.76)),
    "karazhyra": ((2.93, 8.8, 4.98, 0, 2.77), (1.76, 8.8, 3.81, 0, 2.77)),
    "teniz": ((2.93, 17.6, 3.2, 0, 2.77), (1.76, 8.8, 3.2, 0, 2.77)),
}


def _pack(pair: tuple[tuple[float, ...], tuple[float, ...]]) -> dict[str, dict[str, float]]:
    le, gt = pair
    return {
        CAPACITY_LE100_KEY: dict(zip(NORM_KINDS, le)),
        CAPACITY_GT100_KEY: dict(zip(NORM_KINDS, gt)),
    }


DEFAULT_NORMS: dict[str, dict[str, dict[str, float]]] = {
    key: _pack(pair) for key, pair in _N.items()
}

VOLUME_ROW_FORMULA_KEYS: dict[str, tuple[str, ...]] = {
    "pollutants_total": ("nt_zv_sum",),
    "ash": ("nt_zv_thous",),
    "so2": ("nt_zv_thous",),
    "nox": ("nt_zv_thous",),
    "co": ("nt_zv_tonnes",),
    "co2": ("nt_pg_mass",),
}


def get_calc_sheet(slug: str) -> dict[str, Any] | None:
    wanted = str(slug or "").strip()
    return next((item for item in NEW_TES_CALC_SHEETS if item["slug"] == wanted), None)


def parse_norm_field(field: str) -> tuple[str, str] | None:
    """'ash_le100' → ('ash', 'le100')."""
    wanted = str(field or "").strip()
    for kind in NORM_KINDS:
        prefix = f"{kind}_"
        if wanted.startswith(prefix):
            cls = wanted[len(prefix) :]
            if cls in CAPACITY_CLASSES:
                return kind, cls
    return None


def default_norm(fuel_key: str, capacity_class: str, kind: str) -> float:
    by_fuel = DEFAULT_NORMS.get(fuel_key) or {}
    by_class = by_fuel.get(capacity_class) or {}
    return float(by_class.get(kind, 0.0))

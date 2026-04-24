# -*- coding: utf-8 -*-
"""Колонки предпросмотра таблицы основных топливных параметров (пакетный пересчёт, страница «Расчёт»)."""

from __future__ import annotations

# Полный набор как на stations_equipment_group_fuel_params / пакетный пересчёт.
FUEL_PARAM_PREVIEW_COLUMNS_FULL: list[tuple[str, str, bool]] = [
    ("numb1120", "Код станции", False),
    ("nust", "Руст", True),
    ("nr", "Ррасп", True),
    ("e", "Выработка эл.эн.", True),
    ("ewtp", "Этц", True),
    ("eotp", "Отпуск эл.эн.", True),
    ("eurt", "Уд.расх эл.эн.", True),
    ("eust", "Расх топ эл.эн.", True),
    ("snk", "СН, %", True),
    ("q", "Отпуск тепл.эн.", True),
    ("qotr", "Отраб тепл.эн.", True),
    ("turt", "Уд.расх тепл.эн.", True),
    ("tust", "Расх топ тепл.эн.", True),
    ("sn_t", "СН, кВтч/Гкал", True),
    ("b", "Расх топл.", True),
    ("gaz", "Газ", True),
    ("isk_gaz", "Иск. газ", True),
    ("mazut", "Мазут", True),
    ("torf", "Торф", True),
    ("slan", "Сланцы", True),
    ("proch", "Прочее", True),
    ("ugol", "Уголь", True),
    ("don", "Дон", True),
    ("podm", "Подм", True),
    ("pech", "Печ", True),
    ("arkt", "Арктикуголь", True),
    ("kuzn", "Кузбасс", True),
    ("ural", "Урал", True),
    ("bashk", "Башкортостан", True),
    ("kazah", "Казахстан", True),
    ("kan", "Канск", True),
    ("tung", "Тунгусск", True),
    ("irkut", "Иркутск", True),
    ("hak", "Хакасия", True),
    ("tuv", "Тува", True),
    ("bur", "Бурятия", True),
    ("chit", "Чита", True),
    ("yakut", "Якутия", True),
    ("amur", "Амур", True),
    ("urg", "Юрга", True),
    ("ushum", "Ушумун", True),
    ("prim", "Приморье", True),
    ("mag", "Магадан", True),
    ("chukot", "Чукотка", True),
    ("kamch", "Камчатка", True),
    ("sah", "Сахалин", True),
    ("nt", "Тепл. мощн. отборов", True),
    ("nt_sum", "Сумма NT", True),
]

# Входы и результаты этапов Коэфф / Распред / расчётных формул по строке (без долей по видам топлива).
FUEL_PARAM_PREVIEW_COLUMNS_CALCULATION: list[tuple[str, str, bool]] = [
    ("numb1120", "Код станции", False),
    ("nust", "Руст", True),
    ("nr", "Ррасп", True),
    ("y", "Уд. выработка эл.эн. (Y)", True),
    ("e", "Выработка эл.эн.", True),
    ("ewtp", "Этц", True),
    ("eotp", "Отпуск эл.эн.", True),
    ("eurt", "Уд.расх эл.эн.", True),
    ("eust", "Расх топ эл.эн.", True),
    ("snk", "СН, %", True),
    ("q", "Отпуск тепл.эн.", True),
    ("qotr", "Отраб тепл.эн.", True),
    ("turt", "Уд.расх тепл.эн.", True),
    ("tust", "Расх топ тепл.эн.", True),
    ("sn_t", "СН, кВтч/Гкал", True),
    ("b", "Расх топл.", True),
    ("nt", "Тепл. мощн. отборов", True),
    ("nt_sum", "Сумма NT", True),
]

COLLAPSIBLE_UGOL_ATTRS: list[str] = [
    "don",
    "podm",
    "pech",
    "arkt",
    "kuzn",
    "ural",
    "bashk",
    "kazah",
    "kan",
    "tung",
    "irkut",
    "hak",
    "tuv",
    "bur",
    "chit",
    "yakut",
    "amur",
    "urg",
    "ushum",
    "prim",
    "mag",
    "chukot",
    "kamch",
    "sah",
]


def resolve_fuel_param_preview_columns(
    column_set: str | None,
) -> tuple[list[tuple[str, str, bool]], list[str]]:
    """
    column_set: «full» (по умолчанию) или «calculation» — только поля баланса и расчётных показателей по строке.
    Возвращает (список колонок, атрибуты для сворачивания блока углей; для calculation — пусто).
    """
    key = (column_set or "full").strip().lower()
    if key == "calculation":
        return list(FUEL_PARAM_PREVIEW_COLUMNS_CALCULATION), []
    return list(FUEL_PARAM_PREVIEW_COLUMNS_FULL), list(COLLAPSIBLE_UGOL_ATTRS)

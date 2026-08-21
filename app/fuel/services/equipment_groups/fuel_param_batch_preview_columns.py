# -*- coding: utf-8 -*-
"""Колонки предпросмотра таблицы основных топливных параметров (пакетный пересчёт, страница «Расчёт»)."""

from __future__ import annotations

from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)

# Полный набор как на stations_equipment_group_fuel_params / пакетный пересчёт.
FUEL_PARAM_PREVIEW_COLUMNS_FULL: list[tuple[str, str, bool]] = [
    ("numb1120", "Код группы оборудования", False),
    ("nust", EquipmentGroupFuelParam.NUST_COLUMN_LABEL, True),
    ("nr", EquipmentGroupFuelParam.NR_COLUMN_LABEL, True),
    ("e", "Выработка ЭЭ, тыс.кВтч", True),
    ("ewtp", "Теплофикационная выработка ЭЭ, тыс.кВтч", True),
    ("eotp", EquipmentGroupFuelParam.EOTP_COLUMN_LABEL, True),
    ("eurt", EquipmentGroupFuelParam.EURT_COLUMN_LABEL, True),
    ("eust", "Расх топ эл.эн.", True),
    ("sn_ee", EquipmentGroupFuelParam.SN_EE_COLUMN_LABEL, True),
    ("snk", EquipmentGroupSpecificFuelConsumption.SNK_COLUMN_LABEL, True),
    ("q", EquipmentGroupFuelParam.Q_COLUMN_LABEL, True),
    ("qotr", "Тепловое потребление (отборов турбин), тыс.Гкал", True),
    ("turt", EquipmentGroupFuelParam.TURT_COLUMN_LABEL, True),
    ("tust", EquipmentGroupFuelParam.TUST_COLUMN_LABEL, True),
    ("sn_te", EquipmentGroupFuelParam.SN_TE_COLUMN_LABEL, True),
    ("sn_t", EquipmentGroupFuelParam.SN_T_COLUMN_LABEL, True),
    ("b", "Расход топлива, всего", True),
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
    ("nt", EquipmentGroupFuelParam.NT_COLUMN_LABEL, True),
    ("nt_sum", EquipmentGroupFuelParam.NT_SUM_COLUMN_LABEL, True),
]

# Входы и результаты этапов Коэфф / Распред / расчётных формул по строке (без долей по видам топлива).
FUEL_PARAM_PREVIEW_COLUMNS_CALCULATION: list[tuple[str, str, bool]] = [
    ("numb1120", "Код группы оборудования", False),
    ("nust", EquipmentGroupFuelParam.NUST_COLUMN_LABEL, True),
    ("nr", EquipmentGroupFuelParam.NR_COLUMN_LABEL, True),
    ("y", EquipmentGroupSpecificFuelConsumption.Y_COLUMN_LABEL, True),
    ("e", "Выработка ЭЭ, тыс.кВтч", True),
    ("ewtp", "Теплофикационная выработка ЭЭ, тыс.кВтч", True),
    ("eotp", EquipmentGroupFuelParam.EOTP_COLUMN_LABEL, True),
    ("eurt", EquipmentGroupFuelParam.EURT_COLUMN_LABEL, True),
    ("eust", "Расх топ эл.эн.", True),
    ("sn_ee", EquipmentGroupFuelParam.SN_EE_COLUMN_LABEL, True),
    ("snk", EquipmentGroupSpecificFuelConsumption.SNK_COLUMN_LABEL, True),
    ("q", EquipmentGroupFuelParam.Q_COLUMN_LABEL, True),
    ("qotr", "Тепловое потребление (отборов турбин), тыс.Гкал", True),
    ("turt", EquipmentGroupFuelParam.TURT_COLUMN_LABEL, True),
    ("tust", EquipmentGroupFuelParam.TUST_COLUMN_LABEL, True),
    ("sn_te", EquipmentGroupFuelParam.SN_TE_COLUMN_LABEL, True),
    ("sn_t", EquipmentGroupFuelParam.SN_T_COLUMN_LABEL, True),
    ("b", "Расход топлива, всего", True),
    ("nt", EquipmentGroupFuelParam.NT_COLUMN_LABEL, True),
    ("nt_sum", EquipmentGroupFuelParam.NT_SUM_COLUMN_LABEL, True),
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

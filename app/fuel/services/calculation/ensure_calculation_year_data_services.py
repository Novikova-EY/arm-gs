# -*- coding: utf-8 -*-
"""
Автозаполнение расчётного года на /fuel/calculation.

Если для выбранного расчётного года ещё нет строк «ТЭП», копирует ТЭП
с базового года той же логикой, что кнопка «Добавить год».

Удельные и формулы не копируем: Access Seek берёт последнюю запись
year ≤ расчётный. Лишняя строка расчётного года (копия 2024) перекрывает
живой 2025/2026 и ломает Топливо.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import distinct

from app.extensions import db
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)
from app.fuel.services.calculation.fuel_calculation_edit_data_services import (
    apply_heat_and_tariffs_q_for_existing_rows,
    copy_heat_fuel_param_columns_for_filters,
    fill_snk_snt_from_source_year_for_existing_rows,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
    get_equipment_group_ids_for_fuel_params_filters,
)


# UniqueConstraint без database_version_id — одна строка на (группу, год).
_MODELS_UNIQUE_BY_GROUP_YEAR = frozenset(
    {
        EquipmentGroupFuelParam,
        EquipmentGroupSpecificFuelConsumption,
    }
)


def _eg_ids_with_year(
    model,
    eg_ids: list[int],
    year_number: int,
    version_id: int | None,
    *,
    match_version: bool | None = None,
) -> set[int]:
    if not eg_ids:
        return set()
    if match_version is None:
        match_version = model not in _MODELS_UNIQUE_BY_GROUP_YEAR
    q = db.session.query(distinct(model.equipment_group_id)).filter(
        model.equipment_group_id.in_(eg_ids),
        model.year_number == int(year_number),
    )
    if match_version and hasattr(model, "database_version_id"):
        if version_id is not None:
            q = q.filter(model.database_version_id == version_id)
        else:
            q = q.filter(model.database_version_id.is_(None))
    return {int(gid) for (gid,) in q.all() if gid is not None}


def _needs_year_copy(
    model,
    eg_ids: list[int],
    source_year: int,
    target_year: int,
    version_id: int | None,
) -> bool:
    """True, если есть группы с данными за базовый год без строки за расчётный."""
    with_source = _eg_ids_with_year(model, eg_ids, source_year, version_id)
    if not with_source:
        return False
    with_target = _eg_ids_with_year(model, eg_ids, target_year, version_id)
    return bool(with_source - with_target)


def heat_seed_target_years(base_year: int, calc_year: int) -> list[int]:
    """Промежуточные и расчётный годы для посева ТЭП (без базового)."""
    lo, hi = int(base_year), int(calc_year)
    if hi <= lo:
        return []
    return list(range(lo + 1, hi + 1))


def ensure_calculation_year_data_from_base(
    filters: dict[str, Any] | None,
    *,
    base_year: int,
    calc_year: int,
) -> dict[str, Any]:
    """
    При необходимости копирует ТЭП с base_year на calc_year.
    ТЭП: создаёт только недостающие годы base+1…calc (не затирает уже существующие,
    чтобы сохранить QOTR из импорта Access «Станции(Схема)»).
    На существующие прогнозные годы накладывает Q из «Тепло и тарифы» (схемы теплоснабжения),
    как Access «Тепло из СТ» — без этого на расчётном году остаётся Q базового года.
    Формулы и удельные не копируем (Access Seek year ≤ расчётный; копия 2024 на
    2026/2027 перекрывает живой 2025). Явное копирование — кнопки «Добавить год»
    на страницах формул / удельных.
    Если строки ТЭП за расчётный год уже есть — дозаполняет пустые SNK/SNT с базового года.

    Возвращает словарь со счётчиками и флагом ``did_anything``.
    Коммит не выполняет — вызывающая сторона делает ``db.session.commit()``.
    """
    source = int(base_year)
    target = int(calc_year)
    empty = {
        "did_anything": False,
        "base_year": source,
        "calc_year": target,
        "heat": None,
        "hat_q": 0,
        "formulas": None,
        "specific": None,
    }
    if source == target:
        return empty

    f = {**(filters or {})}
    f.pop("page", None)
    filter_start = min(source, target)
    filter_end = max(source, target)

    eg_ids = get_equipment_group_ids_for_fuel_params_filters(
        f, start_year=filter_start, end_year=filter_end
    )
    if not eg_ids:
        return empty

    result = {**empty, "heat": (0, 0, 0), "hat_q": 0, "formulas": (0, 0, 0), "specific": (0, 0, 0)}

    heat_years = heat_seed_target_years(source, target)
    if heat_years:
        result["heat"] = copy_heat_fuel_param_columns_for_filters(
            f,
            filter_start_year=filter_start,
            filter_end_year=filter_end,
            source_year_number=source,
            target_year_numbers=heat_years,
            only_new_rows=True,
        )
        if result["heat"][0]:
            result["did_anything"] = True

    if heat_years:
        n_hat = apply_heat_and_tariffs_q_for_existing_rows(
            f,
            filter_start_year=filter_start,
            filter_end_year=filter_end,
            target_year_numbers=heat_years,
        )
        result["hat_q"] = n_hat
        if n_hat:
            result["did_anything"] = True

    sn_filled = fill_snk_snt_from_source_year_for_existing_rows(
        f,
        filter_start_year=filter_start,
        filter_end_year=filter_end,
        source_year_number=source,
        target_year_numbers=[target],
    )
    if sn_filled:
        copied, skipped, total = result["heat"] or (0, 0, 0)
        if not copied:
            result["heat"] = (sn_filled, 0, len(eg_ids))
        else:
            result["heat"] = (copied, skipped, total)
        result["did_anything"] = True

    return result

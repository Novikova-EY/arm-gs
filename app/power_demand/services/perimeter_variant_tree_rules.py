# -*- coding: utf-8 -*-
"""Правила состава дерева для вариантов периметра в модуле нагрузок."""
from __future__ import annotations

from collections.abc import Iterable

from app.common.perimeter_variant.constants import (
    EES_RUSSIA_AGGREGATE_NAME_CF,
    ENTITY_KIND_EES_RUSSIA,
)
from app.common.perimeter_variant.registry import CODE_WITHOUT_NT, CODE_WITH_NT

SOUTH_UES_ENTITY_KIND = "union_energy_system"
SOUTH_UES_NAME_CF = "оэс юга"
EES_RUSSIA_ENTITY_KIND = ENTITY_KIND_EES_RUSSIA
EES_RUSSIA_NAME_CF = EES_RUSSIA_AGGREGATE_NAME_CF
NEW_TERRITORIES_FROM_YEAR = 2023


def _years_include_from_year(years: Iterable[int], from_year: int) -> bool:
    for year in years:
        try:
            if int(year) >= int(from_year):
                return True
        except (TypeError, ValueError):
            continue
    return False


def south_ues_base_tree_includes_new_territories(years: Iterable[int]) -> bool:
    """Правило 2: узел «Новые территории» в базовом дереве ОЭС Юга с 2023 года."""
    return _years_include_from_year(years, NEW_TERRITORIES_FROM_YEAR)


def should_add_new_territories_to_south_ues_tree(
    *,
    entity_kind: str,
    entity_name: str | None,
    perimeter_variant_code: str | None,
    years: Iterable[int],
) -> bool:
    """НТ в базовом дереве ОЭС Юга (вариант without_nt) при годах >= 2023."""
    return (
        entity_kind == SOUTH_UES_ENTITY_KIND
        and (entity_name or "").strip().casefold() == SOUTH_UES_NAME_CF
        and perimeter_variant_code == CODE_WITHOUT_NT
        and south_ues_base_tree_includes_new_territories(years)
    )


def should_add_new_territories_to_ees_russia_base_tree(
    *,
    entity_kind: str,
    entity_name: str | None,
    perimeter_variant_code: str | None,
    years: Iterable[int],
) -> bool:
    """Для ЭЭС России (агрегат): в базовом дереве (without_nt) ОЭС Юга получает НТ с 2023 года.

    Вариант with_nt — только строка показателей; территориальное отличие отражается
    в дереве under without_nt (правило 2 по отображаемым годам).
    """
    return (
        entity_kind == EES_RUSSIA_ENTITY_KIND
        and (entity_name or "").strip().casefold() == EES_RUSSIA_NAME_CF
        and perimeter_variant_code == CODE_WITHOUT_NT
        and south_ues_base_tree_includes_new_territories(years)
    )

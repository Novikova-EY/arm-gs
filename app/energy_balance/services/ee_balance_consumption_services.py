# -*- coding: utf-8 -*-
"""Потребление ЭЭ для балансов — со сводки потребления (вариант без НТ).

Берём ``energy_consumption_mln_kvt_ch`` по ЕЭС, СЗ и ОЭС. Калининградская СЗ —
сохранённый вариант периметра, как на сводке потребления.

Для «без НТ» учитываем GAES-коды той же группы и строки с ``perimeter_variant_code IS NULL``
(часто плановые годы лежат там, а строка ``without_nt`` пустая). Для 1-й СЗ —
дополнительно варианты ``*_kaliningrad*``.

ТИТЭС Востока (листы энергорайонов): как на
``/energy_consumption/summary/oes/`` — одноименные строки **без варианта О-1**.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.common.perimeter_variant.constants import (
    CODE_WITHOUT_NT,
    perimeter_variant_codes_prefer_without_gaes,
)
from app.common.perimeter_variant.registry import (
    is_kaliningrad_sync_area_entity_name,
    is_o1_perimeter_variant_code,
)
from app.energy_balance.services.power_balance_demand_max_services import (
    resolve_demand_max_territory,
)
from app.energy_consumption.models.energy_systems.energy_unit_energy_consumption_parameter_model import (
    EnergyUnitEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.energy_system_type_energy_consumption_parameter_model import (
    EnergySystemTypeEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.regional_energy_system_energy_consumption_parameter_model import (
    RegionalEnergySystemEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.synchronous_area_energy_consumption_parameter_model import (
    SynchronousAreaEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.union_energy_system_energy_consumption_parameter_model import (
    UnionEnergySystemEnergyConsumptionParameter,
)
from app.energy_consumption.services.energy_consumption_parameter_services import (
    get_demand_rows,
    peek_stored_perimeter_variant_code_for_parent,
)

_KIND_CONSUMPTION = {
    "est": (EnergySystemTypeEnergyConsumptionParameter, "id_energy_system_type"),
    "ues": (UnionEnergySystemEnergyConsumptionParameter, "id_union_energy_system"),
    "sa": (SynchronousAreaEnergyConsumptionParameter, "id_synchronous_area"),
    "res": (RegionalEnergySystemEnergyConsumptionParameter, "id_regional_energy_system"),
    "eu": (EnergyUnitEnergyConsumptionParameter, "id_energy_unit"),
}

CONSUMPTION_ROW_KEY = "consumption"

_FIRST_SA_EXTRA_CODES = (
    "without_nt_with_gaes_kaliningrad",
    "without_nt_without_gaes_kaliningrad",
    "without_nt_with_gaes_with_kaliningrad_es",
    "without_nt_without_gaes_with_kaliningrad_es",
    "without_nt_with_gaes_without_kaliningrad",
    "without_nt_without_gaes_without_kaliningrad",
    "without_nt_with_gaes_without_kaliningrad_es",
    "without_nt_without_gaes_without_kaliningrad_es",
)


def _norm_name(text: str | None) -> str:
    return (text or "").casefold().replace("ё", "е").replace("-", " ").strip()


def _is_first_sz_name(name: str | None) -> bool:
    n = _norm_name(name)
    if "калининг" in n:
        return False
    return ("1" in n or "перв" in n) and "сз" in n


def year_values_from_consumption_rows(
    rows: list[Any],
    years: list[int],
) -> dict[int, Decimal]:
    """energy_consumption_mln_kvt_ch по календарным годам."""
    wanted = {int(year) for year in years}
    result: dict[int, Decimal] = {}
    for row in rows or []:
        year = getattr(row, "year_number", None)
        if year is None:
            continue
        year_int = int(year)
        if year_int not in wanted:
            continue
        value = getattr(row, "energy_consumption_mln_kvt_ch", None)
        if value is None:
            continue
        result[year_int] = Decimal(str(value))
    return result


def _consumption_value(row: Any) -> Decimal | None:
    value = getattr(row, "energy_consumption_mln_kvt_ch", None)
    if value is None:
        return None
    return Decimal(str(value))


def _prefer_consumption_row(existing: Any | None, candidate: Any) -> Any:
    if existing is None:
        return candidate
    old = _consumption_value(existing)
    new = _consumption_value(candidate)
    if old is None and new is not None:
        return candidate
    if (old is None or old == 0) and new is not None and new != 0:
        return candidate
    return existing


def _merge_consumption_rows_by_year(
    codes: list[str | None],
    model: Any,
    fk_column: str,
    parent_id: int,
    *,
    skip_o1: bool = False,
) -> list[Any]:
    by_year: dict[int, Any] = {}
    for code in codes:
        if skip_o1 and is_o1_perimeter_variant_code(code):
            continue
        for row in get_demand_rows(
            model,
            fk_column,
            parent_id,
            perimeter_variant_code=code,
        ):
            if skip_o1 and is_o1_perimeter_variant_code(
                getattr(row, "perimeter_variant_code", None)
            ):
                continue
            year = getattr(row, "year_number", None)
            if year is None:
                continue
            y = int(year)
            by_year[y] = _prefer_consumption_row(by_year.get(y), row)
    return list(by_year.values())


def _consumption_rows_energy_unit_without_o1(
    model: Any,
    fk_column: str,
    parent_id: int,
) -> list[Any]:
    """Энергорайон ТИТЭС на сводке ОЭС: базовая строка (NULL / без НТ), не О-1."""
    codes: list[str | None] = [None, *perimeter_variant_codes_prefer_without_gaes(CODE_WITHOUT_NT)]
    codes = list(dict.fromkeys(codes))
    return _merge_consumption_rows_by_year(
        codes,
        model,
        fk_column,
        parent_id,
        skip_o1=True,
    )


def _consumption_rows_without_nt(
    model: Any,
    fk_column: str,
    parent_id: int,
    *,
    kind: str,
    name: str | None,
) -> list[Any]:
    if kind == "eu":
        return _consumption_rows_energy_unit_without_o1(model, fk_column, parent_id)
    codes: list[str | None] = list(perimeter_variant_codes_prefer_without_gaes(CODE_WITHOUT_NT))
    if kind == "sa" and is_kaliningrad_sync_area_entity_name(name):
        stored = peek_stored_perimeter_variant_code_for_parent(model, fk_column, parent_id)
        extras: list[str | None] = list(_FIRST_SA_EXTRA_CODES)
        if stored:
            extras.insert(0, stored)
        codes = extras + codes
    elif kind == "sa" and _is_first_sz_name(name):
        stored = peek_stored_perimeter_variant_code_for_parent(model, fk_column, parent_id)
        extras = list(_FIRST_SA_EXTRA_CODES)
        if stored:
            extras.insert(0, stored)
        codes = extras + codes
    # Плановые годы часто лежат в строках с NULL-кодом при пустом without_nt.
    codes = list(dict.fromkeys([*codes, None]))
    return _merge_consumption_rows_by_year(codes, model, fk_column, parent_id)


def load_ee_balance_consumption_inputs(
    years: list[int],
    sheets: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, dict[int, Decimal]]]:
    """consumption по листам БЭ из потребления ЭЭ (вариант без НТ + GAES/NULL)."""
    if not years or not sheets:
        return {}
    inputs: dict[str, dict[str, dict[int, Decimal]]] = {}
    for sheet in sheets:
        slug = str(sheet.get("slug") or "")
        if not slug or sheet.get("skip_table"):
            continue
        territory = resolve_demand_max_territory(sheet)
        if territory is None:
            continue
        kind = str(territory.get("kind") or "")
        spec = _KIND_CONSUMPTION.get(kind)
        if spec is None:
            continue
        model, fk_column = spec
        try:
            parent_id = int(territory["id"])
        except (TypeError, ValueError, KeyError):
            continue
        rows = _consumption_rows_without_nt(
            model,
            fk_column,
            parent_id,
            kind=kind,
            name=territory.get("name") or sheet.get("sheet_name"),
        )
        year_map = year_values_from_consumption_rows(rows, years)
        if year_map:
            inputs[slug] = {CONSUMPTION_ROW_KEY: year_map}
    return inputs

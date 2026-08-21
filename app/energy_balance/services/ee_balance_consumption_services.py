# -*- coding: utf-8 -*-
"""Потребление ЭЭ для балансов — со сводки потребления (вариант без НТ).

Берём ``energy_consumption_mln_kvt_ch`` по ЕЭС, СЗ и ОЭС. Калининградская СЗ —
сохранённый вариант периметра, как на сводке потребления.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.common.perimeter_variant.constants import CODE_WITHOUT_NT
from app.common.perimeter_variant.registry import is_kaliningrad_sync_area_entity_name
from app.energy_balance.services.power_balance_demand_max_services import (
    resolve_demand_max_territory,
)
from app.energy_consumption.models.energy_systems.energy_system_type_energy_consumption_parameter_model import (
    EnergySystemTypeEnergyConsumptionParameter,
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
}

CONSUMPTION_ROW_KEY = "consumption"


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


def _consumption_rows_without_nt(
    model: Any,
    fk_column: str,
    parent_id: int,
    *,
    kind: str,
    name: str | None,
) -> list[Any]:
    if kind == "sa" and is_kaliningrad_sync_area_entity_name(name):
        stored = peek_stored_perimeter_variant_code_for_parent(model, fk_column, parent_id)
        return get_demand_rows(
            model,
            fk_column,
            parent_id,
            perimeter_variant_code=stored,
        )
    return get_demand_rows(
        model,
        fk_column,
        parent_id,
        perimeter_variant_code=CODE_WITHOUT_NT,
    )


def load_ee_balance_consumption_inputs(
    years: list[int],
    sheets: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, dict[int, Decimal]]]:
    """consumption по листам БЭ из потребления ЭЭ (вариант без НТ)."""
    if not years or not sheets:
        return {}
    inputs: dict[str, dict[str, dict[int, Decimal]]] = {}
    for sheet in sheets:
        slug = str(sheet.get("slug") or "")
        if not slug:
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

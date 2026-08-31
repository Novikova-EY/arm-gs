# -*- coding: utf-8 -*-
"""Заряд ГАЭС для балансов электрической энергии.

Сумма потребления ГАЭС на заряд (млн.кВт·ч) по территории листа — те же станции
типа «ГАЭС», что на сводке /energy_consumption/summary/oes/gaes_charge/.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.common.services.database_version_services import get_current_version
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

GAES_CHARGE_ROW_KEY = "gaes_charge"

_KIND_TO_SUMMARY_ENTITY = {
    "est": (EnergySystemTypeEnergyConsumptionParameter.__name__, "id_energy_system_type"),
    "ues": (UnionEnergySystemEnergyConsumptionParameter.__name__, "id_union_energy_system"),
    "sa": (SynchronousAreaEnergyConsumptionParameter.__name__, "id_synchronous_area"),
    "res": (RegionalEnergySystemEnergyConsumptionParameter.__name__, "id_regional_energy_system"),
    "eu": (EnergyUnitEnergyConsumptionParameter.__name__, "id_energy_unit"),
}


def year_values_from_gaes_charge_station_rows(
    station_rows: list[Any] | tuple[Any, ...] | None,
    years: list[int],
) -> dict[int, Decimal]:
    """Сумма charge_consumption станций ГАЭС по календарным годам."""
    wanted = {int(year) for year in years}
    result: dict[int, Decimal] = {year: Decimal("0") for year in wanted}
    has_any = False
    for _station_id, _name, values_tuple in station_rows or ():
        for year, value in values_tuple or ():
            if year is None or value is None:
                continue
            year_int = int(year)
            if year_int not in wanted:
                continue
            result[year_int] += Decimal(str(value))
            has_any = True
    if not has_any:
        return {}
    return result


def load_ee_balance_gaes_charge_inputs(
    years: list[int],
    sheets: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, dict[int, Decimal]]]:
    """gaes_charge по листам БЭ — сумма заряда ГАЭС по территории (как на сводке)."""
    if not years or not sheets:
        return {}
    from app.energy_consumption.services.energy_consumption_summary_services import (
        _gaes_charge_raw_station_values_for_entity,
    )

    version_id = get_current_version()
    years_tuple = tuple(int(year) for year in years)
    inputs: dict[str, dict[str, dict[int, Decimal]]] = {}
    for sheet in sheets:
        slug = str(sheet.get("slug") or "")
        if not slug or sheet.get("skip_table"):
            continue
        territory = resolve_demand_max_territory(sheet)
        if territory is None:
            continue
        spec = _KIND_TO_SUMMARY_ENTITY.get(str(territory.get("kind") or ""))
        if spec is None:
            continue
        model_name, fk_column = spec
        try:
            parent_id = int(territory["id"])
        except (TypeError, ValueError, KeyError):
            continue
        try:
            station_rows = _gaes_charge_raw_station_values_for_entity(
                version_id,
                model_name,
                fk_column,
                parent_id,
                years_tuple,
            )
        except Exception:
            continue
        year_map = year_values_from_gaes_charge_station_rows(station_rows, years)
        if year_map:
            inputs[slug] = {GAES_CHARGE_ROW_KEY: year_map}
    return inputs

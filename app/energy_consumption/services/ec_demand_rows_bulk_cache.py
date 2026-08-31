# -*- coding: utf-8 -*-
"""Пакетная загрузка строк параметров потребления для сводок (один SELECT на модель)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from flask import g, has_request_context

from app.common.perimeter_variant.registry import model_supports_perimeter_variant
from app.common.services.database_version_services import get_current_version
from app.energy_consumption.models.energy_systems.centralized_zone_energy_consumption_parameter_model import (
    CentralizedZoneEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.ees_energy_consumption_parameter_model import (
    EesEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.ees_russia_energy_consumption_parameter_model import (
    EesRussiaEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.energy_area_energy_consumption_parameter_model import (
    EnergyAreaEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.energy_system_type_energy_consumption_parameter_model import (
    EnergySystemTypeEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.energy_unit_energy_consumption_parameter_model import (
    EnergyUnitEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.energy_zone_energy_consumption_parameter_model import (
    EnergyZoneEnergyConsumptionParameter,
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
from app.energy_consumption.models.territories.federal_district_energy_consumption_parameter_model import (
    FederalDistrictEnergyConsumptionParameter,
)
from app.energy_consumption.models.territories.regional_district_energy_consumption_parameter_model import (
    RegionalDistrictEnergyConsumptionParameter,
)
from app.energy_consumption.models.territories.russia_federation_energy_consumption_parameter_model import (
    RussiaFederationEnergyConsumptionParameter,
)
from app.energy_consumption.services.energy_consumption_parameter_services import (
    filter_demand_by_version,
)

SUMMARY_ENERGY_CONSUMPTION_MODELS: tuple[type, ...] = (
    RussiaFederationEnergyConsumptionParameter,
    EesEnergyConsumptionParameter,
    EesRussiaEnergyConsumptionParameter,
    CentralizedZoneEnergyConsumptionParameter,
    EnergySystemTypeEnergyConsumptionParameter,
    SynchronousAreaEnergyConsumptionParameter,
    UnionEnergySystemEnergyConsumptionParameter,
    RegionalEnergySystemEnergyConsumptionParameter,
    RegionalDistrictEnergyConsumptionParameter,
    FederalDistrictEnergyConsumptionParameter,
    EnergyZoneEnergyConsumptionParameter,
    EnergyUnitEnergyConsumptionParameter,
    EnergyAreaEnergyConsumptionParameter,
)

DEMAND_MODEL_PARENT_FK: dict[type, str | None] = {
    RussiaFederationEnergyConsumptionParameter: None,
    EesEnergyConsumptionParameter: None,
    EesRussiaEnergyConsumptionParameter: None,
    CentralizedZoneEnergyConsumptionParameter: None,
    EnergySystemTypeEnergyConsumptionParameter: "id_energy_system_type",
    SynchronousAreaEnergyConsumptionParameter: "id_synchronous_area",
    UnionEnergySystemEnergyConsumptionParameter: "id_union_energy_system",
    RegionalEnergySystemEnergyConsumptionParameter: "id_regional_energy_system",
    RegionalDistrictEnergyConsumptionParameter: "id_regional_district",
    FederalDistrictEnergyConsumptionParameter: "id_federal_district",
    EnergyZoneEnergyConsumptionParameter: "id_energy_zone",
    EnergyUnitEnergyConsumptionParameter: "id_energy_unit",
    EnergyAreaEnergyConsumptionParameter: "id_energy_area",
}

_AGGREGATE_PARENT_KEY = "__aggregate__"


def activate_energy_consumption_rows_bulk() -> None:
    if has_request_context():
        g._ec_demand_rows_bulk_active = True


def is_energy_consumption_rows_bulk_active() -> bool:
    return bool(has_request_context() and g.get("_ec_demand_rows_bulk_active"))


def _model_store() -> dict[tuple[str, int | None], dict[Any, list[Any]]]:
    return g.setdefault("_ec_demand_rows_bulk_by_model", {})


def _sort_demand_rows(rows: list[Any], demand_model: type) -> list[Any]:
    has_hist = "is_historical_maximum" in demand_model.__table__.columns

    def _key(row: Any) -> tuple[int, int]:
        if has_hist and bool(getattr(row, "is_historical_maximum", False)):
            return (0, -1)
        year_number = getattr(row, "year_number", None)
        if year_number is None:
            return (1, -1)
        return (1, int(year_number))

    return sorted(rows, key=_key)


def _row_matches_pvc(row: Any, demand_model: type, pvc_filter: Any) -> bool:
    if not model_supports_perimeter_variant(demand_model):
        return True
    row_pvc = getattr(row, "perimeter_variant_code", None)
    if pvc_filter is None:
        return row_pvc is None
    return row_pvc == pvc_filter


def _ensure_model_bulk_loaded(demand_model: type) -> dict[Any, list[Any]]:
    version_id = get_current_version()
    store_key = (demand_model.__name__, version_id)
    store = _model_store()
    if store_key in store:
        return store[store_key]

    fk_column = DEMAND_MODEL_PARENT_FK.get(demand_model)
    q = demand_model.query
    q = filter_demand_by_version(q, demand_model)
    all_rows = q.all()

    by_parent: dict[Any, list[Any]] = defaultdict(list)
    for row in all_rows:
        if fk_column is None:
            parent_key = _AGGREGATE_PARENT_KEY
        else:
            parent_key = getattr(row, fk_column, None)
        by_parent[parent_key].append(row)

    store[store_key] = dict(by_parent)
    return store[store_key]


def preload_energy_consumption_rows_for_summary() -> None:
    """Eager load всех моделей, используемых на сводках потребления."""
    if not is_energy_consumption_rows_bulk_active():
        return
    for model in SUMMARY_ENERGY_CONSUMPTION_MODELS:
        _ensure_model_bulk_loaded(model)


def clear_energy_consumption_rows_bulk_cache() -> None:
    """Сброс in-request кэша после сохранения ячеек на той же странице."""
    if has_request_context():
        g.pop("_ec_demand_rows_bulk_by_model", None)


def get_demand_rows_from_bulk(
    demand_model: type,
    fk_column_name: str | None,
    parent_id: int | None,
    *,
    perimeter_variant_code: Any = None,
) -> list[Any]:
    by_parent = _ensure_model_bulk_loaded(demand_model)
    fk_column = DEMAND_MODEL_PARENT_FK.get(demand_model)
    if fk_column_name is not None and fk_column is not None and fk_column_name != fk_column:
        return []

    if fk_column is None:
        candidates = list(by_parent.get(_AGGREGATE_PARENT_KEY, ()))
    elif parent_id is None:
        return []
    else:
        candidates = list(by_parent.get(parent_id, ()))

    filtered = [
        row
        for row in candidates
        if _row_matches_pvc(row, demand_model, perimeter_variant_code)
    ]
    return _sort_demand_rows(filtered, demand_model)


def get_all_demand_rows_for_parent_from_bulk(
    demand_model: type,
    fk_column_name: str | None,
    parent_id: int | None,
) -> list[Any]:
    """Все строки родителя без фильтра варианта периметра (для peek кода)."""
    by_parent = _ensure_model_bulk_loaded(demand_model)
    fk_column = DEMAND_MODEL_PARENT_FK.get(demand_model)
    if fk_column_name is not None and fk_column is not None and fk_column_name != fk_column:
        return []
    if fk_column is None:
        candidates = list(by_parent.get(_AGGREGATE_PARENT_KEY, ()))
    elif parent_id is None:
        return []
    else:
        candidates = list(by_parent.get(parent_id, ()))
    return _sort_demand_rows(candidates, demand_model)

# -*- coding: utf-8 -*-
"""Пакетная загрузка строк параметров нагрузки для сводок (один SELECT на модель)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from flask import g, has_request_context

from app.common.perimeter_variant.registry import model_supports_perimeter_variant
from app.common.services.database_version_services import get_current_version
from app.power_demand.models.energy_systems.centralized_zone_demand_parameter_model import (
    CentralizedZoneDemandParameter,
)
from app.power_demand.models.energy_systems.ees_demand_parameter_model import (
    EesDemandParameter,
)
from app.power_demand.models.energy_systems.ees_russia_demand_parameter_model import (
    EesRussiaDemandParameter,
)
from app.power_demand.models.energy_systems.energy_system_type_demand_parameter_model import (
    EnergySystemTypeDemandParameter,
)
from app.power_demand.models.energy_systems.energy_unit_demand_parameter_model import (
    EnergyUnitDemandParameter,
)
from app.power_demand.models.energy_systems.energy_zone_demand_parameter_model import (
    EnergyZoneDemandParameter,
)
from app.power_demand.models.energy_systems.regional_energy_system_demand_parameter_model import (
    RegionalEnergySystemDemandParameter,
)
from app.power_demand.models.energy_systems.synchronous_area_demand_parameter_model import (
    SynchronousAreaDemandParameter,
)
from app.power_demand.models.energy_systems.union_energy_system_demand_parameter_model import (
    UnionEnergySystemDemandParameter,
)
from app.power_demand.models.territories.federal_district_demand_parameter_model import (
    FederalDistrictDemandParameter,
)
from app.power_demand.models.territories.regional_district_demand_parameter_model import (
    RegionalDistrictDemandParameter,
)
from app.power_demand.models.territories.russia_federation_demand_parameter_model import (
    RussiaFederationDemandParameter,
)
from app.power_demand.services.demand_parameter_services import (
    _UNSET,
    filter_demand_by_version,
)

SUMMARY_POWER_DEMAND_MODELS: tuple[type, ...] = (
    RussiaFederationDemandParameter,
    EesDemandParameter,
    EesRussiaDemandParameter,
    CentralizedZoneDemandParameter,
    EnergySystemTypeDemandParameter,
    SynchronousAreaDemandParameter,
    UnionEnergySystemDemandParameter,
    RegionalEnergySystemDemandParameter,
    RegionalDistrictDemandParameter,
    FederalDistrictDemandParameter,
    EnergyZoneDemandParameter,
    EnergyUnitDemandParameter,
)

DEMAND_MODEL_PARENT_FK: dict[type, str | None] = {
    RussiaFederationDemandParameter: None,
    EesDemandParameter: None,
    EesRussiaDemandParameter: None,
    CentralizedZoneDemandParameter: None,
    EnergySystemTypeDemandParameter: "id_energy_system_type",
    SynchronousAreaDemandParameter: "id_synchronous_area",
    UnionEnergySystemDemandParameter: "id_union_energy_system",
    RegionalEnergySystemDemandParameter: "id_regional_energy_system",
    RegionalDistrictDemandParameter: "id_regional_district",
    FederalDistrictDemandParameter: "id_federal_district",
    EnergyZoneDemandParameter: "id_energy_zone",
    EnergyUnitDemandParameter: "id_energy_unit",
}

_AGGREGATE_PARENT_KEY = "__aggregate__"


def activate_power_demand_rows_bulk() -> None:
    if has_request_context():
        g._pd_demand_rows_bulk_active = True


def is_power_demand_rows_bulk_active() -> bool:
    return bool(has_request_context() and g.get("_pd_demand_rows_bulk_active"))


def _model_store() -> dict[tuple[str, int | None], dict[Any, list[Any]]]:
    return g.setdefault("_pd_demand_rows_bulk_by_model", {})


def _sort_demand_rows(rows: list[Any]) -> list[Any]:
    def _key(row: Any) -> tuple[int, int]:
        is_hist = bool(getattr(row, "is_historical_maximum", False))
        year_number = getattr(row, "year_number", None)
        if is_hist:
            return (0, -1)
        if year_number is None:
            return (1, -1)
        return (1, int(year_number))

    return sorted(rows, key=_key)


def _effective_pvc_filter(demand_model: type, perimeter_variant_code: Any) -> Any:
    if perimeter_variant_code is not _UNSET:
        return perimeter_variant_code
    if model_supports_perimeter_variant(demand_model):
        return None
    return _UNSET


def _row_matches_pvc(row: Any, demand_model: type, pvc_filter: Any) -> bool:
    if pvc_filter is _UNSET:
        return True
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


def preload_power_demand_rows_for_summary() -> None:
    """Eager load всех моделей, используемых на сводках нагрузок."""
    if not is_power_demand_rows_bulk_active():
        return
    for model in SUMMARY_POWER_DEMAND_MODELS:
        _ensure_model_bulk_loaded(model)


def clear_power_demand_rows_bulk_cache() -> None:
    """Сброс in-request кэша после сохранения ячеек на той же странице."""
    if has_request_context():
        g.pop("_pd_demand_rows_bulk_by_model", None)


def get_demand_rows_from_bulk(
    demand_model: type,
    fk_column_name: str | None,
    parent_id: int | None,
    *,
    perimeter_variant_code: Any = _UNSET,
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

    pvc_filter = _effective_pvc_filter(demand_model, perimeter_variant_code)
    filtered = [
        row
        for row in candidates
        if _row_matches_pvc(row, demand_model, pvc_filter)
    ]
    return _sort_demand_rows(filtered)


def get_demand_rows_for_summary_block_from_bulk(
    demand_model: type,
    fk_column_name: str | None,
    parent_id: int | None,
    *,
    display_perimeter_variant_code: str | None,
) -> list[Any]:
    """Сводка: legacy with_nt/without_nt + NULL/GAES в той же НТ-группе (bulk-кэш)."""
    from app.power_demand.services.demand_parameter_services import (
        _LEGACY_NT_TREE_DISPLAY_CODES,
        _merge_summary_demand_rows_by_slice,
    )
    from app.common.perimeter_variant.constants import (
        perimeter_variant_codes_prefer_without_gaes,
    )

    display = (
        str(display_perimeter_variant_code).strip()
        if display_perimeter_variant_code not in (None, "")
        else None
    )
    if display not in _LEGACY_NT_TREE_DISPLAY_CODES:
        return get_demand_rows_from_bulk(
            demand_model,
            fk_column_name,
            parent_id,
            perimeter_variant_code=display,
        )

    by_slice: dict[tuple[bool, int | None], Any] = {}
    pvc_order: list[Any] = list(perimeter_variant_codes_prefer_without_gaes(display))
    if None not in pvc_order:
        pvc_order.append(None)

    for idx, pvc in enumerate(pvc_order):
        _merge_summary_demand_rows_by_slice(
            by_slice,
            get_demand_rows_from_bulk(
                demand_model,
                fk_column_name,
                parent_id,
                perimeter_variant_code=pvc,
            ),
            prefer=(idx == 0),
        )
    return _sort_demand_rows(list(by_slice.values()))

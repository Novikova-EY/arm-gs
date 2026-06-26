# -*- coding: utf-8 -*-
"""ЧЧИ (число часов использования максимального потребления мощности) на сводках /summary/."""

from __future__ import annotations

from typing import Any

from app.common.perimeter_variant.constants import (
    CODE_WITHOUT_NT,
    CODE_WITH_NT,
    perimeter_variant_codes_prefer_without_gaes,
)
from app.power_demand.models.energy_systems.ees_russia_demand_parameter_model import (
    EesRussiaDemandParameter,
)
from app.power_demand.models.energy_systems.energy_system_type_demand_parameter_model import (
    EnergySystemTypeDemandParameter,
)
from app.energy_consumption.models.energy_systems.ees_russia_energy_consumption_parameter_model import (
    EesRussiaEnergyConsumptionParameter,
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
from app.energy_consumption.models.energy_systems.synchronous_area_energy_consumption_parameter_model import (
    SynchronousAreaEnergyConsumptionParameter,
)
from app.energy_consumption.models.territories.russia_federation_energy_consumption_parameter_model import (
    RussiaFederationEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.regional_energy_system_energy_consumption_parameter_model import (
    RegionalEnergySystemEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.union_energy_system_energy_consumption_parameter_model import (
    UnionEnergySystemEnergyConsumptionParameter,
)
from app.energy_consumption.models.territories.regional_district_energy_consumption_parameter_model import (
    RegionalDistrictEnergyConsumptionParameter,
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
from app.power_demand.models.territories.russia_federation_demand_parameter_model import (
    RussiaFederationDemandParameter,
)
from app.power_demand.models.territories.federal_district_demand_parameter_model import (
    FederalDistrictDemandParameter,
)
from app.power_demand.models.territories.regional_district_demand_parameter_model import (
    RegionalDistrictDemandParameter,
)
from app.energy_consumption.models.territories.federal_district_energy_consumption_parameter_model import (
    FederalDistrictEnergyConsumptionParameter,
)
from app.power_demand.services.demand_summary_services import (
    _format_full_numeric_tooltip,
    _format_numeric,
    _parse_summary_cell_float,
)

PEAK_MAX_POWER_USAGE_HOURS_KEY = "peak_max_power_usage_hours"
PEAK_MAX_POWER_USAGE_HOURS_LABEL = (
    "Число часов использования максимального потребления мощности"
)

_AGGREGATE_EC_PARENT_ID = 0

_PD_TO_EC: dict[str, tuple[type, str | None]] = {
    RussiaFederationDemandParameter.__name__: (
        RussiaFederationEnergyConsumptionParameter,
        None,
    ),
    EesRussiaDemandParameter.__name__: (EesRussiaEnergyConsumptionParameter, None),
    EnergySystemTypeDemandParameter.__name__: (
        EnergySystemTypeEnergyConsumptionParameter,
        "id_energy_system_type",
    ),
    SynchronousAreaDemandParameter.__name__: (
        SynchronousAreaEnergyConsumptionParameter,
        "id_synchronous_area",
    ),
    UnionEnergySystemDemandParameter.__name__: (
        UnionEnergySystemEnergyConsumptionParameter,
        "id_union_energy_system",
    ),
    RegionalEnergySystemDemandParameter.__name__: (
        RegionalEnergySystemEnergyConsumptionParameter,
        "id_regional_energy_system",
    ),
    FederalDistrictDemandParameter.__name__: (
        FederalDistrictEnergyConsumptionParameter,
        "id_federal_district",
    ),
    RegionalDistrictDemandParameter.__name__: (
        RegionalDistrictEnergyConsumptionParameter,
        "id_regional_district",
    ),
    EnergyUnitDemandParameter.__name__: (
        EnergyUnitEnergyConsumptionParameter,
        "id_energy_unit",
    ),
    EnergyZoneDemandParameter.__name__: (
        EnergyZoneEnergyConsumptionParameter,
        "id_energy_zone",
    ),
}

_OES_CHI_PD_MODELS = frozenset(_PD_TO_EC.keys())
# Потребление РФ в RussiaFederationEnergyConsumptionParameter хранится в млрд кВт·ч.
_RUSSIA_FEDERATION_EC_CHI_NUMERATOR_SCALE = 1000.0
# Итоговое ЧЧИ на сводках ОЭС / ФО / ЭЗ: (потребление, млн кВт·ч) / (мощность, МВт) × 1000.
_CHI_RESULT_DISPLAY_SCALE = 1000.0
_CHI_ROUNDING_DIGITS = 0


def _chi_ec_consumption_scale_for_pd_model(pd_model_name: str) -> float:
    if pd_model_name == RussiaFederationDemandParameter.__name__:
        return _RUSSIA_FEDERATION_EC_CHI_NUMERATOR_SCALE
    return 1.0


def _legacy_nt_display_code_for_chi_anchor(anchor: dict[str, Any]) -> str | None:
    if anchor.get("pd_pd_nt_extra_row"):
        return CODE_WITH_NT
    label = str(anchor.get("entity_label") or "")
    if "с НТ" in label and "без НТ" not in label:
        return CODE_WITH_NT
    if "без НТ" in label:
        return CODE_WITHOUT_NT
    return None


def _pd_perimeter_variant_code_for_chi_anchor(anchor: dict[str, Any]) -> str | None:
    code = str(anchor.get("perimeter_variant_code") or "").strip()
    if code:
        return code
    return _legacy_nt_display_code_for_chi_anchor(anchor)


def _chi_ec_consumption_pvc_for_anchor(anchor: dict[str, Any]) -> str | None:
    """Код варианта потребления ЭЭ для числителя ЧЧИ (тот же, что у max_power в блоке)."""
    return _pd_perimeter_variant_code_for_chi_anchor(anchor)


def _ec_parent_id_for_chi(
    pd_model_name: str,
    parent_id: int | None,
) -> int | None:
    fk_column = _PD_TO_EC[pd_model_name][1]
    if fk_column is None:
        return _AGGREGATE_EC_PARENT_ID
    if parent_id is None:
        return None
    return int(parent_id)


def _resolve_ec_parent_id_for_chi_block(
    anchor: dict[str, Any],
    *,
    ec_model_name: str,
    anchor_parent_id: int | None,
    fk_column: str | None,
    years: list[int],
    ec_index: dict[tuple[str, int, str | None, Any], float],
) -> int | None:
    """FK для числителя ЧЧИ: из строки сводки или единственный id из индекса потребления ЭЭ."""
    base_parent_id = _ec_parent_id_for_chi(
        str(anchor.get("demand_model_name") or ""),
        anchor_parent_id,
    )
    if base_parent_id is None or fk_column is None:
        return base_parent_id

    pvc_candidates = _ec_consumption_pvc_candidates_for_chi(anchor)
    slice_keys: list[Any] = ["hist", *[int(y) for y in years]]
    for slice_key in slice_keys:
        for pvc in pvc_candidates:
            if (
                _lookup_ec_consumption_direct(
                    ec_model_name,
                    int(base_parent_id),
                    pvc,
                    slice_key,
                    ec_index=ec_index,
                )
                is not None
            ):
                return int(base_parent_id)

    pvc_keys = {str(pvc) if pvc not in (None, "") else None for pvc in pvc_candidates}
    slice_key_set = set(slice_keys)
    matching_parent_ids: set[int] = set()
    for model_name, parent_id, pvc_key, slice_key in ec_index:
        if model_name != ec_model_name:
            continue
        if pvc_key not in pvc_keys:
            continue
        if slice_key not in slice_key_set:
            continue
        matching_parent_ids.add(int(parent_id))
    if len(matching_parent_ids) == 1:
        return next(iter(matching_parent_ids))
    return int(base_parent_id)


def _ec_consumption_pvc_candidates_for_chi(anchor: dict[str, Any]) -> list[str | None]:
    """Потребление ЭЭ для ЧЧИ — вариант периметра строки (с тем же порядком поиска, что у max_power)."""
    pvc = _chi_ec_consumption_pvc_for_anchor(anchor)
    if not pvc:
        return [None]
    candidates = list(perimeter_variant_codes_prefer_without_gaes(pvc))
    return candidates if candidates else [pvc]


def _lookup_ec_consumption_direct(
    ec_model_name: str,
    parent_id: int,
    pvc: str | None,
    slice_key: Any,
    *,
    ec_index: dict[tuple[str, int, str | None, Any], float],
) -> float | None:
    pvc_key = str(pvc) if pvc not in (None, "") else None
    return ec_index.get((ec_model_name, parent_id, pvc_key, slice_key))


def _lookup_ec_consumption_for_chi(
    ec_model_name: str,
    parent_id: int,
    anchor: dict[str, Any],
    slice_key: Any,
    *,
    ec_index: dict[tuple[str, int, str | None, Any], float],
    parent_fk_column: str | None,
    years: list[int],
) -> float | None:
    for pvc in _ec_consumption_pvc_candidates_for_chi(anchor):
        hit = _lookup_ec_consumption_direct(
            ec_model_name, parent_id, pvc, slice_key, ec_index=ec_index
        )
        if hit is not None:
            return hit
    return None


def _slice_key_from_ec_row(row: Any) -> Any:
    if getattr(row, "is_historical_maximum", False):
        return "hist"
    return getattr(row, "year_number", None)


def _build_ec_consumption_index(
    years: list[int],
) -> dict[tuple[str, int, str | None, Any], float]:
    """(ec_model_name, parent_id, pvc, slice) -> energy_consumption_mln_kvt_ch."""
    from app.power_demand.services.pd_ec_consumption_index_cache import (
        get_ec_consumption_index_for_years,
    )

    return get_ec_consumption_index_for_years(years)


def _chi_ec_consumption_mln_for_anchor(
    anchor: dict[str, Any],
    slice_key: Any,
    *,
    ec_index: dict[tuple[str, int, str | None, Any], float],
    ec_model_name: str,
    ec_parent_id: int,
    fk_column: str | None,
    years: list[int],
) -> float | None:
    hit = _lookup_ec_consumption_for_chi(
        ec_model_name,
        ec_parent_id,
        anchor,
        slice_key,
        ec_index=ec_index,
        parent_fk_column=fk_column,
        years=years,
    )
    if hit is None:
        return None
    scale = _chi_ec_consumption_scale_for_pd_model(
        str(anchor.get("demand_model_name") or "")
    )
    return hit * scale


def _divide_hours(ec_mln: float | None, max_mw: float | None) -> float | None:
    if ec_mln is None or max_mw is None:
        return None
    if abs(max_mw) < 1e-12:
        return None
    return ec_mln / max_mw * _CHI_RESULT_DISPLAY_SCALE


def _find_max_power_row(block: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in block:
        if str(row.get("parameter_key") or "") == "max_power":
            return row
    return None


def _insert_index_before_peak_datetime(
    summary_rows: list[dict[str, Any]],
    block_start: int,
    block_size: int,
) -> int:
    end = min(block_start + block_size, len(summary_rows))
    for i in range(block_start, end):
        if str(summary_rows[i].get("parameter_key") or "") == "peak_datetime":
            return i
    return block_start + 1


def _build_chi_row_for_block(
    block: list[dict[str, Any]],
    years: list[int],
    _rounding_digits: int,
    *,
    ec_index: dict[tuple[str, int, str | None, Any], float],
) -> dict[str, Any] | None:
    anchor = block[0]
    pd_model_name = str(anchor.get("demand_model_name") or "")
    if pd_model_name not in _OES_CHI_PD_MODELS:
        return None
    parent_id = anchor.get("parent_id")
    ec_model, fk_column = _PD_TO_EC[pd_model_name]
    ec_model_name = ec_model.__name__
    ec_index_local = ec_index
    ec_parent_id = _resolve_ec_parent_id_for_chi_block(
        anchor,
        ec_model_name=ec_model_name,
        anchor_parent_id=parent_id,
        fk_column=fk_column,
        years=years,
        ec_index=ec_index_local,
    )
    if ec_parent_id is None:
        return None
    max_power_row = _find_max_power_row(block)
    if max_power_row is None:
        return None

    year_values: list[str] = []
    year_tooltips: list[str] = []
    for ix, year in enumerate(years):
        ec_val = _chi_ec_consumption_mln_for_anchor(
            anchor,
            int(year),
            ec_index=ec_index,
            ec_model_name=ec_model_name,
            ec_parent_id=ec_parent_id,
            fk_column=fk_column,
            years=years,
        )
        mw_val = _parse_summary_cell_float(
            (max_power_row.get("year_values") or [None] * len(years))[ix]
        )
        hours = _divide_hours(ec_val, mw_val)
        if hours is None:
            year_values.append("—")
            year_tooltips.append("")
        else:
            year_values.append(_format_numeric(hours, _CHI_ROUNDING_DIGITS))
            year_tooltips.append(_format_full_numeric_tooltip(hours))

    hist_ec = _chi_ec_consumption_mln_for_anchor(
        anchor,
        "hist",
        ec_index=ec_index,
        ec_model_name=ec_model_name,
        ec_parent_id=ec_parent_id,
        fk_column=fk_column,
        years=years,
    )
    hist_mw = _parse_summary_cell_float(max_power_row.get("hist_value"))
    hist_hours = _divide_hours(hist_ec, hist_mw)
    if hist_hours is None:
        hist_value = "—"
        hist_tooltip = ""
    else:
        hist_value = _format_numeric(hist_hours, _CHI_ROUNDING_DIGITS)
        hist_tooltip = _format_full_numeric_tooltip(hist_hours)

    new_row = {
        "entity_label": anchor.get("entity_label"),
        "entity_rowspan": int(anchor.get("entity_rowspan") or len(block)) + 1,
        "entity_depth": anchor.get("entity_depth", 0),
        "entity_kind": anchor.get("entity_kind"),
        "show_entity_cell": False,
        "parameter_key": PEAK_MAX_POWER_USAGE_HOURS_KEY,
        "parameter_label": PEAK_MAX_POWER_USAGE_HOURS_LABEL,
        "demand_model_name": anchor.get("demand_model_name"),
        "parent_fk_column": anchor.get("parent_fk_column"),
        "parent_id": anchor.get("parent_id"),
        "hist_row_id": None,
        "year_row_ids": [None for _ in years],
        "hist_value": hist_value,
        "year_values": year_values,
        "hist_numeric_tooltip": hist_tooltip,
        "year_numeric_tooltips": year_tooltips,
        "id_union_energy_system": anchor.get("id_union_energy_system"),
        "id_regional_energy_system": anchor.get("id_regional_energy_system"),
        "id_regional_district": anchor.get("id_regional_district"),
        "id_energy_unit": anchor.get("id_energy_unit"),
        "perimeter_variant_code": _chi_ec_consumption_pvc_for_anchor(anchor)
        or anchor.get("perimeter_variant_code"),
        "year_coeff_k_stored": [],
        "entity_note_text": anchor.get("entity_note_text") or "",
        "entity_note_row_id": anchor.get("entity_note_row_id"),
        "show_entity_note_cell": False,
        "pd_pd_chi_row": True,
    }
    if anchor.get("pd_pd_decentralized_zone_mark"):
        new_row["pd_pd_decentralized_zone_mark"] = True
    if anchor.get("id_synchronous_area") is not None:
        new_row["id_synchronous_area"] = anchor.get("id_synchronous_area")
    if anchor.get("pd_pd_nt_extra_row"):
        new_row["pd_pd_nt_extra_row"] = True
    if anchor.get("pd_pd_territory_detail_row"):
        new_row["pd_pd_territory_detail_row"] = True
        new_row["pd_pd_territory_compact_hide_row"] = True
    elif anchor.get("pd_pd_territory_compact_hide_row"):
        new_row["pd_pd_territory_compact_hide_row"] = True
    return new_row


def inject_peak_usage_hours_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Добавляет строки ЧЧИ перед «Дата и время» для поддерживаемых сущностей сводки."""
    if not summary_rows or not years:
        return

    blocks: list[tuple[int, int, list[dict[str, Any]]]] = []
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if row.get("show_entity_cell"):
            span = int(row.get("entity_rowspan") or 1)
            block = summary_rows[i : i + span]
            dm = str(block[0].get("demand_model_name") or "")
            if dm in _OES_CHI_PD_MODELS and not any(
                str(r.get("parameter_key") or "") == PEAK_MAX_POWER_USAGE_HOURS_KEY
                for r in block
            ):
                blocks.append((i, span, block))
            i += span
        else:
            i += 1

    if not blocks:
        return

    ec_index = _build_ec_consumption_index(years)
    insertions: list[tuple[int, dict[str, Any], int, int]] = []
    for start, span, block in blocks:
        new_row = _build_chi_row_for_block(
            block,
            years,
            rounding_digits,
            ec_index=ec_index,
        )
        if new_row is None:
            continue
        insert_at = _insert_index_before_peak_datetime(summary_rows, start, span)
        insertions.append((insert_at, new_row, start, span))

    for insert_at, new_row, start, span in reversed(insertions):
        summary_rows.insert(insert_at, new_row)
        new_span = span + 1
        for k in range(start, start + new_span):
            summary_rows[k]["entity_rowspan"] = new_span


def inject_oes_peak_usage_hours_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Сводка /summary/oes/: строки ЧЧИ (обратная совместимость)."""
    inject_peak_usage_hours_rows(summary_rows, years, rounding_digits)

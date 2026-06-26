# -*- coding: utf-8 -*-
"""ЧЧИ производных синхронных зон (2-я СЗ, Калининград) на сводке ОЭС."""

from __future__ import annotations

from unittest.mock import patch

from app.power_demand.services.demand_summary_services import (
    _finalize_oes_summary_context,
)
from app.power_demand.services.pd_peak_usage_hours_services import (
    PEAK_MAX_POWER_USAGE_HOURS_KEY,
)
from app.power_demand.services.pd_summary_data_segments import PD_SUMMARY_SEGMENT_CHI


def _ues_chi_row(ues_id: int, year_values: list[str]) -> dict:
    return {
        "demand_model_name": "UnionEnergySystemDemandParameter",
        "parameter_key": PEAK_MAX_POWER_USAGE_HOURS_KEY,
        "parent_fk_column": "id_union_energy_system",
        "parent_id": ues_id,
        "id_union_energy_system": ues_id,
        "year_values": list(year_values),
        "year_numeric_tooltips": list(year_values),
        "hist_value": "6,0",
        "hist_numeric_tooltip": "6,0",
        "pd_pd_chi_row": True,
    }


def _res_chi_row(res_id: int, year_values: list[str]) -> dict:
    return {
        "demand_model_name": "RegionalEnergySystemDemandParameter",
        "parameter_key": PEAK_MAX_POWER_USAGE_HOURS_KEY,
        "parent_fk_column": "id_regional_energy_system",
        "parent_id": res_id,
        "id_regional_energy_system": res_id,
        "year_values": list(year_values),
        "year_numeric_tooltips": list(year_values),
        "hist_value": "5,9",
        "hist_numeric_tooltip": "5,9",
        "pd_pd_chi_row": True,
    }


def _sa_chi_row(sa_id: int, label: str) -> dict:
    return {
        "demand_model_name": "SynchronousAreaDemandParameter",
        "parameter_key": PEAK_MAX_POWER_USAGE_HOURS_KEY,
        "parent_fk_column": "id_synchronous_area",
        "parent_id": sa_id,
        "id_synchronous_area": sa_id,
        "entity_label": label,
        "year_values": ["—", "—"],
        "year_numeric_tooltips": ["", ""],
        "hist_value": "—",
        "hist_numeric_tooltip": "",
        "pd_pd_chi_row": True,
    }


@patch(
    "app.power_demand.services.demand_summary_services._resolve_union_energy_system_id_by_name_cf",
    return_value=7,
)
@patch(
    "app.power_demand.services.demand_summary_services._resolve_synchronous_area_id_by_name_prefix_cf",
    return_value=2,
)
@patch(
    "app.power_demand.services.demand_summary_services._resolve_kaliningrad_synchronous_area_id",
    return_value=3,
)
@patch(
    "app.power_demand.services.demand_summary_services._resolve_regional_energy_system_id_by_name_cf",
    return_value=99,
)
@patch(
    "app.power_demand.services.demand_summary_services._tag_common_power_demand_summary_rows",
)
@patch(
    "app.power_demand.services.demand_summary_services._filter_power_demand_summary_context_segments",
)
def test_finalize_oes_summary_copies_chi_for_derived_sync_areas(
    _filter_mock,
    _tag_mock,
    _res_mock,
    _kal_sa_mock,
    _second_sa_mock,
    _ues_mock,
) -> None:
    years = [2024, 2025]
    rows = [
        _ues_chi_row(7, ["6,1", "6,2"]),
        _res_chi_row(99, ["6,0", "6,3"]),
        _sa_chi_row(2, "Вторая синхронная зона"),
        _sa_chi_row(3, "Синхронная зона Калининградской области"),
    ]
    ctx = {"summary_rows": rows, "years": years}

    _finalize_oes_summary_context(ctx, rounding_digits=1, data_segments=frozenset({PD_SUMMARY_SEGMENT_CHI}))

    by_sa = {
        (r["parent_id"], r["entity_label"]): r
        for r in rows
        if r.get("demand_model_name") == "SynchronousAreaDemandParameter"
        and r.get("parameter_key") == PEAK_MAX_POWER_USAGE_HOURS_KEY
    }
    second = by_sa[(2, "Вторая синхронная зона")]
    kal = by_sa[(3, "Синхронная зона Калининградской области")]

    assert second["year_values"] == ["6,1", "6,2"]
    assert second["pd_formula_text_key"] == "sa_second_chi_from_ues_east"
    assert kal["year_values"] == ["6,0", "6,3"]
    assert kal["pd_formula_text_key"] == "sa_kaliningrad_chi_from_es"

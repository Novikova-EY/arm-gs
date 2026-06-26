# -*- coding: utf-8 -*-
"""Вторая синхронная зона на сводке ОЭС = ОЭС Востока."""

from __future__ import annotations

from unittest.mock import patch

from app.power_demand.services.demand_summary_services import (
    apply_second_sa_from_ues_east_formula,
)


def _ues_row(ues_id: int, parameter_key: str, year_values: list[str]) -> dict:
    return {
        "demand_model_name": "UnionEnergySystemDemandParameter",
        "parameter_key": parameter_key,
        "parent_fk_column": "id_union_energy_system",
        "parent_id": ues_id,
        "id_union_energy_system": ues_id,
        "year_values": list(year_values),
        "year_numeric_tooltips": list(year_values),
        "hist_value": "100",
        "hist_numeric_tooltip": "100",
    }


def _sa_row(sa_id: int, parameter_key: str) -> dict:
    return {
        "demand_model_name": "SynchronousAreaDemandParameter",
        "parameter_key": parameter_key,
        "parent_fk_column": "id_synchronous_area",
        "parent_id": sa_id,
        "id_synchronous_area": sa_id,
        "entity_label": "Вторая синхронная зона",
        "year_values": ["1"],
        "year_numeric_tooltips": ["1"],
        "hist_value": "",
        "hist_numeric_tooltip": "",
    }


@patch(
    "app.power_demand.services.demand_summary_services._resolve_union_energy_system_id_by_name_cf",
    return_value=7,
)
@patch(
    "app.power_demand.services.demand_summary_services._resolve_synchronous_area_id_by_name_prefix_cf",
    return_value=2,
)
def test_apply_second_sa_from_ues_east_copies_all_parameters(_sa_mock, _ues_mock) -> None:
    years = [2024]
    rows = [
        _ues_row(7, "max_power", ["500"]),
        _ues_row(7, "calculated_max_power_mw", ["510"]),
        _ues_row(7, "peak_datetime", ["01.01.2024 12:00"]),
        _ues_row(7, "avg_temp", ["-5"]),
        _ues_row(7, "combined_on_ees", ["520"]),
        _ues_row(7, "calculated_combined_on_ees_mw", ["530"]),
        _ues_row(7, "peak_max_power_usage_hours", ["6,1"]),
        _sa_row(2, "max_power"),
        _sa_row(2, "calculated_max_power_mw"),
        _sa_row(2, "peak_datetime"),
        _sa_row(2, "avg_temp"),
        _sa_row(2, "combined_on_ees"),
        _sa_row(2, "calculated_max_sa_mw"),
        _sa_row(2, "peak_max_power_usage_hours"),
    ]

    apply_second_sa_from_ues_east_formula(rows, years, 0)

    sa_rows = [r for r in rows if r["demand_model_name"] == "SynchronousAreaDemandParameter"]
    assert len(sa_rows) == 7
    for row in sa_rows:
        assert row.get("pd_pd_formula_derived_row") is True
        assert row.get("pd_formula_text_key")

    by_pk = {r["parameter_key"]: r for r in sa_rows}
    assert by_pk["max_power"]["year_values"] == ["500"]
    assert by_pk["calculated_max_power_mw"]["year_values"] == ["510"]
    assert by_pk["peak_datetime"]["year_values"] == ["01.01.2024 12:00"]
    assert by_pk["avg_temp"]["year_values"] == ["-5"]
    assert by_pk["combined_on_ees"]["year_values"] == ["520"]
    assert by_pk["calculated_max_sa_mw"]["year_values"] == ["530"]
    assert by_pk["max_power"]["hist_value"] == "100"
    assert by_pk["peak_max_power_usage_hours"]["year_values"] == ["6,1"]
    assert by_pk["peak_max_power_usage_hours"]["pd_formula_text_key"] == (
        "sa_second_chi_from_ues_east"
    )

# -*- coding: utf-8 -*-
"""Синхронная зона Калининградской области на сводке ОЭС = ЭС Калининградской области."""

from __future__ import annotations

from unittest.mock import patch

from app.power_demand.services.demand_summary_services import (
    apply_kaliningrad_sa_from_kaliningrad_es_formula,
)


def _res_row(res_id: int, parameter_key: str, year_values: list[str]) -> dict:
    return {
        "demand_model_name": "RegionalEnergySystemDemandParameter",
        "parameter_key": parameter_key,
        "parent_fk_column": "id_regional_energy_system",
        "parent_id": res_id,
        "id_regional_energy_system": res_id,
        "year_values": list(year_values),
        "year_numeric_tooltips": list(year_values),
        "hist_value": "200",
        "hist_numeric_tooltip": "200",
    }


def _sa_row(sa_id: int, parameter_key: str) -> dict:
    return {
        "demand_model_name": "SynchronousAreaDemandParameter",
        "parameter_key": parameter_key,
        "parent_fk_column": "id_synchronous_area",
        "parent_id": sa_id,
        "id_synchronous_area": sa_id,
        "entity_label": "Синхронная зона Калининградской области",
        "year_values": ["1"],
        "year_numeric_tooltips": ["1"],
        "hist_value": "",
        "hist_numeric_tooltip": "",
    }


@patch(
    "app.power_demand.services.demand_summary_services._resolve_regional_energy_system_id_by_name_cf",
    return_value=99,
)
@patch(
    "app.power_demand.services.demand_summary_services._resolve_kaliningrad_synchronous_area_id",
    return_value=3,
)
def test_apply_kaliningrad_sa_from_es_copies_all_parameters(_sa_mock, _res_mock) -> None:
    years = [2024]
    rows = [
        _res_row(99, "max_power", ["300"]),
        _res_row(99, "peak_datetime", ["02.01.2024 15:00"]),
        _res_row(99, "avg_temp", ["-2"]),
        _res_row(99, "combined_on_ees", ["310"]),
        _res_row(99, "peak_max_power_usage_hours", ["6,0"]),
        _sa_row(3, "max_power"),
        _sa_row(3, "calculated_max_power_mw"),
        _sa_row(3, "peak_datetime"),
        _sa_row(3, "avg_temp"),
        _sa_row(3, "combined_on_ees"),
        _sa_row(3, "calculated_max_sa_mw"),
        _sa_row(3, "peak_max_power_usage_hours"),
    ]

    apply_kaliningrad_sa_from_kaliningrad_es_formula(rows, years, 0)

    sa_rows = [r for r in rows if r["demand_model_name"] == "SynchronousAreaDemandParameter"]
    assert len(sa_rows) == 7
    for row in sa_rows:
        assert row.get("pd_pd_formula_derived_row") is True
        assert row.get("pd_formula_text_key")

    by_pk = {r["parameter_key"]: r for r in sa_rows}
    assert by_pk["max_power"]["year_values"] == ["300"]
    assert by_pk["calculated_max_power_mw"]["year_values"] == ["300"]
    assert by_pk["peak_datetime"]["year_values"] == ["02.01.2024 15:00"]
    assert by_pk["avg_temp"]["year_values"] == ["-2"]
    assert by_pk["combined_on_ees"]["year_values"] == ["310"]
    assert by_pk["calculated_max_sa_mw"]["year_values"] == ["310"]
    assert by_pk["max_power"]["hist_value"] == "200"
    assert by_pk["peak_max_power_usage_hours"]["year_values"] == ["6,0"]
    assert by_pk["peak_max_power_usage_hours"]["pd_formula_text_key"] == (
        "sa_kaliningrad_chi_from_es"
    )

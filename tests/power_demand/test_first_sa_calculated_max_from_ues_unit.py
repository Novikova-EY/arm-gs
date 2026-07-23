# -*- coding: utf-8 -*-
"""Расчёт «Расчетное максимальное потребление мощности» первой синхронной зоны по ОЭС."""

from __future__ import annotations

from unittest.mock import patch

from app.power_demand.services.demand_summary_services import (
    enrich_oes_summary_calculated_max_power_sa_from_res_max_power,
)


def _sa_calc_row(
    *,
    sa_id: int,
    perimeter_variant_code: str,
    years: list[int],
    entity_label: str = "Первая синхронная зона",
) -> dict:
    n = len(years)
    return {
        "demand_model_name": "SynchronousAreaDemandParameter",
        "parameter_key": "calculated_max_power_mw",
        "parent_fk_column": "id_synchronous_area",
        "parent_id": sa_id,
        "id_synchronous_area": sa_id,
        "entity_label": entity_label,
        "perimeter_variant_code": perimeter_variant_code,
        "year_values": ["—"] * n,
        "year_numeric_tooltips": [""] * n,
        "show_entity_cell": True,
        "entity_rowspan": 1,
    }


def _ues_combined_on_ees_row(
    *,
    ues_id: int,
    year_values: list[str],
    perimeter_variant_code: str | None = None,
) -> dict:
    return {
        "demand_model_name": "UnionEnergySystemDemandParameter",
        "parameter_key": "combined_on_ees",
        "parent_fk_column": "id_union_energy_system",
        "parent_id": ues_id,
        "id_union_energy_system": ues_id,
        "year_values": list(year_values),
        "year_numeric_tooltips": list(year_values),
        "perimeter_variant_code": perimeter_variant_code,
        "show_entity_cell": True,
        "entity_rowspan": 1,
        "entity_label": f"ОЭС {ues_id}",
    }


def _kaliningrad_es_combined_on_ees_row(*, res_id: int, year_values: list[str]) -> dict:
    return {
        "demand_model_name": "RegionalEnergySystemDemandParameter",
        "parameter_key": "combined_on_ees",
        "parent_fk_column": "id_regional_energy_system",
        "parent_id": res_id,
        "id_regional_energy_system": res_id,
        "year_values": list(year_values),
        "year_numeric_tooltips": list(year_values),
        "show_entity_cell": True,
        "entity_rowspan": 1,
        "entity_label": "ЭС Калининградской области",
    }


@patch(
    "app.power_demand.services.demand_summary_services._build_res_to_synchronous_area_ids_map",
    return_value={},
)
@patch(
    "app.power_demand.services.demand_summary_services._resolve_kaliningrad_synchronous_area_id",
    return_value=None,
)
@patch(
    "app.power_demand.services.demand_summary_services._resolve_synchronous_area_id_by_name_prefix_cf",
    side_effect=lambda prefix: 1 if "первая" in prefix else (2 if "вторая" in prefix else None),
)
@patch(
    "app.power_demand.services.demand_summary_services._first_sa_ues_exclude_ids_for_nt_group",
    return_value=frozenset(),
)
@patch(
    "app.power_demand.services.demand_summary_services._union_energy_system_ids_for_synchronous_area",
    return_value=frozenset({10, 20}),
)
@patch(
    "app.power_demand.services.demand_summary_services._resolve_regional_energy_system_id_by_name_cf",
    return_value=99,
)
@patch(
    "app.power_demand.services.demand_summary_services.perimeter_variant_year_bounds_for_code",
    return_value=(None, None),
)
def test_first_sa_without_nt_sums_ues_combined_on_ees(
    _mock_bounds,
    _mock_kal_es_id,
    _mock_ues_ids,
    _mock_exclude,
    _mock_sa_ids,
    _mock_kal_sa,
    _mock_res_map,
) -> None:
    """Без ``_kaliningrad``: сумма combined_on_ees по ОЭС первой СЗ."""
    years = [2024, 2025]
    rows = [
        _sa_calc_row(
            sa_id=1,
            perimeter_variant_code="without_nt",
            years=years,
        ),
        _ues_combined_on_ees_row(
            ues_id=10, year_values=["100", "200"], perimeter_variant_code="without_nt"
        ),
        _ues_combined_on_ees_row(ues_id=20, year_values=["30", "40"]),
        # max_power ОЭС не должен участвовать в сумме
        {
            "demand_model_name": "UnionEnergySystemDemandParameter",
            "parameter_key": "max_power",
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 10,
            "id_union_energy_system": 10,
            "year_values": ["999", "999"],
            "year_numeric_tooltips": ["999", "999"],
            "perimeter_variant_code": "without_nt",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_label": "ОЭС 10",
        },
    ]

    enrich_oes_summary_calculated_max_power_sa_from_res_max_power(rows, years, 0)

    assert rows[0]["year_values"] == ["130", "240"]


@patch(
    "app.power_demand.services.demand_summary_services._build_res_to_synchronous_area_ids_map",
    return_value={},
)
@patch(
    "app.power_demand.services.demand_summary_services._resolve_kaliningrad_synchronous_area_id",
    return_value=None,
)
@patch(
    "app.power_demand.services.demand_summary_services._resolve_synchronous_area_id_by_name_prefix_cf",
    side_effect=lambda prefix: 1 if "первая" in prefix else (2 if "вторая" in prefix else None),
)
@patch(
    "app.power_demand.services.demand_summary_services._first_sa_ues_exclude_ids_for_nt_group",
    return_value=frozenset(),
)
@patch(
    "app.power_demand.services.demand_summary_services._union_energy_system_ids_for_synchronous_area",
    return_value=frozenset({10, 20}),
)
@patch(
    "app.power_demand.services.demand_summary_services._resolve_regional_energy_system_id_by_name_cf",
    return_value=99,
)
@patch(
    "app.power_demand.services.demand_summary_services.perimeter_variant_year_bounds_for_code",
    return_value=(None, None),
)
def test_first_sa_without_nt_kaliningrad_subtracts_all_years(
    _mock_bounds,
    _mock_kal_es_id,
    _mock_ues_ids,
    _mock_exclude,
    _mock_sa_ids,
    _mock_kal_sa,
    _mock_res_map,
) -> None:
    """``without_nt_*_kaliningrad`` без «Год с»: вычитание Калининграда по всем годам."""
    years = [2024, 2025]
    rows = [
        _sa_calc_row(
            sa_id=1,
            perimeter_variant_code="without_nt_without_gaes_kaliningrad",
            years=years,
        ),
        _ues_combined_on_ees_row(
            ues_id=10, year_values=["100", "200"], perimeter_variant_code="without_nt"
        ),
        _ues_combined_on_ees_row(ues_id=20, year_values=["30", "40"]),
        _kaliningrad_es_combined_on_ees_row(res_id=99, year_values=["5", "7"]),
        # max_power Калининграда не должен участвовать в вычитании
        {
            "demand_model_name": "RegionalEnergySystemDemandParameter",
            "parameter_key": "max_power",
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 99,
            "id_regional_energy_system": 99,
            "year_values": ["50", "70"],
            "year_numeric_tooltips": ["50", "70"],
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_label": "ЭС Калининградской области",
        },
    ]

    enrich_oes_summary_calculated_max_power_sa_from_res_max_power(rows, years, 0)

    assert rows[0]["year_values"] == ["125", "233"]


@patch(
    "app.power_demand.services.demand_summary_services._build_res_to_synchronous_area_ids_map",
    return_value={},
)
@patch(
    "app.power_demand.services.demand_summary_services._resolve_kaliningrad_synchronous_area_id",
    return_value=None,
)
@patch(
    "app.power_demand.services.demand_summary_services._resolve_synchronous_area_id_by_name_prefix_cf",
    side_effect=lambda prefix: 1 if "первая" in prefix else (2 if "вторая" in prefix else None),
)
@patch(
    "app.power_demand.services.demand_summary_services._first_sa_ues_exclude_ids_for_nt_group",
    return_value=frozenset(),
)
@patch(
    "app.power_demand.services.demand_summary_services._union_energy_system_ids_for_synchronous_area",
    return_value=frozenset({10, 20}),
)
@patch(
    "app.power_demand.services.demand_summary_services._resolve_regional_energy_system_id_by_name_cf",
    return_value=99,
)
@patch(
    "app.power_demand.services.demand_summary_services.perimeter_variant_year_bounds_for_code",
    return_value=(2025, None),
)
def test_first_sa_with_nt_kaliningrad_subtracts_from_year_from(
    _mock_bounds,
    _mock_kal_es_id,
    _mock_ues_ids,
    _mock_exclude,
    _mock_sa_ids,
    _mock_kal_sa,
    _mock_res_map,
) -> None:
    """``with_nt_*_kaliningrad`` с «Год с»=2025: сумма ОЭС всегда; вычитание только с 2025."""
    years = [2024, 2025]
    rows = [
        _sa_calc_row(
            sa_id=1,
            perimeter_variant_code="with_nt_without_gaes_kaliningrad",
            years=years,
        ),
        _ues_combined_on_ees_row(
            ues_id=10, year_values=["100", "200"], perimeter_variant_code="with_nt"
        ),
        _ues_combined_on_ees_row(ues_id=20, year_values=["30", "40"]),
        _kaliningrad_es_combined_on_ees_row(res_id=99, year_values=["5", "7"]),
    ]

    enrich_oes_summary_calculated_max_power_sa_from_res_max_power(rows, years, 0)

    # 2024: сумма ОЭС без вычитания Калининграда; 2025: 240 − 7 (combined_on_ees)
    assert rows[0]["year_values"] == ["130", "233"]


@patch(
    "app.power_demand.services.demand_summary_services._build_res_to_synchronous_area_ids_map",
    return_value={},
)
@patch(
    "app.power_demand.services.demand_summary_services._resolve_kaliningrad_synchronous_area_id",
    return_value=None,
)
@patch(
    "app.power_demand.services.demand_summary_services._resolve_synchronous_area_id_by_name_prefix_cf",
    side_effect=lambda prefix: 1 if "первая" in prefix else (2 if "вторая" in prefix else None),
)
@patch(
    "app.power_demand.services.demand_summary_services._first_sa_ues_exclude_ids_for_nt_group",
    return_value=frozenset(),
)
@patch(
    "app.power_demand.services.demand_summary_services._union_energy_system_ids_for_synchronous_area",
    return_value=frozenset({10, 20}),
)
@patch(
    "app.power_demand.services.demand_summary_services._resolve_regional_energy_system_id_by_name_cf",
    return_value=99,
)
@patch(
    "app.power_demand.services.demand_summary_services.perimeter_variant_year_bounds_for_code",
    return_value=(2025, None),
)
def test_first_sa_without_nt_kaliningrad_formula_before_year_from_no_subtract(
    _mock_bounds,
    _mock_kal_es_id,
    _mock_ues_ids,
    _mock_exclude,
    _mock_sa_ids,
    _mock_kal_sa,
    _mock_res_map,
) -> None:
    """``without_nt_*_kaliningrad``: до «Год с» формула есть, Калининград не вычитается."""
    years = [2017, 2025]
    rows = [
        _sa_calc_row(
            sa_id=1,
            perimeter_variant_code="without_nt_without_gaes_kaliningrad",
            years=years,
        ),
        _ues_combined_on_ees_row(
            ues_id=10, year_values=["100", "200"], perimeter_variant_code="without_nt"
        ),
        _ues_combined_on_ees_row(ues_id=20, year_values=["30", "40"]),
        _kaliningrad_es_combined_on_ees_row(res_id=99, year_values=["5", "7"]),
    ]

    enrich_oes_summary_calculated_max_power_sa_from_res_max_power(rows, years, 0)

    assert rows[0]["year_values"] == ["130", "233"]

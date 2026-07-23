# -*- coding: utf-8 -*-
"""Расчёт «Расчетное максимальное потребление мощности» для агрегата «ЕЭС России» на сводке по ОЭС."""

from __future__ import annotations

from unittest.mock import patch

from app.power_demand.services.demand_summary_services import (
    enrich_oes_ees_russia_calculated_max_russia_mw,
)


def _ues_row(
    *,
    ues_id: int,
    pk: str,
    year_values: list[str],
    show_entity_cell: bool = False,
    perimeter_variant_code: str | None = None,
) -> dict:
    return {
        "demand_model_name": "UnionEnergySystemDemandParameter",
        "parameter_key": pk,
        "parent_fk_column": "id_union_energy_system",
        "parent_id": ues_id,
        "id_union_energy_system": ues_id,
        "year_values": list(year_values),
        "year_numeric_tooltips": list(year_values),
        "show_entity_cell": show_entity_cell,
        "entity_rowspan": 1,
        "entity_label": f"ОЭС {ues_id}",
        "entity_kind": "union_energy_system",
        "perimeter_variant_code": perimeter_variant_code,
    }


def _ees_russia_block(*, variant: str | None = None) -> list[dict]:
    return [
        {
            "demand_model_name": "EnergySystemTypeDemandParameter",
            "parameter_key": "max_power",
            "show_entity_cell": True,
            "entity_rowspan": 2,
            "entity_label": "ЕЭС России без НТ",
            "perimeter_variant_code": variant,
            "year_values": ["100"],
            "year_numeric_tooltips": ["100"],
        },
        {
            "demand_model_name": "EnergySystemTypeDemandParameter",
            "parameter_key": "calculated_max_ees_russia_mw",
            "show_entity_cell": False,
            "entity_rowspan": 1,
            "perimeter_variant_code": variant,
            "year_values": ["—"],
            "year_numeric_tooltips": [""],
        },
    ]


@patch(
    "app.power_demand.services.demand_summary_services._union_energy_system_ids_for_energy_system_type",
    return_value=frozenset({1, 2}),
)
def test_ees_russia_calculated_max_sums_ues_combined_on_ees(_mock_ues_ids) -> None:
    """«Расчетное максимальное потребление мощности» = сумма combined_on_ees по ОЭС (не calculated_combined)."""
    years = [2025]
    rows = _ees_russia_block(variant="without_nt_without_gaes") + [
        _ues_row(ues_id=1, pk="combined_on_ees", year_values=["40 568"], show_entity_cell=True),
        _ues_row(ues_id=1, pk="calculated_combined_on_ees_mw", year_values=["1"]),
        _ues_row(ues_id=2, pk="combined_on_ees", year_values=["17 293"], show_entity_cell=True),
        _ues_row(ues_id=2, pk="calculated_combined_on_ees_mw", year_values=["999"]),
    ]
    rows[0]["entity_rowspan"] = len(rows)

    enrich_oes_ees_russia_calculated_max_russia_mw(
        rows, years, rounding_digits=0, filter_year_list=years
    )

    calc_row = next(
        r for r in rows if r.get("parameter_key") == "calculated_max_ees_russia_mw"
    )
    assert calc_row["year_values"] == ["57 861"]


@patch(
    "app.power_demand.services.demand_summary_services._union_energy_system_ids_for_energy_system_type",
    return_value=frozenset({10}),
)
def test_ees_russia_calculated_max_via_es_sums_res_with_subject_fallback(_mock_ues_ids) -> None:
    """«Через РЭС» = сумма combined_on_ees по РЭС; пустая РЭС — сумма по субъектам."""
    from app.power_demand.services.demand_summary_services import (
        enrich_oes_ees_russia_calculated_max_via_es,
    )

    years = [2025]
    rows = _ees_russia_block(variant="without_nt_without_gaes") + [
        {
            "demand_model_name": "EnergySystemTypeDemandParameter",
            "parameter_key": "calculated_max_ees_via_es_mw",
            "show_entity_cell": False,
            "entity_rowspan": 1,
            "perimeter_variant_code": "without_nt_without_gaes",
            "year_values": ["—"],
            "year_numeric_tooltips": [""],
        },
        _ues_row(ues_id=10, pk="combined_on_ees", year_values=[""], show_entity_cell=True),
        {
            "demand_model_name": "RegionalEnergySystemDemandParameter",
            "parameter_key": "combined_on_ees",
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 101,
            "id_union_energy_system": 10,
            "id_regional_energy_system": 101,
            "year_values": ["—"],
            "year_numeric_tooltips": [""],
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_label": "РЭС тест",
        },
        {
            "demand_model_name": "RegionalDistrictDemandParameter",
            "parameter_key": "combined_on_ees",
            "parent_fk_column": "id_regional_district",
            "parent_id": 201,
            "id_union_energy_system": 10,
            "id_regional_energy_system": 101,
            "id_regional_district": 201,
            "year_values": ["1 000"],
            "year_numeric_tooltips": ["1 000"],
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_label": "Субъект 1",
        },
        {
            "demand_model_name": "RegionalDistrictDemandParameter",
            "parameter_key": "combined_on_ees",
            "parent_fk_column": "id_regional_district",
            "parent_id": 202,
            "id_union_energy_system": 10,
            "id_regional_energy_system": 101,
            "id_regional_district": 202,
            "year_values": ["500"],
            "year_numeric_tooltips": ["500"],
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_label": "Субъект 2",
        },
    ]
    rows[0]["entity_rowspan"] = len(rows)

    enrich_oes_ees_russia_calculated_max_via_es(rows, years, rounding_digits=0)

    via_es = next(
        r for r in rows if r.get("parameter_key") == "calculated_max_ees_via_es_mw"
    )
    assert via_es["year_values"] == ["1 500"]


@patch(
    "app.power_demand.services.demand_summary_services._union_energy_system_ids_for_energy_system_type",
    return_value=frozenset({1, 2}),
)
@patch(
    "app.power_demand.services.demand_summary_services._new_territories_regional_district_ids",
    return_value=frozenset({901}),
)
@patch(
    "app.power_demand.services.demand_summary_services._south_ues_ids_for_nt_enrichment",
    return_value=frozenset({2}),
)
def test_ees_russia_with_nt_equals_without_nt_plus_nt_subjects(
    _mock_south, _mock_nt_ids, _mock_ues_ids
) -> None:
    """ЕЭС с НТ = сумма ОЭС как у без НТ + Σ combined_on_ees субъектов НТ."""
    years = [2025]
    without = _ees_russia_block(variant="without_nt")
    without[0]["entity_label"] = "ЕЭС России без НТ"
    with_nt = [
        {
            "demand_model_name": "EnergySystemTypeDemandParameter",
            "parameter_key": "max_power",
            "show_entity_cell": True,
            "entity_rowspan": 2,
            "entity_label": "ЕЭС России с НТ",
            "perimeter_variant_code": "with_nt",
            "year_values": ["100"],
            "year_numeric_tooltips": ["100"],
        },
        {
            "demand_model_name": "EnergySystemTypeDemandParameter",
            "parameter_key": "calculated_max_ees_russia_mw",
            "show_entity_cell": False,
            "entity_rowspan": 1,
            "perimeter_variant_code": "with_nt",
            "year_values": ["—"],
            "year_numeric_tooltips": [""],
        },
    ]
    rows = (
        without
        + with_nt
        + [
            _ues_row(
                ues_id=1,
                pk="combined_on_ees",
                year_values=["10 000"],
                show_entity_cell=True,
            ),
            # ОЭС Юга без НТ — база для обеих агрегаций ЕЭС.
            _ues_row(
                ues_id=2,
                pk="combined_on_ees",
                year_values=["20 000"],
                show_entity_cell=True,
                perimeter_variant_code="without_nt",
            ),
            # ОЭС Юга с НТ — заниженное значение; не должно уменьшать ЕЭС с НТ.
            _ues_row(
                ues_id=2,
                pk="combined_on_ees",
                year_values=["1"],
                show_entity_cell=True,
                perimeter_variant_code="with_nt",
            ),
            {
                "demand_model_name": "RegionalDistrictDemandParameter",
                "parameter_key": "combined_on_ees",
                "parent_fk_column": "id_regional_district",
                "parent_id": 901,
                "id_union_energy_system": 2,
                "id_regional_district": 901,
                "year_values": ["500"],
                "year_numeric_tooltips": ["500"],
                "show_entity_cell": True,
                "entity_rowspan": 1,
                "entity_label": "НТ субъект",
            },
        ]
    )
    without[0]["entity_rowspan"] = 2
    with_nt[0]["entity_rowspan"] = 2

    enrich_oes_ees_russia_calculated_max_russia_mw(
        rows, years, rounding_digits=0, filter_year_list=years
    )

    calc_rows = [
        r for r in rows if r.get("parameter_key") == "calculated_max_ees_russia_mw"
    ]
    without_calc = next(
        r for r in calc_rows if r.get("perimeter_variant_code") == "without_nt"
    )
    with_nt_calc = next(
        r for r in calc_rows if r.get("perimeter_variant_code") == "with_nt"
    )
    assert without_calc["year_values"] == ["30 000"]
    assert with_nt_calc["year_values"] == ["30 500"]

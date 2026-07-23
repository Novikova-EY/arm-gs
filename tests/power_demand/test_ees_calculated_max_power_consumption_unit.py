# -*- coding: utf-8 -*-
"""Расчёт «Расчетное максимальное потребление мощности» для агрегата «ЭЭС России»."""

from __future__ import annotations

from unittest.mock import patch

from app.power_demand.services.demand_summary_services import (
    enrich_oes_ees_calculated_max_power_consumption,
)


def _eu_row(*, eu_id: int, year_values: list[str], label: str = "EU") -> dict:
    return {
        "demand_model_name": "EnergyUnitDemandParameter",
        "parameter_key": "max_power",
        "parent_fk_column": "id_energy_unit",
        "parent_id": eu_id,
        "id_energy_unit": eu_id,
        "year_values": list(year_values),
        "year_numeric_tooltips": list(year_values),
        "show_entity_cell": True,
        "entity_rowspan": 1,
        "entity_label": label,
    }


def _ees_aggregate_block(*, variant: str, label: str) -> list[dict]:
    return [
        {
            "demand_model_name": "EesRussiaDemandParameter",
            "parameter_key": "max_power",
            "show_entity_cell": True,
            "entity_rowspan": 2,
            "entity_label": label,
            "perimeter_variant_code": variant,
            "year_values": ["—"],
            "year_numeric_tooltips": [""],
        },
        {
            "demand_model_name": "EesRussiaDemandParameter",
            "parameter_key": "calculated_max_power_consumption_mw",
            "show_entity_cell": False,
            "entity_rowspan": 1,
            "perimeter_variant_code": variant,
            "year_values": ["—"],
            "year_numeric_tooltips": [""],
        },
    ]


def _ees_russia_max_power_row(*, year_values: list[str]) -> dict:
    return {
        "demand_model_name": "EnergySystemTypeDemandParameter",
        "parameter_key": "max_power",
        "show_entity_cell": True,
        "entity_rowspan": 1,
        "entity_label": "ЕЭС России без НТ",
        "perimeter_variant_code": "without_nt_without_gaes",
        "year_values": list(year_values),
        "year_numeric_tooltips": list(year_values),
    }


@patch(
    "app.power_demand.services.demand_summary_services._ees_aggregate_formula_tites_energy_unit_ids",
    return_value=frozenset({11, 12}),
)
@patch(
    "app.power_demand.services.demand_summary_services._south_ues_ids_for_nt_enrichment",
    return_value=frozenset({2}),
)
@patch(
    "app.power_demand.services.demand_summary_services._new_territories_regional_district_ids",
    return_value=frozenset({901}),
)
def test_ees_without_nt_is_ees_russia_max_plus_raw_eu_max(
    _mock_nt_ids, _mock_south, _mock_eu_ids
) -> None:
    """Без НТ: max_power ЕЭС без НТ + сырые max_power энергорайонов (без поправок)."""
    years = [2025]
    without = _ees_aggregate_block(variant="without_nt", label="ЭЭС России без НТ")
    rows = without + [
        _ees_russia_max_power_row(year_values=["100 000"]),
        _eu_row(eu_id=11, year_values=["1 079"], label="Норильск"),
        _eu_row(eu_id=12, year_values=["294"], label="Камчатка"),
    ]
    without[0]["entity_rowspan"] = 2

    enrich_oes_ees_calculated_max_power_consumption(rows, years, rounding_digits=0)

    calc = next(
        r for r in rows if r.get("parameter_key") == "calculated_max_power_consumption_mw"
    )
    # 100000 + 1079 + 294 = 101373 (без −12 / −174.4)
    assert calc["year_values"] == ["101 373"]


@patch(
    "app.power_demand.services.demand_summary_services._ees_aggregate_formula_tites_energy_unit_ids",
    return_value=frozenset({11}),
)
@patch(
    "app.power_demand.services.demand_summary_services._south_ues_ids_for_nt_enrichment",
    return_value=frozenset({2}),
)
@patch(
    "app.power_demand.services.demand_summary_services._new_territories_regional_district_ids",
    return_value=frozenset({901}),
)
def test_ees_with_nt_adds_nt_subjects_max_power(
    _mock_nt_ids, _mock_south, _mock_eu_ids
) -> None:
    """С НТ: расчёт без НТ + сумма max_power субъектов «Новые территории»."""
    years = [2025]
    without = _ees_aggregate_block(variant="without_nt", label="ЭЭС России без НТ")
    with_nt = _ees_aggregate_block(variant="with_nt", label="ЭЭС России с НТ")
    rows = (
        without
        + with_nt
        + [
            _ees_russia_max_power_row(year_values=["50 000"]),
            _eu_row(eu_id=11, year_values=["100"], label="Норильск"),
            {
                "demand_model_name": "RegionalDistrictDemandParameter",
                "parameter_key": "max_power",
                "parent_fk_column": "id_regional_district",
                "parent_id": 901,
                "id_union_energy_system": 2,
                "id_regional_district": 901,
                "year_values": ["1 501"],
                "year_numeric_tooltips": ["1 501"],
                "show_entity_cell": True,
                "entity_rowspan": 1,
                "entity_label": "ДНР",
            },
        ]
    )
    without[0]["entity_rowspan"] = 2
    with_nt[0]["entity_rowspan"] = 2

    enrich_oes_ees_calculated_max_power_consumption(rows, years, rounding_digits=0)

    calc_rows = [
        r
        for r in rows
        if r.get("parameter_key") == "calculated_max_power_consumption_mw"
    ]
    without_calc = next(
        r for r in calc_rows if r.get("perimeter_variant_code") == "without_nt"
    )
    with_nt_calc = next(
        r for r in calc_rows if r.get("perimeter_variant_code") == "with_nt"
    )
    assert without_calc["year_values"] == ["50 100"]
    assert with_nt_calc["year_values"] == ["51 601"]

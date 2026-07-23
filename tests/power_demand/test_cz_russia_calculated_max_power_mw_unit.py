# -*- coding: utf-8 -*-
"""ЦЗ России: расчетное max_power = ЕЭС без НТ + энергорайоны формулы ЭЭС (+ НТ)."""

from __future__ import annotations

from unittest.mock import patch

from app.power_demand.services import demand_summary_services as dss


def _ees_russia_max_row(*, year_values: list[str], variant: str = "without_nt") -> dict:
    return {
        "show_entity_cell": True,
        "entity_label": "ЕЭС России без НТ",
        "entity_rowspan": 1,
        "entity_kind": "oes_top_aggregate",
        "demand_model_name": "EnergySystemTypeDemandParameter",
        "parameter_key": "max_power",
        "perimeter_variant_code": variant,
        "year_values": list(year_values),
        "year_numeric_tooltips": list(year_values),
        "hist_value": "",
    }


def _eu_max_row(*, eu_id: int, year_values: list[str], label: str = "EU") -> dict:
    return {
        "show_entity_cell": True,
        "entity_label": label,
        "entity_rowspan": 1,
        "entity_kind": "child",
        "demand_model_name": "EnergyUnitDemandParameter",
        "parameter_key": "max_power",
        "parent_fk_column": "id_energy_unit",
        "parent_id": eu_id,
        "id_energy_unit": eu_id,
        "perimeter_variant_code": None,
        "year_values": list(year_values),
        "year_numeric_tooltips": list(year_values),
        "hist_value": "",
    }


def _cz_block(*, pvc: str, year_values: list[str] | None = None) -> list[dict]:
    yv = list(year_values) if year_values is not None else ["—", "—"]
    n = len(yv)
    return [
        {
            "show_entity_cell": True,
            "entity_label": "ЦЗ России без НТ" if "without" in pvc else "ЦЗ России с НТ",
            "entity_rowspan": 2,
            "entity_kind": "centralized_zone",
            "demand_model_name": "CentralizedZoneDemandParameter",
            "parameter_key": "max_power",
            "perimeter_variant_code": pvc,
            "year_values": list(yv),
            "year_numeric_tooltips": [""] * n,
            "hist_value": "",
        },
        {
            "show_entity_cell": False,
            "entity_label": "ЦЗ России без НТ" if "without" in pvc else "ЦЗ России с НТ",
            "entity_rowspan": 2,
            "entity_kind": "centralized_zone",
            "demand_model_name": "CentralizedZoneDemandParameter",
            "parameter_key": "calculated_max_power_mw",
            "perimeter_variant_code": pvc,
            "year_values": ["—"] * n,
            "year_numeric_tooltips": [""] * n,
            "hist_value": "",
        },
    ]


def _cell_float(value: str) -> float:
    return float(
        str(value).replace("\xa0", "").replace(" ", "").replace(",", ".")
    )


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
def test_enrich_cz_without_nt_is_ees_russia_max_plus_formula_eu(
    _mock_nt_ids, _mock_south, _mock_eu_ids
) -> None:
    years = [2024, 2025]
    rows = [
        *_cz_block(pvc="without_nt"),
        _ees_russia_max_row(year_values=["100", "200"]),
        _eu_max_row(eu_id=11, year_values=["5", "6"], label="Норильск"),
        _eu_max_row(eu_id=12, year_values=["1", "2"], label="Камчатка"),
        # Энергорайон вне формулы в сумму не входит.
        {
            "show_entity_cell": True,
            "entity_label": "Другой ЭР",
            "entity_rowspan": 1,
            "demand_model_name": "EnergyUnitDemandParameter",
            "parameter_key": "max_power",
            "parent_fk_column": "id_energy_unit",
            "parent_id": 99,
            "id_energy_unit": 99,
            "perimeter_variant_code": None,
            "year_values": ["999", "999"],
            "year_numeric_tooltips": ["999", "999"],
            "hist_value": "",
        },
    ]
    dss.enrich_cz_russia_calculated_max_power_mw(rows, years, rounding_digits=1)

    calc = next(r for r in rows if r.get("parameter_key") == "calculated_max_power_mw")
    # 100+5+1 , 200+6+2
    assert _cell_float(calc["year_values"][0]) == 106.0
    assert _cell_float(calc["year_values"][1]) == 208.0
    assert calc.get("pd_pd_formula_derived_row") is True
    assert calc.get("pd_formula_text_key") == "cz_russia_calc_max_mw"


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
def test_enrich_cz_with_nt_adds_nt_subjects_max_power(
    _mock_nt_ids, _mock_south, _mock_eu_ids
) -> None:
    years = [2025]
    without = _cz_block(pvc="without_nt", year_values=["—"])
    without[0]["entity_rowspan"] = 2
    with_nt = _cz_block(pvc="with_nt", year_values=["—"])
    with_nt[0]["entity_rowspan"] = 2
    rows = (
        without
        + with_nt
        + [
            _ees_russia_max_row(year_values=["50 000"]),
            _eu_max_row(eu_id=11, year_values=["100"], label="Норильск"),
            {
                "demand_model_name": "RegionalDistrictDemandParameter",
                "parameter_key": "max_power",
                "parent_fk_column": "id_regional_district",
                "parent_id": 901,
                "id_regional_district": 901,
                "id_union_energy_system": 2,
                "year_values": ["1 501"],
                "year_numeric_tooltips": ["1 501"],
                "show_entity_cell": True,
                "entity_rowspan": 1,
                "entity_label": "ДНР",
            },
        ]
    )

    dss.enrich_cz_russia_calculated_max_power_mw(rows, years, rounding_digits=0)

    calc_rows = [
        r for r in rows if r.get("parameter_key") == "calculated_max_power_mw"
    ]
    without_calc = next(
        r for r in calc_rows if r.get("perimeter_variant_code") == "without_nt"
    )
    with_nt_calc = next(
        r for r in calc_rows if r.get("perimeter_variant_code") == "with_nt"
    )
    # without: 50000 + 100 = 50100
    assert without_calc["year_values"] == ["50 100"]
    # with NT: 50100 + 1501 = 51601
    assert with_nt_calc["year_values"] == ["51 601"]


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
def test_enrich_cz_o1_with_nt_variant_gets_nt_addon(
    _mock_nt_ids, _mock_south, _mock_eu_ids
) -> None:
    """Коды o1_with_nt / o1_without_nt тоже должны различать с/без НТ."""
    years = [2025]
    without = _cz_block(pvc="o1_without_nt", year_values=["—"])
    without[0]["entity_rowspan"] = 2
    with_nt = _cz_block(pvc="o1_with_nt", year_values=["—"])
    with_nt[0]["entity_rowspan"] = 2
    rows = (
        without
        + with_nt
        + [
            _ees_russia_max_row(year_values=["50 000"]),
            _eu_max_row(eu_id=11, year_values=["100"], label="Норильск"),
            {
                "demand_model_name": "RegionalDistrictDemandParameter",
                "parameter_key": "max_power",
                "parent_fk_column": "id_regional_district",
                "parent_id": 901,
                "id_regional_district": 901,
                "id_union_energy_system": 2,
                "year_values": ["1 501"],
                "year_numeric_tooltips": ["1 501"],
                "show_entity_cell": True,
                "entity_rowspan": 1,
                "entity_label": "ДНР",
            },
        ]
    )

    dss.enrich_cz_russia_calculated_max_power_mw(rows, years, rounding_digits=0)

    calc_rows = [
        r for r in rows if r.get("parameter_key") == "calculated_max_power_mw"
    ]
    without_calc = next(
        r for r in calc_rows if r.get("perimeter_variant_code") == "o1_without_nt"
    )
    with_nt_calc = next(
        r for r in calc_rows if r.get("perimeter_variant_code") == "o1_with_nt"
    )
    assert without_calc["year_values"] == ["50 100"]
    assert with_nt_calc["year_values"] == ["51 601"]


def test_inject_verify_for_cz_calculated_max_power() -> None:
    years = [2024]
    rows = [
        {
            "show_entity_cell": True,
            "entity_label": "ЦЗ России без НТ",
            "entity_rowspan": 2,
            "entity_kind": "centralized_zone",
            "demand_model_name": "CentralizedZoneDemandParameter",
            "parameter_key": "max_power",
            "perimeter_variant_code": "without_nt",
            "year_values": ["100"],
            "year_numeric_tooltips": [""],
            "hist_value": "",
        },
        {
            "show_entity_cell": False,
            "entity_label": "ЦЗ России без НТ",
            "entity_rowspan": 2,
            "entity_kind": "centralized_zone",
            "demand_model_name": "CentralizedZoneDemandParameter",
            "parameter_key": "calculated_max_power_mw",
            "perimeter_variant_code": "without_nt",
            "year_values": ["110"],
            "year_numeric_tooltips": ["110"],
            "hist_value": "",
        },
    ]
    dss._inject_oes_summary_verification_rows(rows, years)
    keys = [r.get("parameter_key") for r in rows]
    assert "verify_for_calculated_max_power_mw" in keys
    verify = next(
        r for r in rows if r.get("parameter_key") == "verify_for_calculated_max_power_mw"
    )
    assert verify.get("pd_pd_verify_for_row") is True
    assert _cell_float(verify["year_values"][0]) == 10.0


def test_parameters_cz_oes_summary_includes_calculated_max() -> None:
    keys = [pk for pk, _ in dss.PARAMETERS_CZ_OES_SUMMARY]
    assert keys == ["max_power", "calculated_max_power_mw", "peak_datetime"]

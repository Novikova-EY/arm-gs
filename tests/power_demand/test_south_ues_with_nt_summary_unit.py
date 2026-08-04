# -*- coding: utf-8 -*-
"""ОЭС Юга с НТ: расчётные строки и сумма субъектов «Новые территории»."""

from __future__ import annotations

from unittest.mock import patch

from app.power_demand.services.demand_summary_services import (
    _clear_south_ues_with_nt_formula_years_before,
    _inject_oes_summary_verification_rows,
    enrich_oes_summary_calculated_max_power_from_res_combined,
    enrich_south_ues_perimeter_calculated_combined_on_ees_from_res,
    enrich_south_ues_with_nt_calculated_max_power_from_res_and_nt_subjects,
    tag_power_demand_south_ues_without_nt_manual_rows,
)


def _south_ues_row(
    *,
    pk: str,
    year_values: list[str],
    perimeter_variant_code: str = "with_nt_without_gaes",
    ues_id: int = 100,
    entity_label: str = "ОЭС Юга",
) -> dict:
    return {
        "demand_model_name": "UnionEnergySystemDemandParameter",
        "parameter_key": pk,
        "parent_fk_column": "id_union_energy_system",
        "parent_id": ues_id,
        "id_union_energy_system": ues_id,
        "year_values": list(year_values),
        "year_numeric_tooltips": list(year_values),
        "entity_label": entity_label,
        "perimeter_variant_code": perimeter_variant_code,
    }


def _res_row(*, pk: str, year_values: list[str], ues_id: int = 100, res_id: int = 1) -> dict:
    return {
        "demand_model_name": "RegionalEnergySystemDemandParameter",
        "parameter_key": pk,
        "parent_fk_column": "id_regional_energy_system",
        "parent_id": res_id,
        "id_regional_energy_system": res_id,
        "id_union_energy_system": ues_id,
        "year_values": list(year_values),
        "year_numeric_tooltips": list(year_values),
    }


def _nt_subject_row(
    *,
    pk: str,
    year_values: list[str],
    ues_id: int = 100,
    rd_id: int = 9001,
) -> dict:
    return {
        "demand_model_name": "RegionalDistrictDemandParameter",
        "parameter_key": pk,
        "parent_fk_column": "id_regional_district",
        "parent_id": rd_id,
        "id_regional_district": rd_id,
        "id_union_energy_system": ues_id,
        "year_values": list(year_values),
        "year_numeric_tooltips": list(year_values),
    }


@patch(
    "app.power_demand.services.demand_summary_services._new_territories_regional_district_ids",
    return_value=frozenset({9001}),
)
@patch(
    "app.power_demand.services.demand_summary_services._south_ues_ids_for_nt_enrichment",
    return_value=frozenset({100}),
)
def test_south_ues_with_nt_uses_combined_on_oes_from_nt_subjects(
    _south_ids_mock,
    _nt_rd_mock,
) -> None:
    years = [2022, 2024]
    rows = [
        _south_ues_row(pk="calculated_max_power_mw", year_values=["—", "—"]),
        _res_row(pk="combined_on_oes", year_values=["50", "200"]),
        _nt_subject_row(pk="combined_on_oes", year_values=["30", "40"]),
        _nt_subject_row(pk="combined_on_es", year_values=["99", "99"]),
    ]

    enrich_south_ues_with_nt_calculated_max_power_from_res_and_nt_subjects(
        rows, years, rounding_digits=0
    )

    calc = next(r for r in rows if r["parameter_key"] == "calculated_max_power_mw")
    assert calc["year_values"][0] == "80"
    assert calc["year_values"][1] == "240"


@patch(
    "app.power_demand.services.demand_summary_services._new_territories_regional_district_ids",
    return_value=frozenset({9001}),
)
@patch(
    "app.power_demand.services.demand_summary_services._south_ues_ids_for_nt_enrichment",
    return_value=frozenset({100}),
)
def test_south_ues_with_nt_empty_when_nt_sum_zero(
    _south_ids_mock,
    _nt_rd_mock,
) -> None:
    years = [2022, 2024]
    rows = [
        _south_ues_row(pk="calculated_max_power_mw", year_values=["—", "—"]),
        _res_row(pk="combined_on_oes", year_values=["50", "200"]),
        _nt_subject_row(pk="combined_on_oes", year_values=["0", "40"]),
    ]

    enrich_south_ues_with_nt_calculated_max_power_from_res_and_nt_subjects(
        rows, years, rounding_digits=0
    )

    calc = next(r for r in rows if r["parameter_key"] == "calculated_max_power_mw")
    assert calc["year_values"][0] == "—"
    assert calc["year_values"][1] == "240"


@patch(
    "app.power_demand.services.demand_summary_services._new_territories_regional_district_ids",
    return_value=frozenset({9001}),
)
@patch(
    "app.power_demand.services.demand_summary_services._south_ues_ids_for_nt_enrichment",
    return_value=frozenset({100}),
)
def test_south_ues_with_nt_combined_on_ees_adds_nt_any_year(
    _south_ids_mock,
    _nt_rd_mock,
) -> None:
    years = [2022, 2024]
    rows = [
        _south_ues_row(pk="calculated_combined_on_ees_mw", year_values=["—", "—"]),
        _res_row(pk="combined_on_ees", year_values=["10", "100"]),
        _nt_subject_row(pk="combined_on_ees", year_values=["5", "15"]),
    ]

    enrich_south_ues_perimeter_calculated_combined_on_ees_from_res(
        rows, years, rounding_digits=0
    )

    calc = next(r for r in rows if r["parameter_key"] == "calculated_combined_on_ees_mw")
    assert calc["year_values"][0] == "15"
    assert calc["year_values"][1] == "115"


@patch(
    "app.power_demand.services.demand_summary_services._south_ues_ids_for_nt_enrichment",
    return_value=frozenset({100}),
)
def test_clear_south_ues_with_nt_verify_rows_outside_perimeter(_south_ids_mock) -> None:
    years = [2022, 2024]
    rows = [
        _south_ues_row(
            pk="calculated_max_power_mw",
            year_values=["100", "200"],
            perimeter_variant_code="with_nt_without_gaes",
            entity_label="ОЭС Юга с НТ",
        ),
        _south_ues_row(
            pk="max_power",
            year_values=["90", "190"],
            perimeter_variant_code="with_nt_without_gaes",
            entity_label="ОЭС Юга с НТ",
        ),
        _south_ues_row(
            pk="verify_for_calculated_max_power_mw",
            year_values=["10", "10"],
            perimeter_variant_code="with_nt_without_gaes",
            entity_label="ОЭС Юга с НТ",
        ),
    ]
    _inject_oes_summary_verification_rows(rows, years)
    _clear_south_ues_with_nt_formula_years_before(rows, years)

    verify = next(
        r for r in rows if r["parameter_key"] == "verify_for_calculated_max_power_mw"
    )
    assert verify["year_values"][0] == "10"
    assert verify["year_values"][1] == "10"


@patch(
    "app.power_demand.services.demand_summary_services._new_territories_regional_district_ids",
    return_value=frozenset(),
)
@patch(
    "app.power_demand.services.demand_summary_services._south_ues_ids_for_nt_enrichment",
    return_value=frozenset({100}),
)
def test_south_ues_without_nt_manual_rows_keep_db_calculated_values(
    _south_ids_mock,
    _nt_rd_mock,
) -> None:
    years = [2024, 2025]
    rows = [
        _south_ues_row(
            pk="calculated_max_power_mw",
            year_values=["9 999", "8 888"],
            perimeter_variant_code="without_nt_without_gaes",
            entity_label="ОЭС Юга без НТ без заряда ГАЭС",
        ),
        _south_ues_row(
            pk="calculated_combined_on_ees_mw",
            year_values=["7 777", "6 666"],
            perimeter_variant_code="without_nt_without_gaes",
            entity_label="ОЭС Юга без НТ без заряда ГАЭС",
        ),
        _res_row(pk="combined_on_oes", year_values=["50", "200"]),
        _res_row(pk="combined_on_ees", year_values=["10", "100"]),
    ]

    tag_power_demand_south_ues_without_nt_manual_rows(rows)
    enrich_oes_summary_calculated_max_power_from_res_combined(
        rows, years, rounding_digits=0
    )
    enrich_south_ues_with_nt_calculated_max_power_from_res_and_nt_subjects(
        rows, years, rounding_digits=0
    )
    enrich_south_ues_perimeter_calculated_combined_on_ees_from_res(
        rows, years, rounding_digits=0
    )

    calc_max = next(
        r
        for r in rows
        if r["parameter_key"] == "calculated_max_power_mw"
        and r["perimeter_variant_code"] == "without_nt_without_gaes"
    )
    calc_ees = next(
        r
        for r in rows
        if r["parameter_key"] == "calculated_combined_on_ees_mw"
        and r["perimeter_variant_code"] == "without_nt_without_gaes"
    )
    assert calc_max["year_values"] == ["9 999", "8 888"]
    assert calc_ees["year_values"] == ["7 777", "6 666"]

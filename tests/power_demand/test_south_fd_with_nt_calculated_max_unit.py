# -*- coding: utf-8 -*-
"""Южный ФО с НТ: расчётный max = без НТ (сумма РЭС) + combined_on_fo субъектов НТ."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.power_demand.services.demand_summary_services import (
    enrich_fo_summary_calculated_max_power_from_res_combined_on_fo,
    enrich_south_fd_with_nt_calculated_max_from_res_and_nt_subjects,
)


def _fd_row(
    *,
    pk: str,
    year_values: list[str],
    perimeter_variant_code: str,
    fd_id: int = 93,
    entity_label: str = "Южный ФО",
) -> dict:
    return {
        "demand_model_name": "FederalDistrictDemandParameter",
        "parameter_key": pk,
        "parent_fk_column": "id_federal_district",
        "parent_id": fd_id,
        "id_federal_district": fd_id,
        "year_values": list(year_values),
        "year_numeric_tooltips": list(year_values),
        "entity_label": entity_label,
        "perimeter_variant_code": perimeter_variant_code,
    }


def _res_row(
    *,
    pk: str,
    year_values: list[str],
    fd_id: int = 93,
    res_id: int = 1,
) -> dict:
    return {
        "demand_model_name": "RegionalEnergySystemDemandParameter",
        "parameter_key": pk,
        "parent_fk_column": "id_regional_energy_system",
        "parent_id": res_id,
        "id_regional_energy_system": res_id,
        "id_federal_district": fd_id,
        "year_values": list(year_values),
        "year_numeric_tooltips": list(year_values),
    }


def _nt_subject_row(
    *,
    pk: str,
    year_values: list[str],
    ues_id: int = 118,
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
    return_value=frozenset({9001, 9002}),
)
@patch(
    "app.power_demand.services.demand_summary_services._south_federal_district_for_nt_attachment",
    return_value=(SimpleNamespace(id=93), 118),
)
def test_south_fd_with_nt_calc_max_adds_nt_subjects_combined_on_fo(
    _south_fd_mock,
    _nt_rd_mock,
) -> None:
    years = [2022, 2024]
    rows = [
        _fd_row(
            pk="calculated_max_power_mw",
            year_values=["—", "—"],
            perimeter_variant_code="with_nt_without_gaes",
            entity_label="Южный ФО с НТ",
        ),
        _fd_row(
            pk="calculated_max_power_mw",
            year_values=["—", "—"],
            perimeter_variant_code="without_nt_without_gaes",
            entity_label="Южный ФО без НТ",
        ),
        _res_row(pk="combined_on_fo", year_values=["100", "200"]),
        _nt_subject_row(pk="combined_on_fo", year_values=["10", "40"], rd_id=9001),
        _nt_subject_row(pk="combined_on_fo", year_values=["5", "15"], rd_id=9002),
        # max_power не должен учитываться в добавке
        _nt_subject_row(pk="max_power", year_values=["99", "99"], rd_id=9001),
    ]

    enrich_fo_summary_calculated_max_power_from_res_combined_on_fo(
        rows, years, rounding_digits=0
    )
    enrich_south_fd_with_nt_calculated_max_from_res_and_nt_subjects(
        rows, years, rounding_digits=0
    )

    with_nt = next(
        r
        for r in rows
        if r["parameter_key"] == "calculated_max_power_mw"
        and r["perimeter_variant_code"] == "with_nt_without_gaes"
    )
    without_nt = next(
        r
        for r in rows
        if r["parameter_key"] == "calculated_max_power_mw"
        and r["perimeter_variant_code"] == "without_nt_without_gaes"
    )

    assert without_nt["year_values"] == ["100", "200"]
    assert with_nt["year_values"][0] == "115"
    assert with_nt["year_values"][1] == "255"


@patch(
    "app.power_demand.services.demand_summary_services._new_territories_regional_district_ids",
    return_value=frozenset({9001}),
)
@patch(
    "app.power_demand.services.demand_summary_services._south_federal_district_for_nt_attachment",
    return_value=(SimpleNamespace(id=93), 118),
)
def test_south_fd_with_nt_empty_when_nt_sum_zero(
    _south_fd_mock,
    _nt_rd_mock,
) -> None:
    years = [2022, 2024]
    rows = [
        _fd_row(
            pk="calculated_max_power_mw",
            year_values=["—", "—"],
            perimeter_variant_code="with_nt_without_gaes",
            entity_label="Южный ФО с НТ",
        ),
        _res_row(pk="combined_on_fo", year_values=["100", "200"]),
        _nt_subject_row(pk="combined_on_fo", year_values=["0", "40"]),
    ]

    enrich_fo_summary_calculated_max_power_from_res_combined_on_fo(
        rows, years, rounding_digits=0
    )
    enrich_south_fd_with_nt_calculated_max_from_res_and_nt_subjects(
        rows, years, rounding_digits=0
    )

    with_nt = rows[0]
    assert with_nt["year_values"][0] == "—"
    assert with_nt["year_values"][1] == "240"


@patch(
    "app.power_demand.services.demand_summary_services._nt_combined_on_fo_year_sums_from_demand",
    return_value=[None, 50.0],
)
@patch(
    "app.power_demand.services.demand_summary_services._new_territories_regional_district_ids",
    return_value=frozenset(),
)
@patch(
    "app.power_demand.services.demand_summary_services._south_federal_district_for_nt_attachment",
    return_value=(SimpleNamespace(id=93), 118),
)
def test_south_fd_with_nt_calc_max_falls_back_to_demand_combined_on_fo(
    _south_fd_mock,
    _nt_rd_mock,
    _demand_nt_mock,
) -> None:
    years = [2022, 2024]
    rows = [
        _fd_row(
            pk="calculated_max_power_mw",
            year_values=["—", "—"],
            perimeter_variant_code="with_nt_without_gaes",
            entity_label="Южный ФО с НТ",
        ),
        _res_row(pk="combined_on_fo", year_values=["100", "200"]),
    ]

    enrich_fo_summary_calculated_max_power_from_res_combined_on_fo(
        rows, years, rounding_digits=0
    )
    enrich_south_fd_with_nt_calculated_max_from_res_and_nt_subjects(
        rows, years, rounding_digits=0
    )

    with_nt = rows[0]
    assert with_nt["year_values"][0] == "—"
    assert with_nt["year_values"][1] == "250"

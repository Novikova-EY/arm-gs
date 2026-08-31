# -*- coding: utf-8 -*-
"""Coeff ФО/ЭЗ: расчётный максимум плановых (среднесрочных) лет = сумма совмещённых РЭС."""

from __future__ import annotations

from unittest.mock import patch

from app.power_demand.services.demand_summary_services import (
    enrich_summary_rows_coeff_k_columns,
)


def _fo_row(*, pk: str, year_values: list[str], show_entity_cell: bool, fd_id: int = 7) -> dict:
    return {
        "demand_model_name": "FederalDistrictDemandParameter",
        "parameter_key": pk,
        "parent_fk_column": "id_federal_district",
        "parent_id": fd_id,
        "id_federal_district": fd_id,
        "year_values": list(year_values),
        "year_numeric_tooltips": list(year_values),
        "show_entity_cell": show_entity_cell,
        "entity_rowspan": 2,
        "entity_label": "ФО тест",
        "entity_kind": "group",
    }


def _ez_row(*, pk: str, year_values: list[str], show_entity_cell: bool, ez_id: int = 3) -> dict:
    return {
        "demand_model_name": "EnergyZoneDemandParameter",
        "parameter_key": pk,
        "parent_fk_column": "id_energy_zone",
        "parent_id": ez_id,
        "id_energy_zone": ez_id,
        "year_values": list(year_values),
        "year_numeric_tooltips": list(year_values),
        "show_entity_cell": show_entity_cell,
        "entity_rowspan": 2,
        "entity_label": "ЭЗ тест",
        "entity_kind": "group",
    }


def _res_row(
    *,
    pk: str,
    year_values: list[str],
    res_id: int,
    fd_id: int | None = None,
    ez_id: int | None = None,
    show_entity_cell: bool = False,
) -> dict:
    row = {
        "demand_model_name": "RegionalEnergySystemDemandParameter",
        "parameter_key": pk,
        "parent_fk_column": "id_regional_energy_system",
        "parent_id": res_id,
        "id_regional_energy_system": res_id,
        "year_values": list(year_values),
        "year_numeric_tooltips": list(year_values),
        "show_entity_cell": show_entity_cell,
        "entity_rowspan": 2,
        "entity_kind": "child",
    }
    if fd_id is not None:
        row["id_federal_district"] = fd_id
    if ez_id is not None:
        row["id_energy_zone"] = ez_id
    return row


@patch(
    "app.power_demand.services.demand_summary_services._summary_rows_include_ues_blocks",
    return_value=False,
)
@patch(
    "app.power_demand.services.demand_summary_services.enrich_south_fd_with_nt_calculated_max_from_res_and_nt_subjects",
)
@patch(
    "app.power_demand.services.demand_summary_services.enrich_far_east_fd_calculated_max_from_res_and_tites_eus",
)
def test_fo_coeff_plan_year_calculated_max_sums_res_combined_on_fo(
    _far_east_mock, _south_mock, _ues_mock
) -> None:
    years = [2025, 2026]
    rows = [
        _fo_row(pk="max_power", year_values=["1000", "1100"], show_entity_cell=True),
        _fo_row(
            pk="calculated_max_power_mw",
            year_values=["900", "—"],
            show_entity_cell=False,
        ),
        _res_row(
            pk="max_power",
            year_values=["400", "500"],
            res_id=11,
            fd_id=7,
            show_entity_cell=True,
        ),
        _res_row(
            pk="combined_on_fo",
            year_values=["300", "350"],
            res_id=11,
            fd_id=7,
        ),
        _res_row(
            pk="max_power",
            year_values=["200", "250"],
            res_id=12,
            fd_id=7,
            show_entity_cell=True,
        ),
        _res_row(
            pk="combined_on_fo",
            year_values=["180", "220"],
            res_id=12,
            fd_id=7,
        ),
    ]
    enrich_summary_rows_coeff_k_columns(
        rows,
        years,
        rounding_digits=1,
        year_is_plan={2025: False, 2026: True},
        coeff_base_year=2025,
    )
    calc = next(r for r in rows if r.get("parameter_key") == "calculated_max_power_mw")
    assert calc["year_values"][1] == "570"


@patch(
    "app.power_demand.services.demand_summary_services._summary_rows_include_ues_blocks",
    return_value=False,
)
def test_ez_coeff_plan_year_calculated_max_sums_res_combined_on_ez(_ues_mock) -> None:
    years = [2025, 2026]
    rows = [
        _ez_row(pk="max_power", year_values=["800", "900"], show_entity_cell=True),
        _ez_row(
            pk="calculated_max_power_mw",
            year_values=["700", "—"],
            show_entity_cell=False,
        ),
        _res_row(
            pk="max_power",
            year_values=["300", "400"],
            res_id=21,
            ez_id=3,
            show_entity_cell=True,
        ),
        _res_row(
            pk="combined_on_ez",
            year_values=["240", "320"],
            res_id=21,
            ez_id=3,
        ),
        _res_row(
            pk="max_power",
            year_values=["150", "200"],
            res_id=22,
            ez_id=3,
            show_entity_cell=True,
        ),
        _res_row(
            pk="combined_on_ez",
            year_values=["120", "160"],
            res_id=22,
            ez_id=3,
        ),
    ]
    enrich_summary_rows_coeff_k_columns(
        rows,
        years,
        rounding_digits=1,
        year_is_plan={2025: False, 2026: True},
        coeff_base_year=2025,
    )
    calc = next(r for r in rows if r.get("parameter_key") == "calculated_max_power_mw")
    assert calc["year_values"][1] == "480"


def _rep5(v: str) -> list[str]:
    return [v] * 5


@patch(
    "app.power_demand.services.demand_summary_services._summary_rows_include_ues_blocks",
    return_value=False,
)
@patch(
    "app.power_demand.services.demand_summary_services.enrich_south_fd_with_nt_calculated_max_from_res_and_nt_subjects",
)
@patch(
    "app.power_demand.services.demand_summary_services.enrich_far_east_fd_calculated_max_from_res_and_tites_eus",
)
def test_fo_coeff_plan_year_calculated_max_from_gs5_when_res_combined_empty(
    _far_east_mock, _south_mock, _ues_mock
) -> None:
    """Плановый combined_on_fo пуст: k = СиПР (5 лет), МВт = k×max, сумма → расчётный max ФО."""
    years = [2021, 2022, 2023, 2024, 2025, 2026]
    plan = {y: y == 2026 for y in years}
    rows = [
        _fo_row(
            pk="max_power",
            year_values=_rep5("1000") + ["1100"],
            show_entity_cell=True,
        ),
        _fo_row(
            pk="calculated_max_power_mw",
            year_values=_rep5("800") + ["—"],
            show_entity_cell=False,
        ),
        _res_row(
            pk="max_power",
            year_values=_rep5("500") + ["550"],
            res_id=11,
            fd_id=7,
            show_entity_cell=True,
        ),
        _res_row(
            pk="combined_on_fo",
            year_values=_rep5("400") + ["—"],
            res_id=11,
            fd_id=7,
        ),
        _res_row(
            pk="max_power",
            year_values=_rep5("250") + ["275"],
            res_id=12,
            fd_id=7,
            show_entity_cell=True,
        ),
        _res_row(
            pk="combined_on_fo",
            year_values=_rep5("200") + ["—"],
            res_id=12,
            fd_id=7,
        ),
    ]
    enrich_summary_rows_coeff_k_columns(
        rows,
        years,
        rounding_digits=1,
        year_is_plan=plan,
        coeff_base_year=2025,
    )
    calc = next(r for r in rows if r.get("parameter_key") == "calculated_max_power_mw")
    assert calc["year_values"][5] == "660"
    res_fo = [
        r
        for r in rows
        if r.get("parameter_key") == "combined_on_fo"
        and r.get("demand_model_name") == "RegionalEnergySystemDemandParameter"
    ]
    assert res_fo[0]["year_values"][5] == "440"
    assert res_fo[1]["year_values"][5] == "220"


@patch(
    "app.power_demand.services.demand_summary_services._summary_rows_include_ues_blocks",
    return_value=False,
)
def test_ez_coeff_plan_year_calculated_max_from_gs5_when_res_combined_empty(
    _ues_mock,
) -> None:
    years = [2021, 2022, 2023, 2024, 2025, 2026]
    plan = {y: y == 2026 for y in years}
    rows = [
        _ez_row(
            pk="max_power",
            year_values=_rep5("800") + ["900"],
            show_entity_cell=True,
        ),
        _ez_row(
            pk="calculated_max_power_mw",
            year_values=_rep5("640") + ["—"],
            show_entity_cell=False,
        ),
        _res_row(
            pk="max_power",
            year_values=_rep5("300") + ["330"],
            res_id=21,
            ez_id=3,
            show_entity_cell=True,
        ),
        _res_row(
            pk="combined_on_ez",
            year_values=_rep5("240") + ["—"],
            res_id=21,
            ez_id=3,
        ),
        _res_row(
            pk="max_power",
            year_values=_rep5("150") + ["165"],
            res_id=22,
            ez_id=3,
            show_entity_cell=True,
        ),
        _res_row(
            pk="combined_on_ez",
            year_values=_rep5("120") + ["—"],
            res_id=22,
            ez_id=3,
        ),
    ]
    enrich_summary_rows_coeff_k_columns(
        rows,
        years,
        rounding_digits=1,
        year_is_plan=plan,
        coeff_base_year=2025,
    )
    calc = next(r for r in rows if r.get("parameter_key") == "calculated_max_power_mw")
    assert calc["year_values"][5] == "396"

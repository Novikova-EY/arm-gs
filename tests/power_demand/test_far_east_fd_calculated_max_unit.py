# -*- coding: utf-8 -*-
"""Дальневосточный ФО: расчётный max = сумма РЭС + max_power энергорайонов формулы."""

from __future__ import annotations

from unittest.mock import patch

from app.power_demand.services.demand_summary_services import (
    enrich_far_east_fd_calculated_max_from_res_and_tites_eus,
    enrich_fo_summary_calculated_max_power_from_res_combined_on_fo,
)


def _fd_row(
    *,
    pk: str,
    year_values: list[str],
    fd_id: int = 86,
    entity_label: str = "Дальневосточный ФО",
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
    }


def _res_row(
    *,
    pk: str,
    year_values: list[str],
    fd_id: int = 86,
    res_id: int = 1,
    ues_id: int | None = None,
) -> dict:
    row = {
        "demand_model_name": "RegionalEnergySystemDemandParameter",
        "parameter_key": pk,
        "parent_fk_column": "id_regional_energy_system",
        "parent_id": res_id,
        "id_regional_energy_system": res_id,
        "id_federal_district": fd_id,
        "year_values": list(year_values),
        "year_numeric_tooltips": list(year_values),
    }
    if ues_id is not None:
        row["id_union_energy_system"] = ues_id
    return row


def _eu_max_row(
    *,
    eu_id: int,
    year_values: list[str],
    label: str,
) -> dict:
    return {
        "demand_model_name": "EnergyUnitDemandParameter",
        "parameter_key": "max_power",
        "parent_fk_column": "id_energy_unit",
        "parent_id": eu_id,
        "id_energy_unit": eu_id,
        "entity_label": label,
        "year_values": list(year_values),
        "year_numeric_tooltips": list(year_values),
    }


@patch(
    "app.power_demand.services.demand_summary_services._sum_far_east_fd_formula_energy_units_max_power_from_demand",
    return_value=[None, None],
)
@patch(
    "app.power_demand.services.demand_summary_services._far_east_fd_formula_energy_unit_ids",
    return_value=frozenset({11, 12, 13, 14, 15}),
)
@patch(
    "app.power_demand.services.demand_summary_services._far_east_federal_district_id",
    return_value=86,
)
@patch(
    "app.power_demand.services.demand_summary_services._is_tites_branch_regional_energy_system_row",
    return_value=False,
)
def test_far_east_fd_calc_max_adds_formula_eu_max_power(
    _tites_mock,
    _fd_id_mock,
    _eu_ids_mock,
    _demand_mock,
) -> None:
    years = [2023, 2024]
    rows = [
        _fd_row(pk="calculated_max_power_mw", year_values=["—", "—"]),
        _res_row(pk="combined_on_fo", year_values=["100", "200"], res_id=1),
        _res_row(pk="combined_on_fo", year_values=["50", "60"], res_id=2),
        _eu_max_row(
            eu_id=11,
            year_values=["10", "11"],
            label="Центральный энергорайон Сахалинской области",
        ),
        _eu_max_row(
            eu_id=12,
            year_values=["20", "21"],
            label="Центральный энергорайон Камчатского края",
        ),
        _eu_max_row(
            eu_id=13,
            year_values=["1", "2"],
            label="Чаун-Билибинский энергорайон ЭС Чукотского АО",
        ),
        _eu_max_row(
            eu_id=14,
            year_values=["3", "4"],
            label="Анадырский энергорайон ЭС Чукотского АО",
        ),
        _eu_max_row(
            eu_id=15,
            year_values=["5", "6"],
            label="Центральный энергорайон Магаданской области",
        ),
        # Не из формулы Дальневосточного ФО — не должен войти.
        _eu_max_row(
            eu_id=99,
            year_values=["1000", "1000"],
            label="Таймырский … Норильск",
        ),
    ]

    enrich_fo_summary_calculated_max_power_from_res_combined_on_fo(
        rows, years, rounding_digits=0
    )
    enrich_far_east_fd_calculated_max_from_res_and_tites_eus(
        rows, years, rounding_digits=0
    )

    fd = rows[0]
    # РЭС 100+50 + ЭР 10+20+1+3+5 = 189; 200+60 + 11+21+2+4+6 = 304
    assert fd["year_values"] == ["189", "304"]
    assert fd["pd_formula_text_key"] == "fo_calc_max_power_mw_far_east"


@patch(
    "app.power_demand.services.demand_summary_services._sum_far_east_fd_formula_energy_units_max_power_from_demand",
    return_value=[None, 40.0],
)
@patch(
    "app.power_demand.services.demand_summary_services._sum_far_east_fd_formula_energy_units_max_power",
    return_value=[None, None],
)
@patch(
    "app.power_demand.services.demand_summary_services._far_east_federal_district_id",
    return_value=86,
)
@patch(
    "app.power_demand.services.demand_summary_services._is_tites_branch_regional_energy_system_row",
    return_value=False,
)
def test_far_east_fd_calc_max_falls_back_to_demand_eu_max(
    _tites_mock,
    _fd_id_mock,
    _eu_sum_mock,
    _demand_mock,
) -> None:
    years = [2023, 2024]
    rows = [
        _fd_row(pk="calculated_max_power_mw", year_values=["—", "—"]),
        _res_row(pk="combined_on_fo", year_values=["100", "200"]),
    ]

    enrich_fo_summary_calculated_max_power_from_res_combined_on_fo(
        rows, years, rounding_digits=0
    )
    enrich_far_east_fd_calculated_max_from_res_and_tites_eus(
        rows, years, rounding_digits=0
    )

    fd = rows[0]
    assert fd["year_values"][0] == "100"
    assert fd["year_values"][1] == "240"


@patch(
    "app.power_demand.services.demand_summary_services._sum_far_east_fd_formula_energy_units_max_power_from_demand",
    return_value=[None],
)
@patch(
    "app.power_demand.services.demand_summary_services._far_east_fd_formula_energy_unit_ids",
    return_value=frozenset({11, 12, 13, 14, 15}),
)
@patch(
    "app.power_demand.services.demand_summary_services._far_east_federal_district_id",
    return_value=86,
)
@patch(
    "app.power_demand.services.demand_summary_services._is_tites_branch_regional_energy_system_row",
    return_value=False,
)
def test_other_fd_not_affected_by_far_east_enrich(
    _tites_mock,
    _fd_id_mock,
    _eu_ids_mock,
    _demand_mock,
) -> None:
    years = [2024]
    rows = [
        _fd_row(
            pk="calculated_max_power_mw",
            year_values=["—"],
            fd_id=10,
            entity_label="Сибирский ФО",
        ),
        _res_row(pk="combined_on_fo", year_values=["100"], fd_id=10),
    ]

    enrich_fo_summary_calculated_max_power_from_res_combined_on_fo(
        rows, years, rounding_digits=0
    )
    enrich_far_east_fd_calculated_max_from_res_and_tites_eus(
        rows, years, rounding_digits=0
    )

    assert rows[0]["year_values"] == ["100"]
    assert rows[0].get("pd_formula_text_key") is None

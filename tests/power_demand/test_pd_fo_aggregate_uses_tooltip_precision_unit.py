# -*- coding: utf-8 -*-
"""Агрегаты ФО: сумма по полным title РЭС, не по округлённым year_values."""

from __future__ import annotations

from app.common.services.help_services import format_decimal_trim_for_display
from app.power_demand.services import demand_summary_services as dss


def test_format_integer_rounding_does_not_show_signed_zero() -> None:
    assert format_decimal_trim_for_display(-0.1, digits=-1) == "0"
    assert format_decimal_trim_for_display(-0.4, digits=-1) == "0"
    assert format_decimal_trim_for_display(0.1, digits=-1) == "0"


def test_summary_row_year_float_prefers_tooltip_over_rounded_display() -> None:
    row = {
        "year_values": ["8 835", "10 030"],
        "year_numeric_tooltips": ["8 835,1", "10 030"],
    }
    assert dss._summary_row_year_float(row, 0) == 8835.1
    assert dss._summary_row_year_float(row, 1) == 10030.0


def test_fo_combined_on_fo_aggregate_uses_tooltip_precision() -> None:
    """Как Сибирский ФО при округлении «до целого»: display округлён, title — полный."""
    years = [2022, 2024]
    rows = [
        {
            "parameter_key": "combined_on_fo",
            "demand_model_name": "RegionalEnergySystemDemandParameter",
            "id_federal_district": 90,
            "id_regional_energy_system": 1,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 1,
            "year_values": ["8 835", "10 047"],
            "year_numeric_tooltips": ["8 835,1", "10 046,5"],
        },
        {
            "parameter_key": "combined_on_fo",
            "demand_model_name": "RegionalEnergySystemDemandParameter",
            "id_federal_district": 90,
            "id_regional_energy_system": 2,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 2,
            "year_values": ["20 767", "21 794"],
            "year_numeric_tooltips": ["20 766,5", "21 792,6"],
        },
    ]
    sums = dss._aggregate_res_combined_on_fo_mw_sum_by_federal_district(rows, years)
    assert sums[90][0] == 29601.6
    assert sums[90][1] == 31839.1


def test_fo_aggregate_includes_tites_branch_res() -> None:
    """Норильск (ТИТЭС) под Сибирским ФО входит в расчётный максимум ФО."""
    years = [2022, 2023]
    rows = [
        {
            "parameter_key": "combined_on_fo",
            "demand_model_name": "RegionalEnergySystemDemandParameter",
            "id_federal_district": 90,
            "id_regional_energy_system": 586,
            "id_union_energy_system": 10,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 586,
            "year_values": ["29 601,6", "32 385,9"],
            "year_numeric_tooltips": ["29 601,6", "32 385,9"],
        },
        {
            "parameter_key": "combined_on_fo",
            "demand_model_name": "RegionalEnergySystemDemandParameter",
            "id_federal_district": 90,
            "id_regional_energy_system": 635,
            "id_union_energy_system": 120,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 635,
            "year_values": ["1 091", "1 117"],
            "year_numeric_tooltips": ["1 091", "1 117"],
        },
    ]
    sums = dss._aggregate_res_combined_on_fo_mw_sum_by_federal_district(rows, years)
    assert sums[90] == [30692.6, 33502.9]


def test_verify_diff_uses_tooltip_precision() -> None:
    years = [2022]
    rows = [
        {
            "show_entity_cell": True,
            "entity_rowspan": 2,
            "entity_label": "Сибирский ФО",
            "entity_kind": "group",
            "demand_model_name": "FederalDistrictDemandParameter",
            "parameter_key": "max_power",
            "year_values": ["29 602"],
            "year_numeric_tooltips": ["29 601,6"],
        },
        {
            "show_entity_cell": False,
            "entity_rowspan": 2,
            "demand_model_name": "FederalDistrictDemandParameter",
            "parameter_key": "calculated_max_power_mw",
            "year_values": ["29 602"],
            "year_numeric_tooltips": ["29 601,6"],
        },
    ]
    dss._inject_oes_summary_verification_rows(rows, years)
    verify = next(
        r for r in rows if r.get("parameter_key") == "verify_for_calculated_max_power_mw"
    )
    assert verify["year_values"] == ["0"]

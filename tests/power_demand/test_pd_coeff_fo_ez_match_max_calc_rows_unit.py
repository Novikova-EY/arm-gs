# -*- coding: utf-8 -*-
"""Coeff ФО/ЭЗ: тот же набор расчётных строк и подписи, что на max-сводках."""

from __future__ import annotations

from unittest.mock import patch

from app.common.perimeter_variant.constants import CODE_WITHOUT_NT_WITHOUT_GAES
from app.power_demand.models.territories.federal_district_demand_parameter_model import (
    FederalDistrictDemandParameter,
)
from app.power_demand.services import demand_summary_services as dss
from app.power_demand.services.power_demand_summary_formula_registry import (
    PAGE_COEFF_FO,
    PAGE_FO,
    get_formula_def,
)


def test_fo_coeff_context_uses_max_extended_parameters() -> None:
    captured: dict = {}

    def _capture(*_a, **kwargs):
        captured.update(kwargs)
        return {
            "summary_rows": [],
            "years": [2024],
            "rounding_digits": 0,
        }

    with (
        patch.object(dss, "build_federal_district_summary_context", side_effect=_capture),
        patch.object(dss, "_inject_fo_coeff_cz_total_rows"),
    ):
        dss.build_federal_district_summary_context_coeff(
            0,
            start_year=2024,
            end_year=2024,
            filter_year_list=[2024],
        )

    assert captured.get("fo_max_extended_parameters") is True
    assert captured.get("fo_aggregate_by_res") is True


def test_ez_coeff_context_uses_max_extended_parameters() -> None:
    captured: dict = {}

    def _capture(*_a, **kwargs):
        captured.update(kwargs)
        return {
            "summary_rows": [],
            "years": [2024],
            "rounding_digits": 0,
        }

    with patch.object(dss, "build_energy_zones_summary_context", side_effect=_capture):
        dss.build_energy_zones_summary_context_coeff(
            0,
            start_year=2024,
            end_year=2024,
            filter_year_list=[2024],
        )

    assert captured.get("ez_max_extended_parameters") is True


def test_fo_ez_coeff_builders_do_not_force_gaes_entity_labels() -> None:
    """Coeff ФО/ЭЗ не должны затирать compact-подписи «+ НТ» полным «без ГАЭС»."""
    with (
        patch.object(
            dss,
            "build_federal_district_summary_context",
            return_value={
                "summary_rows": [],
                "years": [2024],
                "rounding_digits": 0,
            },
        ),
        patch.object(dss, "_inject_fo_coeff_cz_total_rows"),
        patch.object(
            dss,
            "build_energy_zones_summary_context",
            return_value={"summary_rows": [], "years": [2024], "rounding_digits": 0},
        ),
        patch.object(
            dss, "tag_power_demand_coeff_summary_rows_without_gaes_entity_labels"
        ) as tag_gaes,
    ):
        dss.build_federal_district_summary_context_coeff(
            0, start_year=2024, end_year=2024, filter_year_list=[2024]
        )
        dss.build_energy_zones_summary_context_coeff(
            0, start_year=2024, end_year=2024, filter_year_list=[2024]
        )

    tag_gaes.assert_not_called()


def test_fo_coeff_entity_label_compact_matches_max_summary_nt_off() -> None:
    row = {
        "show_entity_cell": True,
        "entity_label": "Южный ФО без НТ",
        "demand_model_name": FederalDistrictDemandParameter.__name__,
        "parameter_key": "max_power",
        "perimeter_variant_code": CODE_WITHOUT_NT_WITHOUT_GAES,
        "entity_kind": "perimeter_variant",
        "entity_depth": 0,
    }
    dss.tag_power_demand_summary_rows_for_nt_toggle([row])

    assert row["pd_pd_entity_label_compact_nt"] == "Южный ФО"
    assert row["pd_pd_entity_label_nt_detail"] == "Южный ФО без НТ"
    assert "ГАЭС" not in row["pd_pd_entity_label_compact_nt"]
    assert "ГАЭС" not in row["pd_pd_entity_label_nt_detail"]


def test_fo_verify_combined_on_cz_label_matches_max_summary() -> None:
    rows = [
        {
            "show_entity_cell": True,
            "entity_rowspan": 2,
            "demand_model_name": FederalDistrictDemandParameter.__name__,
            "parameter_key": "calculated_combined_on_cz_mw",
            "parameter_label": (
                "Расчетное совмещенное потребление мощности на час максимума ЦЗ России, МВт"
            ),
        },
        {
            "show_entity_cell": False,
            "entity_rowspan": 2,
            "demand_model_name": FederalDistrictDemandParameter.__name__,
            "parameter_key": "combined_on_cz",
            "parameter_label": (
                "Совмещенное потребление мощности на час максимума ЦЗ России, МВт"
            ),
        },
    ]
    dss._inject_oes_summary_verification_rows(rows, [2024])
    verify = next(
        r
        for r in rows
        if r.get("parameter_key") == "verify_for_calculated_combined_on_cz_mw"
    )
    assert verify["parameter_label"] == (
        "Проверка расчетного совмещенного потребления мощности "
        "на час максимума ЦЗ России, МВт"
    )


def test_fo_combined_on_cz_formulas_shared_by_coeff_and_max_pages() -> None:
    calc = get_formula_def("fo_calc_combined_on_cz_mw")
    verify = get_formula_def("fo_verify_combined_on_cz_mw_without_nt")
    assert calc is not None and verify is not None
    assert PAGE_FO in calc.pages and PAGE_COEFF_FO in calc.pages
    assert PAGE_FO in verify.pages and PAGE_COEFF_FO in verify.pages
    assert calc.cell_name == (
        "Расчетное совмещенное потребление мощности на час максимума ЦЗ России, МВт"
    )
    assert verify.cell_name == (
        "Проверка расчетного совмещенного потребления мощности "
        "на час максимума ЦЗ России, МВт"
    )
    assert get_formula_def("fo_calc_combined_on_cz_mw_coeff") is None
    assert get_formula_def("fo_verify_combined_on_cz_mw_coeff_without_nt") is None

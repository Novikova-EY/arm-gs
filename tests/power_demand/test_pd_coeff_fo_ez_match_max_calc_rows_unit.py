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


def test_strip_new_territories_block_for_ez_summary_removes_header_and_subjects() -> None:
    rows = [
        {
            "show_entity_cell": True,
            "entity_depth": 1,
            "entity_rowspan": 1,
            "entity_kind": "aggregation_level",
            "entity_label": "Новые территории",
            "pd_pd_nt_subtree_root": True,
            "pd_pd_aggregation_level_row": True,
            "parameter_key": "",
        },
        {
            "show_entity_cell": True,
            "entity_depth": 2,
            "entity_rowspan": 2,
            "entity_kind": "child",
            "entity_label": "ДНР",
            "demand_model_name": "RegionalDistrictDemandParameter",
            "parameter_key": "max_power",
            "pd_pd_nt_extra_row": True,
        },
        {
            "show_entity_cell": False,
            "entity_depth": 2,
            "entity_rowspan": 2,
            "entity_kind": "child",
            "parameter_key": "peak_datetime",
            "pd_pd_nt_extra_row": True,
        },
        {
            "show_entity_cell": True,
            "entity_depth": 0,
            "entity_rowspan": 1,
            "entity_kind": "centralized_zone",
            "entity_label": "ЦЗ России с НТ",
            "demand_model_name": "CentralizedZoneDemandParameter",
            "parameter_key": "max_power",
            "pd_pd_nt_extra_row": True,
            "pd_pd_nt_subtree_root": True,
        },
        {
            "show_entity_cell": True,
            "entity_depth": 0,
            "entity_rowspan": 1,
            "entity_kind": "group",
            "entity_label": "Следующая зона",
            "demand_model_name": "EnergyZoneDemandParameter",
            "parameter_key": "max_power",
        },
    ]
    out = dss._strip_new_territories_block_for_ez_summary(rows)
    labels = [r.get("entity_label") for r in out if r.get("show_entity_cell")]
    assert labels == ["ЦЗ России с НТ", "Следующая зона"]
    assert all(r.get("entity_label") != "Новые территории" for r in out)
    assert all(r.get("entity_label") != "ДНР" for r in out)


def test_strip_new_territories_block_for_coeff_ez_removes_header_and_subjects() -> None:
    """Обратная совместимость: прежнее имя функции — тот же strip для ЭЗ."""
    rows = [
        {
            "show_entity_cell": True,
            "entity_depth": 1,
            "entity_rowspan": 1,
            "entity_kind": "aggregation_level",
            "entity_label": "Новые территории",
            "pd_pd_nt_subtree_root": True,
            "pd_pd_aggregation_level_row": True,
            "parameter_key": "",
        },
        {
            "show_entity_cell": True,
            "entity_depth": 0,
            "entity_rowspan": 1,
            "entity_kind": "group",
            "entity_label": "Следующая зона",
            "demand_model_name": "EnergyZoneDemandParameter",
            "parameter_key": "max_power",
        },
    ]
    out = dss._strip_new_territories_subject_rows_for_coeff_ez(rows)
    labels = [r.get("entity_label") for r in out if r.get("show_entity_cell")]
    assert labels == ["Следующая зона"]
    assert all(r.get("entity_label") != "Новые территории" for r in out)


def test_fo_ez_level_skip_second_coeff_k_row() -> None:
    """На уровне ФО/ЭЗ/ОЭС нет строки k у расчётного совмещённого (вторая k под совмещённым)."""
    fo_keep = {
        "demand_model_name": FederalDistrictDemandParameter.__name__,
        "parameter_key": "combined_on_cz",
    }
    fo_skip = {
        "demand_model_name": FederalDistrictDemandParameter.__name__,
        "parameter_key": "calculated_combined_on_cz_mw",
    }
    ez_keep = {
        "demand_model_name": "EnergyZoneDemandParameter",
        "parameter_key": "combined_on_ees",
    }
    ez_skip = {
        "demand_model_name": "EnergyZoneDemandParameter",
        "parameter_key": "calculated_combined_on_ees_mw",
    }
    res_keep = {
        "demand_model_name": "RegionalEnergySystemDemandParameter",
        "parameter_key": "combined_on_ees",
    }
    assert dss.summary_row_allows_coeff_k_row(fo_keep) is True
    assert dss.summary_row_allows_coeff_k_row(fo_skip) is False
    assert dss.summary_row_allows_coeff_k_row(
        {
            "demand_model_name": FederalDistrictDemandParameter.__name__,
            "parameter_key": "calculated_max_power_mw",
        }
    )
    assert dss.summary_row_allows_coeff_k_row(ez_keep) is True
    assert dss.summary_row_allows_coeff_k_row(ez_skip) is False
    assert dss.summary_row_allows_coeff_k_row(res_keep) is True
    assert dss.summary_row_allows_coeff_k_row(
        {
            "demand_model_name": "UnionEnergySystemDemandParameter",
            "parameter_key": "combined_on_ees",
        }
    )
    assert (
        dss.summary_row_allows_coeff_k_row(
            {
                "demand_model_name": "UnionEnergySystemDemandParameter",
                "parameter_key": "calculated_combined_on_ees_mw",
            }
        )
        is False
    )
    assert dss.summary_row_allows_coeff_k_row(
        {
            "demand_model_name": "UnionEnergySystemDemandParameter",
            "parameter_key": "calculated_max_power_mw",
        }
    )

    tagged = [dict(fo_keep), dict(fo_skip), dict(ez_keep), dict(ez_skip)]
    dss.tag_summary_rows_coeff_k_row_visibility(tagged)
    assert tagged[0]["pd_pd_skip_coeff_k_row"] is False
    assert tagged[1]["pd_pd_skip_coeff_k_row"] is True
    assert tagged[2]["pd_pd_skip_coeff_k_row"] is False
    assert tagged[3]["pd_pd_skip_coeff_k_row"] is True


def test_fo_coeff_cz_total_rows_are_verify_without_k() -> None:
    rows = [
        {
            "show_entity_cell": True,
            "entity_kind": "centralized_zone",
            "entity_label": "ЦЗ России с НТ",
            "entity_rowspan": 1,
            "entity_depth": 0,
            "parameter_key": "max_power",
            "demand_model_name": "CentralizedZoneDemandParameter",
            "year_values": ["100"],
            "year_numeric_tooltips": [""],
            "parent_fk_column": None,
            "parent_id": None,
            "entity_note_text": "",
            "entity_note_row_id": None,
            "id_union_energy_system": None,
        }
    ]
    dss._inject_fo_coeff_cz_total_rows(rows, [2024], 0)
    totals = [r for r in rows if r.get("pd_fo_coeff_cz_total")]
    assert len(totals) == 3
    assert all(r.get("pd_pd_verify_for_row") is True for r in totals)
    assert {r["parameter_key"] for r in totals} == {
        "cz_total_sum_fo_max_power",
        "cz_total_sum_res_combined_cz",
        "cz_total_imbalance_mw",
    }


def test_fo_ez_coeff_builders_do_not_force_gaes_entity_labels() -> None:
    """Coeff ОЭС/ФО/ЭЗ не должны затирать compact-подписи «+ НТ» полным «без ГАЭС»."""
    with (
        patch.object(
            dss,
            "build_oes_summary_context",
            return_value={
                "summary_rows": [],
                "years": [2024],
                "rounding_digits": 0,
            },
        ),
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
        dss.build_oes_summary_context_coeff(
            0, start_year=2024, end_year=2024, filter_year_list=[2024]
        )
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

# -*- coding: utf-8 -*-
"""Выбор формул с/без НТ по коду периметра строки сводки."""

from __future__ import annotations

from app.power_demand.services.formula_text.pd_summary_formula_row_resolver import (
    nt_group_for_pd_formula_row,
    resolve_pd_summary_parameter_formula_base_key,
    resolve_pd_summary_row_formula_key,
    strip_pd_formula_nt_suffix,
)
from app.power_demand.services.power_demand_summary_formula_registry import get_formula_def


def test_strip_pd_formula_nt_suffix() -> None:
    assert strip_pd_formula_nt_suffix("oes_ees_russia_calc_max_with_nt") == (
        "oes_ees_russia_calc_max"
    )
    assert strip_pd_formula_nt_suffix("oes_ees_russia_calc_max_without_nt") == (
        "oes_ees_russia_calc_max"
    )
    assert strip_pd_formula_nt_suffix("fo_calc_max_mw") == "fo_calc_max_mw"


def test_nt_group_maps_composite_perimeter_codes() -> None:
    assert nt_group_for_pd_formula_row({"perimeter_variant_code": "with_nt"}) == "with_nt"
    assert (
        nt_group_for_pd_formula_row({"perimeter_variant_code": "with_nt_without_gaes"})
        == "with_nt"
    )
    assert (
        nt_group_for_pd_formula_row({"perimeter_variant_code": "with_nt_with_gaes"})
        == "with_nt"
    )
    assert (
        nt_group_for_pd_formula_row({"perimeter_variant_code": "o1_with_nt"}) == "with_nt"
    )
    assert (
        nt_group_for_pd_formula_row({"perimeter_variant_code": "without_nt_without_gaes"})
        == "without_nt"
    )
    assert (
        nt_group_for_pd_formula_row({"perimeter_variant_code": "o1_without_nt"})
        == "without_nt"
    )


def test_nt_group_falls_back_to_entity_label() -> None:
    assert (
        nt_group_for_pd_formula_row(
            {"entity_label": "ЕЭС России с НТ", "perimeter_variant_code": None}
        )
        == "with_nt"
    )
    assert (
        nt_group_for_pd_formula_row(
            {"entity_label": "ЕЭС России без НТ", "perimeter_variant_code": None}
        )
        == "without_nt"
    )


def test_ees_russia_with_nt_composite_code_gets_with_nt_formula() -> None:
    row = {
        "demand_model_name": "EnergySystemTypeDemandParameter",
        "parameter_key": "calculated_max_ees_russia_mw",
        "perimeter_variant_code": "with_nt_without_gaes",
        "entity_label": "ЕЭС России с НТ",
    }
    base = resolve_pd_summary_parameter_formula_base_key(row)
    key = resolve_pd_summary_row_formula_key(row, base_key=base)
    assert base == "oes_ees_russia_calc_max"
    assert key == "oes_ees_russia_calc_max_with_nt"
    text = get_formula_def(key).default_text
    assert "с НТ" in text
    assert "без НТ" not in text


def test_ees_russia_without_nt_composite_code_gets_without_nt_formula() -> None:
    row = {
        "demand_model_name": "EnergySystemTypeDemandParameter",
        "parameter_key": "calculated_max_ees_russia_mw",
        "perimeter_variant_code": "without_nt_without_gaes",
        "entity_label": "ЕЭС России без НТ",
    }
    key = resolve_pd_summary_row_formula_key(
        row,
        base_key=resolve_pd_summary_parameter_formula_base_key(row),
    )
    assert key == "oes_ees_russia_calc_max_without_nt"
    text = get_formula_def(key).default_text
    assert "без НТ" in text


def test_explicit_without_nt_key_rebinds_to_with_nt_for_with_nt_row() -> None:
    row = {
        "demand_model_name": "EnergySystemTypeDemandParameter",
        "parameter_key": "calculated_max_ees_russia_mw",
        "perimeter_variant_code": "with_nt_with_gaes",
        "entity_label": "ЕЭС России с НТ",
        "pd_formula_text_key": "oes_ees_russia_calc_max_without_nt",
    }
    base = resolve_pd_summary_parameter_formula_base_key(row)
    key = resolve_pd_summary_row_formula_key(row, base_key=base)
    assert base == "oes_ees_russia_calc_max"
    assert key == "oes_ees_russia_calc_max_with_nt"


def test_ees_russia_with_nt_verify_and_calc_keys_align() -> None:
    calc_row = {
        "demand_model_name": "EnergySystemTypeDemandParameter",
        "parameter_key": "calculated_max_ees_russia_mw",
        "perimeter_variant_code": "with_nt_without_gaes",
        "entity_label": "ЕЭС России с НТ",
    }
    verify_row = {
        "demand_model_name": "EnergySystemTypeDemandParameter",
        "parameter_key": "verify_for_calculated_max_ees_russia_mw",
        "perimeter_variant_code": "with_nt_without_gaes",
        "entity_label": "ЕЭС России с НТ",
    }
    calc_key = resolve_pd_summary_row_formula_key(
        calc_row,
        base_key=resolve_pd_summary_parameter_formula_base_key(calc_row),
    )
    verify_key = resolve_pd_summary_row_formula_key(
        verify_row,
        base_key=resolve_pd_summary_parameter_formula_base_key(verify_row),
    )
    assert calc_key == "oes_ees_russia_calc_max_with_nt"
    assert verify_key == "ees_russia_verify_calc_max_with_nt"
    assert "с НТ" in get_formula_def(calc_key).default_text
    assert "без НТ" not in get_formula_def(calc_key).default_text
    assert "с НТ" in get_formula_def(verify_key).default_text


def test_ues_and_fo_verify_follow_perimeter_nt_group() -> None:
    ues_with = {
        "demand_model_name": "UnionEnergySystemDemandParameter",
        "parameter_key": "calculated_max_power_mw",
        "perimeter_variant_code": "with_nt_with_gaes",
        "entity_label": "ОЭС Юга с НТ",
    }
    fo_with = {
        "demand_model_name": "FederalDistrictDemandParameter",
        "parameter_key": "verify_for_calculated_max_power_mw",
        "perimeter_variant_code": "with_nt",
        "entity_label": "Южный ФО с НТ",
    }
    assert (
        resolve_pd_summary_row_formula_key(
            ues_with,
            base_key=resolve_pd_summary_parameter_formula_base_key(ues_with),
        )
        == "oes_ues_calc_max_oes_mw_with_nt"
    )
    assert (
        resolve_pd_summary_row_formula_key(
            fo_with,
            base_key=resolve_pd_summary_parameter_formula_base_key(fo_with),
        )
        == "fo_verify_calc_max_mw_with_nt"
    )

# -*- coding: utf-8 -*-
"""ЦЗ России: расчетное max_power = ОЭС + ТИТЭС + О-1."""

from __future__ import annotations

from unittest.mock import patch

from app.power_demand.services import demand_summary_services as dss


def _ues_max_row(
    *,
    label: str,
    ues_id: int,
    year_values: list[str],
    pvc: str | None = None,
) -> dict:
    return {
        "show_entity_cell": True,
        "entity_label": label,
        "entity_rowspan": 1,
        "entity_kind": "group",
        "demand_model_name": "UnionEnergySystemDemandParameter",
        "parameter_key": "max_power",
        "parent_fk_column": "id_union_energy_system",
        "parent_id": ues_id,
        "id_union_energy_system": ues_id,
        "perimeter_variant_code": pvc,
        "year_values": year_values,
        "year_numeric_tooltips": [""] * len(year_values),
        "hist_value": "",
    }


def _res_max_row(
    *,
    label: str,
    res_id: int,
    ues_id: int,
    year_values: list[str],
    pvc: str | None = None,
) -> dict:
    return {
        "show_entity_cell": True,
        "entity_label": label,
        "entity_rowspan": 1,
        "entity_kind": "child",
        "demand_model_name": "RegionalEnergySystemDemandParameter",
        "parameter_key": "max_power",
        "parent_fk_column": "id_regional_energy_system",
        "parent_id": res_id,
        "id_regional_energy_system": res_id,
        "id_union_energy_system": ues_id,
        "perimeter_variant_code": pvc,
        "year_values": year_values,
        "year_numeric_tooltips": [""] * len(year_values),
        "hist_value": "",
    }


def _cz_block(*, pvc: str, year_values: list[str] | None = None) -> list[dict]:
    n = 2
    yv = year_values or ["—"] * n
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


def test_enrich_cz_russia_calculated_max_power_sums_oes_tites_and_o1() -> None:
    years = [2024, 2025]
    rows = [
        *_cz_block(pvc="without_nt"),
        _ues_max_row(
            label="ОЭС Центра",
            ues_id=1,
            year_values=["100", "200"],
        ),
        _ues_max_row(
            label="ОЭС Юга без НТ",
            ues_id=2,
            year_values=["10", "20"],
            pvc="without_nt_without_gaes",
        ),
        _res_max_row(
            label="ЭС Камчатского края",
            res_id=10,
            ues_id=99,
            year_values=["5", "6"],
        ),
        _res_max_row(
            label="ЭС Камчатского края О-1",
            res_id=10,
            ues_id=99,
            year_values=["1", "2"],
            pvc="o1",
        ),
    ]
    with (
        patch.object(
            dss,
            "_union_energy_system_ids_for_energy_system_type",
            return_value=frozenset({1, 2}),
        ),
        patch.object(dss, "_tites_union_energy_system_ids", return_value=frozenset({99})),
        patch.object(
            dss,
            "_make_ues_perimeter_filter_for_ees_russia_aggregate",
            return_value=lambda _r: True,
        ),
        patch.object(
            dss,
            "_is_o1_form_summary_entity_row",
            side_effect=lambda r: str(r.get("perimeter_variant_code") or "") == "o1",
        ),
    ):
        dss.enrich_cz_russia_calculated_max_power_mw(rows, years, rounding_digits=1)

    calc = next(r for r in rows if r.get("parameter_key") == "calculated_max_power_mw")
    # 100+10+5+1 , 200+20+6+2
    assert calc["year_values"][0].replace("\xa0", " ").replace(" ", "") in (
        "116",
        "116.0",
    )
    assert float(str(calc["year_values"][0]).replace("\xa0", "").replace(" ", "").replace(",", ".")) == 116.0
    assert float(str(calc["year_values"][1]).replace("\xa0", "").replace(" ", "").replace(",", ".")) == 228.0
    assert calc.get("pd_pd_formula_derived_row") is True


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
    assert float(str(verify["year_values"][0]).replace("\xa0", "").replace(" ", "").replace(",", ".")) == 10.0


def test_parameters_cz_oes_summary_includes_calculated_max() -> None:
    keys = [pk for pk, _ in dss.PARAMETERS_CZ_OES_SUMMARY]
    assert keys == ["max_power", "calculated_max_power_mw", "peak_datetime"]

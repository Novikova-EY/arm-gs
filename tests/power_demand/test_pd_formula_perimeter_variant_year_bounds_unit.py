# -*- coding: utf-8 -*-
"""Формулы сводки спроса: только в интервале «Год с»…«Год по» варианта периметра."""

from __future__ import annotations

from app.power_demand.services import demand_summary_services as service


def test_formula_year_applies_ignores_skip_flag(monkeypatch):
    monkeypatch.setattr(
        service,
        "perimeter_variant_year_bounds_for_code",
        lambda _code: (2023, None),
    )
    row = {
        "perimeter_variant_code": "with_nt",
        "pd_pd_skip_perimeter_variant_year_bounds": True,
    }
    assert service._year_applies_to_pd_summary_row_perimeter_variant(row, 2022) is True
    assert service._formula_year_applies_to_row_perimeter_variant(row, 2022) is False
    assert service._formula_year_applies_to_row_perimeter_variant(row, 2023) is True


def test_formula_write_respects_perimeter_variant_year_bounds_even_when_input_unrestricted(
    monkeypatch,
):
    """Формулы на oes/fo/ez пишутся только в «Год с»…«Год по»; вне периода — данные из БД."""
    years = [2022, 2023, 2024, 2025]

    def _fake_bounds(code: str):
        if code == "with_nt_with_gaes":
            return 2023, 2024
        return None, None

    monkeypatch.setattr(
        service,
        "perimeter_variant_year_bounds_for_code",
        _fake_bounds,
    )
    row = {
        "demand_model_name": "UnionEnergySystemDemandParameter",
        "parameter_key": "calculated_max_power_mw",
        "id_union_energy_system": 10,
        "parent_fk_column": "id_union_energy_system",
        "parent_id": 10,
        "perimeter_variant_code": "with_nt_with_gaes",
        "pd_pd_skip_perimeter_variant_year_bounds": True,
        "year_values": ["11.0", "22.0", "33.0", "44.0"],
        "year_numeric_tooltips": ["11.0", "22.0", "33.0", "44.0"],
    }
    service._apply_ues_calculated_mw_from_res_sums(
        [row],
        years,
        rounding_digits=1,
        ues_parameter_key="calculated_max_power_mw",
        sums_by_union={10: [100.0, 200.0, 300.0, 400.0]},
        row_include_predicate=lambda _r: True,
    )
    assert row["year_values"] == ["11.0", "200", "300", "44.0"]
    assert row["year_numeric_tooltips"][0] == "11.0"
    assert row["year_numeric_tooltips"][3] == "44.0"


def test_copy_pd_summary_row_display_respects_formula_year_bounds(monkeypatch):
    monkeypatch.setattr(
        service,
        "perimeter_variant_year_bounds_for_code",
        lambda _code: (2024, None),
    )
    years = [2022, 2024]
    target = {
        "perimeter_variant_code": "with_nt",
        "parameter_key": "calculated_max_power_mw",
        "year_values": ["keep-2022", "old-2024"],
        "year_numeric_tooltips": ["keep-tt", "old-tt"],
    }
    source = {
        "year_values": ["src-2022", "src-2024"],
        "year_numeric_tooltips": ["s-tt-2022", "s-tt-2024"],
    }
    service._copy_pd_summary_row_display_from_reference(target, source, years)
    assert target["year_values"] == ["keep-2022", "src-2024"]
    assert target["year_numeric_tooltips"] == ["keep-tt", "s-tt-2024"]


def test_first_sa_formula_year_ignores_perimeter_year_from(monkeypatch):
    """У первой СЗ «Год с» не глушит формулы (только вычитание Калининграда)."""
    monkeypatch.setattr(
        service,
        "perimeter_variant_year_bounds_for_code",
        lambda _code: (2025, None),
    )
    row = {
        "demand_model_name": "SynchronousAreaDemandParameter",
        "entity_label": "Первая синхронная зона без НТ",
        "perimeter_variant_code": "without_nt_without_gaes_kaliningrad",
    }
    assert service._formula_year_applies_to_row_perimeter_variant(row, 2017) is True
    assert service._formula_year_applies_to_row_perimeter_variant(row, 2025) is True
    assert service._pd_should_apply_formula_for_year(row, 2017) is True

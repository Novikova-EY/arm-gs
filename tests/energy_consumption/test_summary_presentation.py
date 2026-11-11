from decimal import Decimal
from types import SimpleNamespace

import pytest
from flask import render_template_string

from app.energy_consumption.pages import _summary_page_transforms as transforms
from app.energy_consumption.services import energy_consumption_summary_services as consumption
from app.energy_consumption.services.summary_formula_presentation import attach_summary_formula_tooltips
from app.energy_consumption.services.ec_summary_client_render_services import prepare_summary_rows_for_client


@pytest.mark.parametrize("parameter,key", [
    ("energy_consumption_yoy_growth_pct", "yoy_growth"),
    ("energy_consumption_sipr_yoy_growth_pct", "sipr_yoy_growth"),
    ("energy_consumption_sipr_abs_growth_mln", "sipr_abs_growth"),
])
def test_growth_formula_is_available_in_client_data_and_uses_overrides(parameter, key):
    row = {"parameter_key": parameter, "pd_ec_summary_row_formula_tooltip": "Consumption formula"}
    context = {"summary_rows": [row], "ec_formula_texts": {key: "Current / Previous * 100 - 100"}}
    attach_summary_formula_tooltips(context)
    assert prepare_summary_rows_for_client([row])[0]["pd_parameter_formula_tooltip"] == "Current / Previous * 100 - 100"


@pytest.mark.parametrize("model", ["FederalDistrictEnergyConsumptionParameter", "EnergyZoneEnergyConsumptionParameter"])
def test_automatic_aggregate_has_actual_formula(model):
    row = {"demand_model_name": model, "entity_kind": "group", "parameter_key": "energy_consumption_mln_kvt_ch"}
    attach_summary_formula_tooltips({"summary_rows": [row]})
    assert "=" in row["pd_parameter_formula_tooltip"]
    assert "РЭС" in row["pd_parameter_formula_tooltip"]


@pytest.mark.parametrize("calculated", [False, True])
def test_each_row_has_an_independent_editable_note_even_when_calculated(app, calculated):
    row = dict(entity_label="Энергосистема", parameter_label="Потребление электрической энергии",
               pd_ec_formula_derived_row=calculated, pd_ec_note_key="a" * 64,
               entity_note_text="Text <safe>")
    with app.test_request_context():
        html = render_template_string("{% include 'energy_consumption/_summary_note_cell.html' %}",
                                      row=row, can_edit_summary_cells=True, show_summary_note_col=True)
    assert 'data-note-key="' + "a" * 64 + '"' in html
    assert "readonly" not in html
    assert "rowspan" not in html
    assert "Text &lt;safe&gt;" in html


def test_no_rounding_preserves_precision_of_source_and_computed_values():
    parameters = (("energy_consumption_mln_kvt_ch", "Consumption"),
                  ("energy_consumption_yoy_growth_pct", "Growth"))
    rows = [SimpleNamespace(year_number=2024, energy_consumption_mln_kvt_ch=Decimal("100")),
            SimpleNamespace(year_number=2025, energy_consumption_mln_kvt_ch=Decimal("101.23456789"))]
    values, tooltips = consumption._build_parameter_maps(rows, parameters, 0)
    assert values["energy_consumption_mln_kvt_ch"][2025] == "101,23456789"
    assert values["energy_consumption_yoy_growth_pct"][2025] == "1,23456789"
    assert tooltips["energy_consumption_yoy_growth_pct"][2025] == "1,23456789"


def test_zero_rounding_reaches_formula_pipeline_without_becoming_one(monkeypatch):
    calls = []
    for name, function in list(vars(transforms).items()):
        if callable(function) and getattr(function, "__module__", "").endswith("energy_consumption_summary_services"):
            def record(*args, **kwargs):
                if "rounding_digits" in kwargs:
                    calls.append(kwargs["rounding_digits"])
                return args[0] if args else None
            monkeypatch.setattr(transforms, name, record)
    context = dict(summary_rows=[], years=[2025], rounding_digits=0, active_summary="ez")
    transforms.convert_context_to_summary_table_page(context)
    assert calls
    assert set(calls) == {0}


def test_verification_rows_keep_small_differences_without_rounding(monkeypatch):
    monkeypatch.setattr(consumption, "perimeter_variant_year_bounds_for_code", lambda code: (None, None))
    rows = consumption._build_ec_summary_verification_rows(
        entity_label="Проверка", entity_kind="verification", entity_depth=0,
        years=[2025], rounding_digits=0,
        base_ec={2025: Decimal("0.000000123456789")}, sum_ec={2025: Decimal(0)},
        base_sipr={}, sum_sipr={}, formula_tooltip="Base - Sum",
    )
    value_row = next(row for row in rows if row["parameter_key"] == "energy_consumption_mln_kvt_ch")
    assert value_row["year_values"] == ["0,000000123456789"]
    assert value_row["year_numeric_tooltips"] == ["0,000000123456789"]

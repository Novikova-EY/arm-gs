from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import re
from types import SimpleNamespace

import pytest
from flask import render_template_string
from openpyxl import load_workbook

from app.common.services.excel_numeric_cell import excel_number_format
from app.energy_consumption.routes.energy_consumption_summary_routes import _parse_rounding_digits
from app.energy_consumption.services import energy_consumption_summary_services as consumption
from app.energy_consumption.services.energy_consumption_summary_export_services import build_demand_summary_excel_stream


TEMPLATES = Path(__file__).resolve().parents[2] / "app/templates/energy_consumption"
GROWTH_KEYS = ("energy_consumption_yoy_growth_pct", "energy_consumption_sipr_yoy_growth_pct")


@pytest.mark.parametrize("general_digits", [-1, 0, 1, 2, 3])
@pytest.mark.parametrize("growth_digits", [0, -1, 1, 2, 3])
def test_growth_uses_displayed_consumption_precision_and_growth_precision_is_independent(general_digits, growth_digits):
    parameters = tuple((key, key) for key in (
        "energy_consumption_mln_kvt_ch", "energy_consumption_sipr_mln_kvt_ch", *GROWTH_KEYS,
    ))
    records = [SimpleNamespace(year_number=year, energy_consumption_mln_kvt_ch=value,
                               energy_consumption_sipr_mln_kvt_ch=value)
               for year, value in [(2024, Decimal("100")), (2025, Decimal("101.23456789"))]]
    values, tooltips = consumption._build_parameter_maps(records, parameters, general_digits)
    rows = [dict(parameter_key=key, year_values=[values[key][2025]],
                 year_numeric_tooltips=[tooltips[key][2025]]) for key, _ in parameters]
    source_values = [list(row["year_values"]) for row in rows[:2]]
    context = {"summary_rows": rows}
    consumption.apply_summary_growth_rounding(context, growth_digits)
    rounded_growth = {
        -1: Decimal("1"),
        0: Decimal("1.23456789"),
        1: Decimal("1.2"),
        2: Decimal("1.23"),
        3: Decimal("1.235"),
    }[general_digits]
    assert [row["year_values"] for row in rows[:2]] == source_values
    if growth_digits == -1:
        expected = str(rounded_growth.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    else:
        digits = 6 if growth_digits == 0 else growth_digits
        expected = format(rounded_growth, f".{digits}f").replace(".", ",")
    assert [row["year_values"] for row in rows[2:]] == [[expected], [expected]]
    expected_tooltip = format(rounded_growth, "f").replace(".", ",")
    assert [row["year_numeric_tooltips"] for row in rows[2:]] == [[expected_tooltip], [expected_tooltip]]
    consumption.apply_summary_growth_rounding(context)
    default_display = format(
        rounded_growth.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f"
    ).replace(".", ",")
    assert [row["year_values"] for row in rows[2:]] == [[default_display], [default_display]]


@pytest.mark.parametrize("raw,expected", [("0", "0,00"), ("1,2", "1,20"), ("-1,2", "-1,20")])
def test_default_growth_precision_always_has_two_decimal_places(raw, expected):
    row = {"parameter_key": GROWTH_KEYS[0], "year_values": [raw], "year_numeric_tooltips": [raw]}
    consumption.apply_summary_growth_rounding({"summary_rows": [row]})
    assert row["year_values"] == [expected]


def test_formula_growth_keeps_raw_precision_and_missing_years():
    row = {"parameter_key": GROWTH_KEYS[0]}
    consumption._write_numeric_year_values_to_summary_row(
        row, [2024, 2025], {2024: None, 2025: Decimal("1.23456789")},
        parameter_key=GROWTH_KEYS[0], rounding_digits=1,
        respect_perimeter_variant_year_bounds=False,
    )
    consumption.apply_summary_growth_rounding({"summary_rows": [row]}, 3)
    assert row["year_values"] == ["–", "1,235"]
    assert row["year_numeric_tooltips"] == ["", "1,23456789"]


def test_sipr_growth_recalculation_uses_rounded_sipr_consumption():
    rows = [
        {
            "entity_label": "Объект",
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "year_values": ["100", "101,23456789"],
            "year_numeric_tooltips": ["100", "101,23456789"],
        },
        {
            "entity_label": "Объект",
            "parameter_key": "energy_consumption_sipr_yoy_growth_pct",
            "year_values": ["–", "0"],
            "year_numeric_tooltips": ["", "0"],
        },
    ]
    consumption.recompute_sipr_growth_metrics_for_summary_rows(rows, [2024, 2025], 2)
    assert rows[1]["year_values"] == ["–", "1,23"]
    assert rows[1]["year_numeric_tooltips"] == ["", "1,23"]


@pytest.mark.parametrize("raw,expected", [(None, 2), ("", 2), ("invalid", 2), ("9", 2), ("0", 0), ("-1", -1), ("3", 3)])
def test_control_and_request_parser_agree_on_defaults(app, raw, expected):
    query = {} if raw is None else {"growth_rounding_digits": raw}
    with app.test_request_context("/energy_consumption/", query_string=query):
        assert _parse_rounding_digits("growth_rounding_digits", 2) == expected
        assert _parse_rounding_digits() == 1
        html = render_template_string("{% include 'energy_consumption/_growth_rounding.html' %}")
    assert re.search(r'<option value="' + str(expected) + r'" selected>', html)
    assert 'form="powerDemandSummaryYearForm"' in html


ROUNDING_TEMPLATES = [path for path in TEMPLATES.rglob("*.html")
                      if 'id="rounding_digits"' in path.read_text(encoding="utf-8")]


@pytest.mark.parametrize("template", ROUNDING_TEMPLATES, ids=lambda path: path.stem)
def test_growth_control_is_immediately_left_of_existing_rounding_on_every_page(template):
    source = template.read_text(encoding="utf-8")
    assert source.count("include 'energy_consumption/_growth_rounding.html'") == 1
    assert re.search(r"{% include 'energy_consumption/_growth_rounding.html' %}\s*"
                     r'<div[^>]*>\s*<label for="rounding_digits"', source)


@pytest.mark.parametrize("sipr_on", [False, True])
@pytest.mark.parametrize("digits", [-1, 0, 1, 2, 3])
def test_excel_respects_growth_precision_without_affecting_source_values(digits, sipr_on):
    rows = [dict(parameter_key=key, parameter_label=key, entity_label="System",
                 year_values=["1,23"], year_numeric_tooltips=["1,23456789"])
            for key in ("energy_consumption_mln_kvt_ch", *GROWTH_KEYS)]
    stream = build_demand_summary_excel_stream(
        summary_rows=rows, years=[2025], sheet_title="Summary", rounding_digits=1,
        growth_rounding_digits=digits, sipr_on=sipr_on,
    )
    sheet = load_workbook(stream).active
    assert sheet["C2"].number_format == excel_number_format(1)
    for address in ("C3", "C4"):
        assert sheet[address].number_format == excel_number_format(6 if digits == 0 else digits)
        assert sheet[address].value == pytest.approx(1.23456789)

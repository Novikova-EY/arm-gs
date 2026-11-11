from decimal import Decimal

import pytest
from openpyxl import load_workbook

from app.common.services.excel_numeric_cell import excel_number_format, parse_excel_numeric
from app.energy_consumption.services.energy_consumption_summary_export_services import (
    build_demand_summary_excel_stream,
)
from app.energy_consumption.services.energy_consumption_summary_import_services import (
    SHEET_MLN_KVTCH,
    SHEET_SIPR,
)
from app.energy_consumption.services.energy_consumption_summary_services import GAES_CHARGE_PARAMETER_KEY


@pytest.mark.parametrize("separator", [" ", "\u00a0", "\u202f", "\u2009"])
@pytest.mark.parametrize("sign", ["", "-", "\u2212"])
def test_grouped_numeric_values_are_numbers_on_every_sheet(separator, sign):
    raw = f"{sign}1{separator}234{separator}567,890123"
    expected = -1234567.890123 if sign else 1234567.890123
    assert parse_excel_numeric(raw) == expected
    rows = [
        {
            "entity_label": "ОЭС Центра",
            "show_entity_cell": True,
            "parameter_key": parameter,
            "parameter_label": label,
            "perimeter_variant_code": "without_nt",
            "year_values": ["1 234 567,9", "0", "–"],
            "year_numeric_tooltips": [raw, "0", ""],
        }
        for parameter, label in (
            ("energy_consumption_mln_kvt_ch", "Потребление ЭЭ"),
            ("energy_consumption_sipr_mln_kvt_ch", "Потребление ЭЭ (СиПР)"),
        )
    ]
    workbook = load_workbook(build_demand_summary_excel_stream(
        summary_rows=rows, years=[2024, 2025, 2026], sheet_title="Спрос", rounding_digits=1,
    ))
    assert workbook.sheetnames == ["Спрос", SHEET_MLN_KVTCH, SHEET_SIPR]
    for sheet in workbook:
        for row in range(2, sheet.max_row + 1):
            cell = sheet.cell(row, 3)
            assert cell.data_type == "n"
            assert cell.value == expected
            assert cell.number_format == excel_number_format(1 if sheet == workbook.active else 0)
            zero = sheet.cell(row, 4)
            assert zero.data_type == "n" and zero.value == 0
            missing = sheet.cell(row, 5)
            assert missing.value == ("–" if sheet == workbook.active else None)
            assert sheet.cell(row, 1).data_type == "s"
            assert sheet.cell(row, 2).data_type == "s"


@pytest.mark.parametrize("value", [Decimal("1234.567890123"), 1234.567890123, "1\u202f234,567890123"])
@pytest.mark.parametrize("parameter", [
    "energy_consumption_mln_kvt_ch",
    "energy_consumption_sipr_mln_kvt_ch",
    "energy_consumption_yoy_growth_pct",
    "energy_consumption_sipr_yoy_growth_pct",
    GAES_CHARGE_PARAMETER_KEY,
])
@pytest.mark.parametrize("rounding", [-1, 0, 1, 2, 3])
def test_numeric_year_values_without_tooltips_preserve_precision(value, parameter, rounding):
    workbook = load_workbook(build_demand_summary_excel_stream(
        summary_rows=[{
            "parameter_key": parameter,
            "year_values": [value],
        }],
        years=[2024], sheet_title="Спрос", rounding_digits=rounding,
    ))
    cell = workbook.active["C2"]
    assert cell.data_type == "n"
    assert cell.value == 1234.567890123
    assert cell.number_format == excel_number_format(2 if "yoy_growth" in parameter else rounding)

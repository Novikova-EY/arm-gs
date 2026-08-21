# -*- coding: utf-8 -*-
"""Юнит-тесты Excel-выгрузки расчета балансов электрической энергии."""

from __future__ import annotations

from unittest.mock import patch

from openpyxl import load_workbook

from app.energy_balance.services.ee_balance_excel_services import (
    ee_balance_excel_table_title,
    export_ee_balance_to_excel,
)
from app.energy_balance.services.power_balance_page_services import KIND_CHILD, KIND_TOTAL


def test_excel_table_title_uses_energy_unit():
    assert (
        ee_balance_excel_table_title(
            {
                "table_number": 4,
                "title": "Баланс электрической энергии ОЭС Юга",
                "sheet_name": "ОЭС Юга",
            }
        )
        == "Таблица 4 - Баланс электрической энергии ОЭС Юга, млн.кВт·ч"
    )


def _sample_sheets():
    return [
        {
            "slug": "centr",
            "sheet_name": "Центр",
            "title": "Баланс электрической энергии Центр",
            "table_number": 2,
            "unit": "млн.кВт·ч",
        },
        {
            "slug": "sibir",
            "sheet_name": "Сибирь",
            "title": "Баланс электрической энергии Сибирь",
            "table_number": 3,
            "unit": "млн.кВт·ч",
        },
    ]


def _sample_tables():
    return {
        "centr": {
            "sheet": _sample_sheets()[0],
            "rows": [
                {
                    "key": "consumption",
                    "label": "Потребление электрической энергии",
                    "kind": KIND_TOTAL,
                    "indent": 0,
                    "italic": False,
                    "year_values_raw": {2026: 10},
                    "year_values": {2026: "10"},
                    "hide_when_empty": False,
                    "is_flow_block": False,
                },
                {
                    "key": "generation_aes",
                    "label": "АЭС",
                    "kind": KIND_CHILD,
                    "indent": 1,
                    "italic": False,
                    "year_values_raw": {2026: 4},
                    "year_values": {2026: "4"},
                    "hide_when_empty": False,
                    "is_flow_block": False,
                },
            ],
        },
        "sibir": {
            "sheet": _sample_sheets()[1],
            "rows": [
                {
                    "key": "consumption",
                    "label": "Потребление электрической энергии",
                    "kind": KIND_TOTAL,
                    "indent": 0,
                    "italic": False,
                    "year_values_raw": {2026: 20},
                    "year_values": {2026: "20"},
                    "hide_when_empty": False,
                    "is_flow_block": False,
                },
            ],
        },
    }


def test_export_writes_sheet_per_tab_and_energy_title():
    with patch(
        "app.energy_balance.services.ee_balance_excel_services.build_ee_balance_tables",
        return_value=_sample_tables(),
    ), patch(
        "app.energy_balance.services.ee_balance_excel_services.get_ee_balance_sheets",
        return_value=_sample_sheets(),
    ), patch(
        "app.energy_balance.services.ee_balance_excel_services.get_ee_balance_year_columns",
        return_value=[2026],
    ), patch(
        "app.energy_balance.services.ee_balance_excel_services.get_ee_balance_year_features",
        return_value={2026: "План"},
    ):
        stream = export_ee_balance_to_excel(
            tables=_sample_tables(),
            sheets=_sample_sheets(),
            years=[2026],
            year_features={2026: "План"},
            include_type_breakdown=True,
        )
    wb = load_workbook(stream)
    assert wb.sheetnames == ["Центр", "Сибирь"]
    ws = wb["Центр"]
    assert "Баланс электрической энергии" in str(ws["A1"].value)
    assert "млн.кВт·ч" in str(ws["A1"].value)
    assert ws["A3"].value == "Потребление электрической энергии"
    assert ws["B3"].value == 10
    assert ws["A4"].value == "АЭС"

# -*- coding: utf-8 -*-
"""Видимость строк ТЭС в помесячном балансе отдельных листов."""

from decimal import Decimal
from unittest.mock import patch

import pytest

from app.energy_balance.services import ee_balance_tes_forecast_services as forecast


def test_tes_rows_are_hidden_only_on_tites_sibir_forecast_page():
    calculated = forecast.compute_tes_forecast_year(
        year=2026,
        stored={"tes_station_1": {1: Decimal("10")}},
        ges_stations=[
            {"id": 2, "label": "ГЭС", "capacity": Decimal("30"), "pivr": {1: Decimal("5")}}
        ],
        tes_stations=[
            {
                "id": 1,
                "label": "ТЭЦ",
                "capacity": Decimal("20"),
                "machines": [{"id": 11, "label": "Агрегат", "capacity": Decimal("20")}],
                "fact_avg_years": [{"year": 2024, "values": {1: Decimal("3")}}],
            }
        ],
    )
    original_rows = forecast.format_tes_forecast_rows(calculated, 2)
    original_keys = [row["key"] for row in original_rows]
    assert {
        "tes_fact_avg_station_1_year_2024",
        "tes_machine_11",
        "capacity_tes_machine_11",
        "chiim_tes_machine_11",
        "kium_tes_machine_11",
    } <= set(original_keys)
    sheets = [
        {"slug": "oes-318", "sheet_name": "ТИТЭС Сибири"},
        {"slug": "another-sheet", "sheet_name": "ТИТЭС Сибири"},
        {"slug": "magadan", "sheet_name": "Центральный энергорайон Магаданской области"},
    ]
    with (
        patch.object(forecast, "get_power_balance_year_columns", return_value=[2026]),
        patch.object(
            forecast, "get_power_balance_year_features", return_value={2026: "план"}
        ),
        patch.object(forecast, "get_power_balance_filter_year_list", return_value=[2026]),
        patch.object(
            forecast, "build_tes_forecast_year_payload", return_value={"rows": original_rows}
        ),
    ):
        contexts = [
            forecast.build_tes_forecast_context(sheet, view_year=2026)
            for sheet in sheets
        ]

    sibir_keys = [row["key"] for row in contexts[0]["rows"]]
    assert {
        "hours", "consumption", "production", "pivr_sum", "ges_station_2",
        "ges_used", "deficit", "capacity_total", "capacity_ges",
    } <= set(sibir_keys)
    assert not any(key.startswith(("tes_", "capacity_tes", "chiim_", "kium_")) for key in sibir_keys)
    assert [row["key"] for row in contexts[1]["rows"]] == original_keys
    assert [row["key"] for row in contexts[2]["rows"]] == original_keys
    assert [row["key"] for row in original_rows] == original_keys


@pytest.mark.parametrize(
    "sheet",
    [
        {"slug": "oes-318", "sheet_name": "ТИТЭС Сибири"},
        {"slug": "eu-257", "sheet_name": "Центральный энергорайон Магаданской области"},
    ],
)
@pytest.mark.parametrize(
    "years, view_year, selected_year, is_plan_year",
    [
        ([2024, 2025, 2026, 2027], None, 2024, False),
        ([2024, 2025, 2026, 2027], "2024", 2024, False),
        ([2024, 2025, 2026, 2027], "2025", 2025, False),
        ([2024, 2025, 2026, 2027], "2027", 2027, True),
        ([2024, 2025], None, 2024, False),
        ([2025], "2025", 2025, False),
        ([2026, 2027], None, 2026, True),
        ([2024, 2025], "2027", 2024, False),
    ],
)
def test_forecast_tabs_include_all_selected_years(
    sheet, years, view_year, selected_year, is_plan_year
):
    features = {2024: "факт", 2025: "текущий (оценка)", 2026: "план", 2027: "план"}
    with (
        patch.object(forecast, "get_power_balance_year_columns", return_value=years),
        patch.object(forecast, "get_power_balance_year_features", return_value=features),
        patch.object(
            forecast, "get_power_balance_filter_year_list", return_value=list(features)
        ),
        patch.object(
            forecast,
            "build_tes_forecast_year_payload",
            side_effect=lambda sheet, year, rounding_digits: {
                "rows": [{"key": "hours", "year": year}]
            },
        ),
    ):
        context = forecast.build_tes_forecast_context(
            sheet, start_year=years[0], end_year=years[-1], view_year=view_year
        )

    assert context["range_years"] == years
    assert context["view_year"] == selected_year
    assert context["rows"] == [{"key": "hours", "year": selected_year}]
    assert context["is_plan_year"] is is_plan_year
    assert (context["start_year"], context["end_year"]) == (years[0], years[-1])

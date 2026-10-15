# -*- coding: utf-8 -*-
"""Юнит-тесты годового импорта/экспорта ЭЭ по ОЭС и странам."""

from __future__ import annotations

from decimal import Decimal

from openpyxl import load_workbook

from app.energy_balance.services import ee_import_export_export_services as export_services
from app.energy_balance.services import ee_import_export_page_services as page_services


def test_annual_country_transfers_group_by_oes_and_split_directions(monkeypatch):
    monkeypatch.setattr(
        page_services,
        "get_ee_transfers_page_data",
        lambda **kwargs: {
            "all_rows": [
                {
                    "ues_id": 4,
                    "from_res_id": 20,
                    "to_country_id": 9,
                    "to_name": "Беларусь",
                    "periods": {2024: Decimal("-5"), 2025: Decimal("8")},
                },
                {
                    "ues_id": 4,
                    "from_res_id": 21,
                    "to_country_id": 9,
                    "to_name": "Беларусь",
                    "periods": {2024: Decimal("-3"), 2025: Decimal("1")},
                },
                {
                    "ues_id": 4,
                    "from_res_id": 20,
                    "to_country_id": None,
                    "to_name": "РЭС вне страны",
                    "periods": {2024: Decimal("100")},
                },
            ]
        },
    )
    monkeypatch.setattr(page_services, "get_union_energy_systems_map", lambda: {4: "ОЭС Центра"})
    monkeypatch.setattr(page_services, "get_union_energy_system_display_order_map", lambda: {})
    monkeypatch.setattr(page_services, "load_ee_import_export_oes_values", lambda **kwargs: {})
    monkeypatch.setattr(page_services, "get_ee_default_start_year", lambda: 2016)
    monkeypatch.setattr(
        page_services,
        "get_year_feature_dict",
        lambda: {2024: "План", 2025: "Факт", 2030: "План", 2031: "План"},
    )

    result = page_services.get_ee_import_export_page_data(
        start_year=2024,
        end_year=2025,
        rounding_digits=0,
    )

    assert result["period_columns"] == [(2024, "2024"), (2025, "2025")]
    assert result["editable_years"] == [2024]
    assert len(result["hierarchy"]) == 1
    oes = result["hierarchy"][0]
    assert oes["ues_name"] == "ОЭС Центра"
    assert [row["direction"] for row in oes["rows"]] == ["import", "export"]

    imported, exported = oes["rows"]
    assert imported["country_name"] == exported["country_name"] == "Беларусь"
    assert imported["cell_values"] == {2024: "—", 2025: "9"}
    assert exported["cell_values"] == {2024: "-8", 2025: "—"}
    assert result["direction_options"] == [
        {"id": "import", "name": "Импорт"},
        {"id": "export", "name": "Экспорт"},
    ]
    assert result["country_options"] == [{"id": 9, "name": "Беларусь"}]

    filtered = page_services.get_ee_import_export_page_data(
        start_year=2024,
        end_year=2025,
        direction_filter=["export"],
        country_filter=[9],
    )
    assert [row["direction"] for row in filtered["hierarchy"][0]["rows"]] == ["export"]

    future = page_services.get_ee_import_export_page_data(
        start_year=2030,
        end_year=2031,
    )
    future_row = future["hierarchy"][0]["rows"][0]
    assert future_row["direction"] == "import"
    assert future_row["cell_values"] == {2030: "—", 2031: "—"}
    assert future["editable_years"] == [2030, 2031]


def test_regional_filter_uses_raw_values_instead_of_oes_saved_aggregate(monkeypatch):
    monkeypatch.setattr(
        page_services,
        "get_ee_transfers_page_data",
        lambda **kwargs: {
            "all_rows": [
                {
                    "ues_id": 4,
                    "from_res_id": 20,
                    "to_country_id": 9,
                    "to_name": "Беларусь",
                    "periods": {2024: Decimal("5")},
                }
            ]
        },
    )
    monkeypatch.setattr(page_services, "get_union_energy_systems_map", lambda: {4: "ОЭС Урала"})
    monkeypatch.setattr(page_services, "get_union_energy_system_display_order_map", lambda: {})
    monkeypatch.setattr(
        page_services,
        "load_ee_import_export_oes_values",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("OES aggregate must not be used")),
    )
    monkeypatch.setattr(page_services, "get_ee_default_start_year", lambda: 2016)
    monkeypatch.setattr(page_services, "get_year_feature_dict", lambda: {2024: "Факт"})

    result = page_services.get_ee_import_export_page_data(
        start_year=2024,
        end_year=2024,
        filters={"regional_energy_system_filter": [20]},
    )

    assert result["hierarchy"][0]["rows"][0]["periods"] == {2024: Decimal("5")}


def test_countries_sort_by_display_order_then_name(monkeypatch):
    monkeypatch.setattr(
        page_services,
        "get_ee_transfers_page_data",
        lambda **kwargs: {
            "all_rows": [
                {"ues_id": 4, "to_country_id": 9, "to_name": "Belarus old", "periods": {2024: Decimal("1")}},
                {"ues_id": 4, "to_country_id": 8, "to_name": "Kazakhstan old", "periods": {2024: Decimal("-2")}},
                {"ues_id": 4, "to_country_id": 7, "to_name": "China old", "periods": {2024: Decimal("3")}},
            ],
            "foreign_border_country_list": [
                {"id": 9, "name": "Беларусь", "display_order": 2},
                {"id": 8, "name": "Казахстан", "display_order": 1},
                {"id": 7, "name": "Китай", "display_order": 1},
            ],
        },
    )
    monkeypatch.setattr(page_services, "get_union_energy_systems_map", lambda: {4: "ОЭС Центра"})
    monkeypatch.setattr(page_services, "get_union_energy_system_display_order_map", lambda: {4: 1})
    monkeypatch.setattr(page_services, "load_ee_import_export_oes_values", lambda **kwargs: {})
    monkeypatch.setattr(page_services, "get_ee_default_start_year", lambda: 2016)
    monkeypatch.setattr(page_services, "get_year_feature_dict", lambda: {2024: "Факт"})

    result = page_services.get_ee_import_export_page_data(
        start_year=2024, end_year=2024, rounding_digits=0
    )

    assert result["country_options"] == [
        {"id": 8, "name": "Казахстан"},
        {"id": 7, "name": "Китай"},
        {"id": 9, "name": "Беларусь"},
    ]
    rows = result["hierarchy"][0]["rows"]
    assert [row["country_id"] for row in rows] == [8, 7, 9]
    assert [row["country_name"] for row in rows] == ["Казахстан", "Китай", "Беларусь"]
    assert [row["direction"] for row in rows] == ["export", "import", "import"]


def test_oes_blocks_sort_by_display_order_then_name(monkeypatch):
    monkeypatch.setattr(
        page_services,
        "get_ee_transfers_page_data",
        lambda **kwargs: {
            "all_rows": [
                {"ues_id": 6, "to_country_id": 9, "to_name": "Беларусь", "periods": {2024: Decimal("1")}},
                {"ues_id": 4, "to_country_id": 9, "to_name": "Беларусь", "periods": {2024: Decimal("1")}},
                {"ues_id": 5, "to_country_id": 9, "to_name": "Беларусь", "periods": {2024: Decimal("1")}},
                {"ues_id": 7, "to_country_id": 9, "to_name": "Беларусь", "periods": {2024: Decimal("1")}},
            ],
            "foreign_border_country_list": [{"id": 9, "name": "Беларусь", "display_order": 1}],
        },
    )
    monkeypatch.setattr(
        page_services,
        "get_union_energy_systems_map",
        lambda: {4: "ОЭС Центра", 5: "ОЭС Сибири", 6: "ОЭС Востока", 7: "ОЭС Урала"},
    )
    monkeypatch.setattr(
        page_services,
        "get_union_energy_system_display_order_map",
        lambda: {4: 2, 5: 3, 6: 1, 7: None},
    )
    monkeypatch.setattr(page_services, "load_ee_import_export_oes_values", lambda **kwargs: {})
    monkeypatch.setattr(page_services, "get_ee_default_start_year", lambda: 2016)
    monkeypatch.setattr(page_services, "get_year_feature_dict", lambda: {2024: "Факт"})

    result = page_services.get_ee_import_export_page_data(
        start_year=2024, end_year=2024, rounding_digits=0
    )

    assert [block["ues_id"] for block in result["hierarchy"]] == [6, 4, 5, 7]


def test_saved_oes_values_override_source_res_sums(monkeypatch):
    monkeypatch.setattr(
        page_services,
        "get_ee_transfers_page_data",
        lambda **kwargs: {
            "all_rows": [
                {
                    "ues_id": 4,
                    "to_country_id": 9,
                    "to_name": "Беларусь",
                    "periods": {2030: Decimal("5")},
                }
            ],
            "foreign_border_country_list": [{"id": 9, "name": "Беларусь"}],
        },
    )
    monkeypatch.setattr(page_services, "get_union_energy_systems_map", lambda: {4: "ОЭС Центра"})
    monkeypatch.setattr(page_services, "get_union_energy_system_display_order_map", lambda: {})
    monkeypatch.setattr(page_services, "get_ee_default_start_year", lambda: 2021)
    monkeypatch.setattr(page_services, "get_year_feature_dict", lambda: {2030: "План"})
    monkeypatch.setattr(
        page_services,
        "load_ee_import_export_oes_values",
        lambda **kwargs: {(4, 9, 2030): Decimal("-2")},
    )

    result = page_services.get_ee_import_export_page_data(
        start_year=2030,
        end_year=2030,
        rounding_digits=0,
        saved_values_only=True,
    )

    row = result["hierarchy"][0]["rows"][0]
    assert row["direction"] == "export"
    assert row["cell_values"] == {2030: "-2"}

    monkeypatch.setattr(
        page_services,
        "load_ee_import_export_oes_values",
        lambda **kwargs: {(4, 9, 2030): None},
    )
    cleared = page_services.get_ee_import_export_page_data(
        start_year=2030,
        end_year=2030,
        saved_values_only=True,
    )
    assert cleared["hierarchy"] == []


def test_export_includes_direction_country_and_annual_values(monkeypatch):
    monkeypatch.setattr(
        export_services,
        "get_ee_import_export_page_data",
        lambda **kwargs: {
            "period_columns": [(2024, "2024")],
            "hierarchy": [
                {
                    "ues_name": "ОЭС Центра",
                    "rows": [
                        {
                            "direction": "export",
                            "direction_label": "Экспорт",
                            "country_name": "Беларусь",
                            "cell_values": {2024: "-8"},
                        }
                    ],
                }
            ],
        },
    )

    output = export_services.export_ee_import_export_to_excel(
        start_year=2024,
        end_year=2024,
        rounding_digits=1,
    )
    workbook = load_workbook(output, read_only=True, data_only=True)
    sheet = workbook.active

    assert next(sheet.values) == ("Экспорт/Импорт", "Страна", "2024")
    rows = list(sheet.values)
    assert rows[1] == ("ОЭС Центра", None, None)
    assert rows[2] == ("Экспорт", "Беларусь", "-8")

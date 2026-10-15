# -*- coding: utf-8 -*-
"""Юнит-тесты приема/передачи электроэнергии между ОЭС."""

from decimal import Decimal

from app.energy_balance.services import ee_receive_transfer_oes_page_services as page_services
from app.energy_balance.services import ee_receive_transfer_oes_export_services as export_services
from app.energy_balance.services import ee_transfers_page_services as transfer_services
from openpyxl import load_workbook


def test_page_aggregates_only_cross_oes_res_transfers(monkeypatch):
    monkeypatch.setattr(
        page_services,
        "get_ee_transfers_page_data",
        lambda **kwargs: {
            "all_rows": [
                {"ues_id": 4, "to_res_id": 20, "periods": {2024: Decimal("-5"), 2025: Decimal("8")}},
                {"ues_id": 4, "to_res_id": 21, "periods": {2024: Decimal("-3"), 2025: Decimal("1")}},
                {"ues_id": 4, "to_res_id": 22, "periods": {2024: Decimal("100")}},
                {"ues_id": 4, "to_res_id": 23, "periods": {2024: Decimal("7"), 2025: Decimal("9")}},
            ]
        },
    )
    monkeypatch.setattr(
        page_services,
        "_get_res_territory_maps",
        lambda: {"res_ues_map": {20: 9, 21: 9, 22: 8, 23: 4}},
    )
    monkeypatch.setattr(page_services, "get_union_energy_systems_map", lambda: {4: "ОЭС Центра", 8: "ОЭС Востока", 9: "ОЭС Урала"})
    monkeypatch.setattr(page_services, "get_union_energy_system_display_order_map", lambda: {})
    monkeypatch.setattr(
        page_services,
        "load_ee_receive_transfer_oes_values",
        lambda **kwargs: {(4, 9, 2024): Decimal("300")},
    )
    monkeypatch.setattr(page_services, "get_ee_default_start_year", lambda: 2016)
    monkeypatch.setattr(page_services, "get_year_feature_dict", lambda: {2024: "Факт", 2025: "План"})

    result = page_services.get_ee_receive_transfer_oes_page_data(
        start_year=2024, end_year=2025, rounding_digits=0
    )

    rows = result["hierarchy"][0]["rows"]
    assert result["hierarchy"][0]["ues_name"] == "ОЭС Центра"
    assert [(row["direction"], row["country_name"]) for row in rows] == [
        ("receive", "ОЭС Востока"),
        ("receive", "ОЭС Урала"),
    ]
    ues_rows = [row for row in rows if row["country_id"] == 9]
    assert ues_rows[0]["cell_values"] == {2024: "300", 2025: "9"}
    assert result["country_options"] == [
        {"id": 8, "name": "ОЭС Востока"},
        {"id": 9, "name": "ОЭС Урала"},
    ]


def test_regional_filter_uses_raw_flows_instead_of_oes_saved_aggregate(monkeypatch):
    monkeypatch.setattr(
        page_services,
        "get_ee_transfers_page_data",
        lambda **kwargs: {
            "all_rows": [
                {
                    "ues_id": 4,
                    "from_res_id": 20,
                    "to_res_id": 30,
                    "periods": {2024: Decimal("12")},
                }
            ]
        },
    )
    monkeypatch.setattr(
        page_services,
        "_get_res_territory_maps",
        lambda: {"res_ues_map": {20: 4, 30: 9}},
    )
    monkeypatch.setattr(page_services, "get_union_energy_systems_map", lambda: {4: "ОЭС Урала", 9: "ОЭС Сибири"})
    monkeypatch.setattr(page_services, "get_union_energy_system_display_order_map", lambda: {})
    monkeypatch.setattr(
        page_services,
        "load_ee_receive_transfer_oes_values",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("OES aggregate must not be used")),
    )
    monkeypatch.setattr(page_services, "get_ee_default_start_year", lambda: 2016)
    monkeypatch.setattr(page_services, "get_year_feature_dict", lambda: {2024: "Факт"})

    result = page_services.get_ee_receive_transfer_oes_page_data(
        start_year=2024,
        end_year=2024,
        filters={"regional_energy_system_filter": [20]},
    )

    assert result["hierarchy"][0]["rows"][0]["periods"] == {2024: Decimal("12")}


def test_page_maps_subjects_and_energy_areas_to_res_before_oes_aggregation(monkeypatch):
    monkeypatch.setattr(
        page_services,
        "get_ee_transfers_page_data",
        lambda **kwargs: {
            "all_rows": [
                {"ues_id": 4, "to_rd_id": 50, "periods": {2024: Decimal("2")}},
                {"ues_id": 4, "to_eu_id": 60, "periods": {2024: Decimal("3")}},
                {"ues_id": 4, "to_res_id": 20, "periods": {2024: Decimal("5")}},
            ]
        },
    )
    monkeypatch.setattr(
        page_services,
        "_get_res_territory_maps",
        lambda: {
            "res_ues_map": {20: 9},
            "rd_res_map": {50: {20}},
            "eu_res_map": {60: 20},
        },
    )
    monkeypatch.setattr(page_services, "get_union_energy_systems_map", lambda: {4: "Источник", 9: "Получатель"})
    monkeypatch.setattr(page_services, "get_union_energy_system_display_order_map", lambda: {})
    monkeypatch.setattr(page_services, "load_ee_receive_transfer_oes_values", lambda **kwargs: {})
    monkeypatch.setattr(page_services, "get_ee_default_start_year", lambda: 2016)
    monkeypatch.setattr(page_services, "get_year_feature_dict", lambda: {2024: "Факт"})

    result = page_services.get_ee_receive_transfer_oes_page_data(
        start_year=2024, end_year=2024, rounding_digits=0
    )

    assert len(result["hierarchy"]) == 1
    assert result["hierarchy"][0]["rows"][0]["country_id"] == 9
    assert result["hierarchy"][0]["rows"][0]["cell_values"] == {2024: "10"}


def test_tites_member_res_is_grouped_under_its_own_ues_not_parent_oes():
    tites_transfer = type(
        "Transfer",
        (),
        {
            "id_union_energy_system": 411,
            "id_from_regional_energy_system": 2822,
            "id_from_regional_district": None,
        },
    )()
    ordinary_transfer = type(
        "Transfer",
        (),
        {
            "id_union_energy_system": 411,
            "id_from_regional_energy_system": 2792,
            "id_from_regional_district": None,
        },
    )()
    non_member_in_tites_workbook = type(
        "Transfer",
        (),
        {
            "id_union_energy_system": 417,
            "id_from_regional_energy_system": 2792,
            "id_from_regional_district": None,
        },
    )()

    assert transfer_services._infer_transfer_ues_id(
        tites_transfer,
        res_ues_map={2822: 417, 2792: 411},
        rd_res_map={},
        tites_ues_ids={417},
    ) == 417
    assert transfer_services._infer_transfer_ues_id(
        ordinary_transfer,
        res_ues_map={2822: 417, 2792: 411},
        rd_res_map={},
        tites_ues_ids={417},
    ) == 411
    assert transfer_services._infer_transfer_ues_id(
        non_member_in_tites_workbook,
        res_ues_map={2822: 417, 2792: 411},
        rd_res_map={},
        tites_ues_ids={417},
    ) == 411


def test_ambiguous_subject_uses_earliest_oes_res():
    territory_maps = {
        "rd_res_map": {50: {10, 11}},
        "res_ues_map": {10: 9, 11: 8},
    }
    names = {8: "ОЭС Северо-Запада", 9: "ОЭС Сибири"}
    display_orders = {8: 2, 9: 1}

    target_res_id = page_services._infer_transfer_target_res_id(
        {"to_rd_id": 50},
        territory_maps=territory_maps,
        ues_names=names,
        display_orders=display_orders,
    )

    assert target_res_id == 10
    assert territory_maps["res_ues_map"][target_res_id] == 9


def test_country_options_and_rows_sort_by_display_order_then_name(monkeypatch):
    monkeypatch.setattr(
        page_services,
        "get_ee_transfers_page_data",
        lambda **kwargs: {
            "all_rows": [
                {"ues_id": 4, "to_res_id": 20, "periods": {2024: Decimal("5")}},
                {"ues_id": 4, "to_res_id": 21, "periods": {2024: Decimal("6")}},
                {"ues_id": 4, "to_res_id": 22, "periods": {2024: Decimal("7"), 2025: Decimal("-2")}},
            ]
        },
    )
    monkeypatch.setattr(
        page_services,
        "_get_res_territory_maps",
        lambda: {"res_ues_map": {20: 9, 21: 8, 22: 7}},
    )
    monkeypatch.setattr(
        page_services,
        "get_union_energy_systems_map",
        lambda: {4: "ОЭС-источник", 7: "Бета", 8: "Альфа", 9: "ОЭС с первым порядком"},
    )
    monkeypatch.setattr(
        page_services,
        "get_union_energy_system_display_order_map",
        lambda: {4: 0, 7: 1, 8: 1, 9: 2},
    )
    monkeypatch.setattr(page_services, "load_ee_receive_transfer_oes_values", lambda **kwargs: {})
    monkeypatch.setattr(page_services, "get_ee_default_start_year", lambda: 2016)
    monkeypatch.setattr(page_services, "get_year_feature_dict", lambda: {2024: "Факт", 2025: "План"})

    result = page_services.get_ee_receive_transfer_oes_page_data(
        start_year=2024, end_year=2025, rounding_digits=0
    )

    assert result["country_options"] == [
        {"id": 8, "name": "Альфа"},
        {"id": 7, "name": "Бета"},
        {"id": 9, "name": "ОЭС с первым порядком"},
    ]
    rows = result["hierarchy"][0]["rows"]
    assert [(row["country_id"], row["direction"]) for row in rows] == [
        (8, "receive"),
        (7, "receive"),
        (7, "transfer"),
        (9, "receive"),
    ]


def test_saved_oes_pair_value_overrides_res_sum(monkeypatch):
    monkeypatch.setattr(
        page_services,
        "get_ee_transfers_page_data",
        lambda **kwargs: {
            "all_rows": [{"ues_id": 4, "to_res_id": 20, "periods": {2024: Decimal("5")}}]
        },
    )
    monkeypatch.setattr(page_services, "_get_res_territory_maps", lambda: {"res_ues_map": {20: 9}})
    monkeypatch.setattr(page_services, "get_union_energy_systems_map", lambda: {4: "ОЭС Центра", 9: "ОЭС Урала"})
    monkeypatch.setattr(page_services, "get_union_energy_system_display_order_map", lambda: {})
    monkeypatch.setattr(
        page_services,
        "load_ee_receive_transfer_oes_values",
        lambda **kwargs: {(4, 9, 2024): Decimal("-2")},
    )
    monkeypatch.setattr(page_services, "get_ee_default_start_year", lambda: 2021)
    monkeypatch.setattr(page_services, "get_year_feature_dict", lambda: {2024: "Факт"})

    result = page_services.get_ee_receive_transfer_oes_page_data(
        start_year=2024, end_year=2024, rounding_digits=0
    )
    row = result["hierarchy"][0]["rows"][0]
    assert row["direction"] == "transfer"
    assert row["cell_values"] == {2024: "-2"}


def test_saved_zero_value_remains_visible_on_receive_row(monkeypatch):
    monkeypatch.setattr(page_services, "get_ee_transfers_page_data", lambda **kwargs: {"all_rows": []})
    monkeypatch.setattr(page_services, "_get_res_territory_maps", lambda: {"res_ues_map": {}})
    monkeypatch.setattr(
        page_services,
        "get_union_energy_systems_map",
        lambda: {4: "ОЭС Центра", 9: "ОЭС Урала"},
    )
    monkeypatch.setattr(page_services, "get_union_energy_system_display_order_map", lambda: {})
    monkeypatch.setattr(
        page_services,
        "load_ee_receive_transfer_oes_values",
        lambda **kwargs: {(4, 9, 2024): Decimal("0")},
    )
    monkeypatch.setattr(page_services, "get_ee_default_start_year", lambda: 2021)
    monkeypatch.setattr(page_services, "get_year_feature_dict", lambda: {2024: "План"})

    result = page_services.get_ee_receive_transfer_oes_page_data(
        start_year=2024, end_year=2024, rounding_digits=0
    )

    row = result["hierarchy"][0]["rows"][0]
    assert row["direction"] == "receive"
    assert row["cell_values"] == {2024: "0"}


def test_export_uses_receive_transfer_and_oes_headers(monkeypatch):
    monkeypatch.setattr(
        export_services,
        "get_ee_receive_transfer_oes_page_data",
        lambda **kwargs: {
            "period_columns": [(2024, "2024")],
            "hierarchy": [
                {
                    "ues_name": "ОЭС Центра",
                    "rows": [
                        {
                            "direction_label": "Передача",
                            "country_name": "ОЭС Урала",
                            "cell_values": {2024: "-8"},
                        }
                    ],
                }
            ],
        },
    )
    output = export_services.export_ee_receive_transfer_oes_to_excel(
        start_year=2024, end_year=2024, rounding_digits=1
    )
    sheet = load_workbook(output, read_only=True, data_only=True).active
    assert next(sheet.values) == ("Прием/Передача", "Наименование ОЭС", "2024")
    rows = list(sheet.values)
    assert rows[1] == ("ОЭС Центра", None, None)
    assert rows[2] == ("Передача", "ОЭС Урала", "-8")

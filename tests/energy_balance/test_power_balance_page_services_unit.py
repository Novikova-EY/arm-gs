# -*- coding: utf-8 -*-
"""Юнит-тесты каркаса страниц расчета балансов мощности."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.energy_balance.services.power_balance_page_services import (
    GROUP_EES,
    GROUP_OES,
    GROUP_SZ,
    KALININGRAD_LARGEST_UNIT_MW,
    POWER_BALANCE_SHEETS,
    VOSTOK_LAYOUT_SEED_PARENT,
    build_power_balance_rows,
    build_power_balance_station_list_url,
    build_power_balance_table_context,
    build_power_balance_tables,
    custom_flow_row_key,
    get_power_balance_sheet,
    get_power_balance_sheets,
    get_power_balance_year_columns,
    get_power_balance_year_features,
    group_power_balance_sheets,
    is_persistable_power_balance_slug,
    power_balance_station_list_query,
    resolve_power_balance_rounding_digits,
    mark_power_balance_empty_rows,
)


@pytest.fixture(autouse=True)
def _stable_station_types_and_no_db_load(monkeypatch):
    monkeypatch.setattr(
        "app.energy_balance.services.power_balance_installed_capacity_services.get_station_type_list_full",
        lambda: [],
    )
    monkeypatch.setattr(
        "app.energy_balance.services.power_balance_page_services.load_power_balance_installed_capacity_inputs",
        lambda years, sheets=None: {},
    )
    monkeypatch.setattr(
        "app.energy_balance.services.power_balance_page_services.load_power_balance_demand_max_inputs",
        lambda years, sheets=None: {},
    )
    monkeypatch.setattr(
        "app.energy_balance.services.power_balance_page_services.load_power_balance_custom_flows",
        lambda sheets=None: {},
    )
    monkeypatch.setattr(
        "app.energy_balance.services.power_balance_page_services.load_power_balance_export_inputs",
        lambda years, sheets=None: {},
    )


def test_power_balance_sheets_order_ees_then_sz_then_oes():
    sheets = get_power_balance_sheets()
    names = [sheet["sheet_name"] for sheet in sheets]
    assert names == [
        "ЕЭС России",
        "1-я СЗ ЕЭС",
        "2-я СЗ ЕЭС (ОЭС Востока)",
        "Калининградская СЗ ЕЭС",
        "Северо-Запад",
        "Центр",
        "Средняя Волга",
        "Юг",
        "Урал",
        "Сибирь",
    ]
    slugs = [sheet["slug"] for sheet in POWER_BALANCE_SHEETS]
    assert len(slugs) == len(set(slugs))
    groups = group_power_balance_sheets(sheets)
    assert [item["group"] for item in groups] == [GROUP_EES, GROUP_SZ, GROUP_OES]
    assert [sheet["sheet_name"] for sheet in groups[0]["sheets"]] == ["ЕЭС России"]
    assert [sheet["sheet_name"] for sheet in groups[1]["sheets"]] == [
        "1-я СЗ ЕЭС",
        "2-я СЗ ЕЭС (ОЭС Востока)",
        "Калининградская СЗ ЕЭС",
    ]
    for sheet in sheets:
        assert sheet["title"] == f"Баланс мощности {sheet['sheet_name']}"


def test_get_power_balance_sheet_unknown_returns_none():
    assert get_power_balance_sheet("unknown") is None
    assert get_power_balance_sheet("sibir")["table_number"] == 10


@pytest.mark.parametrize("sheet", list(POWER_BALANCE_SHEETS))
def test_each_layout_has_unique_row_keys_and_core_rows(sheet):
    rows = build_power_balance_rows(sheet["layout"])
    keys = [row["key"] for row in rows]
    assert keys
    assert len(keys) == len(set(keys))
    assert "demand_max" in keys
    assert "export" in keys
    export = next(row for row in rows if row["key"] == "export")
    assert export["editable_values"] is True
    assert not export.get("formula")
    assert "installed_aes" in keys
    assert "installed_ses_ves" in keys
    assert "flow_in" in keys
    assert "flow_out" in keys
    assert all(row["unit"] == "МВт" for row in rows)
    flow_keys = {row["key"] for row in rows if row.get("is_flow_block")}
    assert "flow_total" in flow_keys
    assert "flow_in" in flow_keys
    assert "flow_out" in flow_keys
    assert "demand_max" not in flow_keys
    if "surplus_deficit_with_flow" in keys:
        assert "surplus_deficit_with_flow" in flow_keys
    assert "surplus_deficit" not in flow_keys


def test_yug_and_sibir_and_kaliningrad_specific_rows():
    yug_keys = {row["key"] for row in build_power_balance_rows("oes_yug")}
    assert "flow_out_kherson_zaporozhye" not in yug_keys
    assert "flow_out_lnr_dnr" not in yug_keys
    sibir_keys = {row["key"] for row in build_power_balance_rows("oes_sibir")}
    assert "flow_in_vostok" not in sibir_keys
    assert "flow_out_vostok" not in sibir_keys
    assert "flow_in_udokan" not in sibir_keys
    assert "flow_out_peleduy" not in sibir_keys
    vostok_keys = {row["key"] for row in build_power_balance_rows("oes_vostok")}
    assert "flow_in_peleduy" not in vostok_keys
    assert "flow_out_udokan" not in vostok_keys
    assert "flow_out_rzd" not in vostok_keys
    kal_rows = build_power_balance_rows("kaliningrad")
    kal_by_key = {row["key"]: row for row in kal_rows}
    assert "1-й единицы" in kal_by_key["surplus_deficit"]["label"]
    assert "2-й единицы" in kal_by_key["surplus_deficit_second_unit"]["label"]


def test_unknown_layout_raises():
    with pytest.raises(KeyError):
        build_power_balance_rows("missing")


def test_year_columns_use_sipr_range():
    with patch(
        "app.energy_balance.services.power_balance_page_services.get_sipr_start_year",
        return_value=2026,
    ), patch(
        "app.energy_balance.services.power_balance_page_services.get_sipr_end_year",
        return_value=2031,
    ), patch(
        "app.energy_balance.services.power_balance_page_services.get_year_numbers_sorted_for_current_db_version",
        return_value=[],
    ), patch(
        "app.energy_balance.services.power_balance_page_services.get_filter_start_year",
        return_value=2026,
    ), patch(
        "app.energy_balance.services.power_balance_page_services.get_filter_end_year",
        return_value=2031,
    ):
        assert get_power_balance_year_columns() == [2026, 2027, 2028, 2029, 2030, 2031]
        assert get_power_balance_year_columns(2028, 2029) == [2028, 2029]


def test_year_features_from_years_catalog():
    with patch(
        "app.energy_balance.services.power_balance_page_services.get_year_feature_dict",
        return_value={2026: "Отчет", 2027: "  ", 2028: "План"},
    ):
        assert get_power_balance_year_features() == {2026: "Отчет", 2028: "План"}


def test_rounding_digits_parsed_and_applied():
    assert resolve_power_balance_rounding_digits(None) == 1
    assert resolve_power_balance_rounding_digits("1") == 1
    assert resolve_power_balance_rounding_digits("9") == 1
    tables = build_power_balance_tables(
        [2026],
        inputs={"centr": {"demand_max": {2026: "10.456"}}},
        rounding_digits=1,
    )
    assert _row_display(tables, "centr", "demand_max", 2026) == "10,5"
    tables3 = build_power_balance_tables(
        [2026],
        inputs={"centr": {"demand_max": {2026: "10.456"}}},
        rounding_digits=3,
    )
    assert _row_display(tables3, "centr", "demand_max", 2026) == "10,456"


def test_table_context_for_known_slug():
    with patch(
        "app.energy_balance.services.power_balance_page_services.get_sipr_start_year",
        return_value=2026,
    ), patch(
        "app.energy_balance.services.power_balance_page_services.get_sipr_end_year",
        return_value=2027,
    ), patch(
        "app.energy_balance.services.power_balance_page_services.get_year_feature_dict",
        return_value={2026: "Отчет", 2027: "План"},
    ):
        context = build_power_balance_table_context("centr")
    assert context is not None
    assert context["sheet"]["sheet_name"] == "Центр"
    assert context["page_title"] == "Баланс мощности Центр"
    assert [item["group"] for item in context["sheet_groups"]] == [GROUP_EES, GROUP_SZ, GROUP_OES]
    assert context["years"] == [2026, 2027]
    assert context["year_features"][2026] == "Отчет"
    assert context["year_features"][2027] == "План"
    assert context["start_year"] == 2026
    assert context["end_year"] == 2027
    assert context["rounding_digits"] == 1
    assert 2026 in context["filter_year_list"]
    assert "start_year=2026" in context["station_list_url"]
    demand_max = next(row for row in context["rows"] if row["key"] == "demand_max")
    demand_total = next(row for row in context["rows"] if row["key"] == "demand_total")
    export = next(row for row in context["rows"] if row["key"] == "export")
    assert demand_max["year_values"] == {}
    assert demand_total["year_values"][2026] == "0"
    assert export["editable_values"] is True
    assert export["hide_when_empty"] is False
    assert "Максимум потребления" in demand_total["formula_tooltip"]
    assert demand_max["hide_when_empty"] is True
    assert demand_total["hide_when_empty"] is True
    assert build_power_balance_table_context("nope") is None


def test_empty_rows_hidden_keep_filled_custom_and_ancestors():
    tables = build_power_balance_tables(
        [2026],
        inputs={"centr": {"demand_max": {2026: 10}}},
        custom_flows={
            "centr": [
                {
                    "id": 1,
                    "direction": "flow_in",
                    "label": "пусто",
                    "sort_order": 0,
                    "values": {},
                }
            ]
        },
    )
    rows = tables["centr"]["rows"]
    by_key = {row["key"]: row for row in rows}
    assert by_key["demand_max"]["hide_when_empty"] is False
    assert by_key["demand_total"]["hide_when_empty"] is False
    assert by_key["export"]["hide_when_empty"] is False
    assert by_key["export"]["editable_values"] is True
    assert by_key["installed_total"]["hide_when_empty"] is True
    custom = next(row for row in rows if row.get("is_custom"))
    assert custom["hide_when_empty"] is False
    assert by_key["flow_in"]["hide_when_empty"] is False
    assert by_key["flow_total"]["hide_when_empty"] is False
    mark_power_balance_empty_rows(rows, [2026])
    assert by_key["demand_max"]["hide_when_empty"] is False


def _row_display(tables, slug, key, year):
    row = next(item for item in tables[slug]["rows"] if item["key"] == key)
    return row["year_values"][year]


def test_oes_formulas_match_excel():
    years = [2026]
    tables = build_power_balance_tables(
        years,
        inputs={
            "centr": {
                "demand_max": {2026: 100},
                "export": {2026: 20},
                "installed_aes": {2026: 40},
                "installed_ges": {2026: 10},
                "installed_gaes": {2026: 5},
                "installed_tes": {2026: 30},
                "installed_snee": {2026: 2},
                "installed_ses_ves": {2026: 3},
                "constraints": {2026: 8},
                "commissioning_after_max": {2026: 4},
                "flow_in": {2026: 7},
                "flow_out": {2026: -3},
            }
        },
    )
    assert _row_display(tables, "centr", "demand_total", 2026) == "120"
    assert _row_display(tables, "centr", "installed_total", 2026) == "90"
    assert _row_display(tables, "centr", "coverage_total", 2026) == "78"
    assert _row_display(tables, "centr", "surplus_deficit", 2026) == "-42"
    assert _row_display(tables, "centr", "flow_total", 2026) == "4"
    assert _row_display(tables, "centr", "surplus_deficit_with_flow", 2026) == "-38"


def test_yug_sibir_vostok_and_kaliningrad_formulas():
    years = [2026]
    tables = build_power_balance_tables(
        years,
        inputs={
            "yug": {
                "flow_out": {2026: -1090},
            },
            "sibir": {
                "flow_in": {2026: 240},
                "flow_out": {2026: -38},
            },
            "2-sz-ees-vostok": {
                "flow_in": {2026: 38},
                "flow_out": {2026: -240},
            },
            "kaliningradskaya-sz-ees": {
                "demand_max": {2026: 100},
                "installed_tes": {2026: 500},
            },
        },
    )
    assert _row_display(tables, "yug", "flow_out", 2026) == "-1 090"
    assert _row_display(tables, "sibir", "flow_in", 2026) == "240"
    assert _row_display(tables, "sibir", "flow_out", 2026) == "-38"
    assert _row_display(tables, "2-sz-ees-vostok", "flow_in", 2026) == "38"
    assert _row_display(tables, "2-sz-ees-vostok", "flow_out", 2026) == "-240"
    assert _row_display(tables, "kaliningradskaya-sz-ees", "coverage_total", 2026) == "500"
    assert _row_display(tables, "kaliningradskaya-sz-ees", "surplus_deficit", 2026) == "175"
    assert _row_display(tables, "kaliningradskaya-sz-ees", "surplus_deficit_second_unit", 2026) == "-50"
    assert KALININGRAD_LARGEST_UNIT_MW == 225


def test_ees_and_sz1_cross_sheet_formulas():
    years = [2026]
    tables = build_power_balance_tables(
        years,
        inputs={
            "severo-zapad": {"installed_aes": {2026: 10}},
            "centr": {"installed_aes": {2026: 20}},
            "srednyaya-volga": {"installed_aes": {2026: 4}},
            "yug": {
                "installed_aes": {2026: 5},
                "flow_out": {2026: -1090},
            },
            "ural": {"installed_aes": {2026: 6}},
            "sibir": {
                "installed_aes": {2026: 7},
                "flow_in": {2026: 240},
                "flow_out": {2026: -38},
            },
            "2-sz-ees-vostok": {"installed_aes": {2026: 8}},
            "kaliningradskaya-sz-ees": {"installed_aes": {2026: 3}},
        },
    )
    assert _row_display(tables, "ees-rossii", "installed_aes", 2026) == "60"
    # 1-я СЗ: 10+20+4+5+6+7 − 3 = 49 (без Востока)
    assert _row_display(tables, "1-sz-ees", "installed_aes", 2026) == "49"
    sz1_by_key = {row["key"]: row for row in tables["1-sz-ees"]["rows"]}
    assert "flow_out_vostok" not in sz1_by_key
    assert "flow_out_south" not in sz1_by_key
    assert sz1_by_key["flow_in"].get("formula") is None
    assert sz1_by_key["flow_out"].get("formula") is None
    ees_aes = next(row for row in tables["ees-rossii"]["rows"] if row["key"] == "installed_aes")
    assert "Северо-Запад" in ees_aes["formula_tooltip"]
    assert "2-я СЗ ЕЭС" in ees_aes["formula_tooltip"]


def test_sheets_use_refdata_names_and_keep_group_order():
    est = [
        SimpleNamespace(id=1, name="ЕЭС России"),
        SimpleNamespace(id=0, name="не указано"),
    ]
    ues = [
        SimpleNamespace(id=11, name="ОЭС Центра", id_energy_system_type=1),
        SimpleNamespace(id=12, name="ОЭС Востока", id_energy_system_type=1),
        SimpleNamespace(id=13, name="ОЭС Сибири", id_energy_system_type=1),
        SimpleNamespace(id=14, name="Новые территории", id_energy_system_type=1),
        SimpleNamespace(id=15, name="ТИТЭС Востока", id_energy_system_type=2),
        SimpleNamespace(id=0, name="не указано", id_energy_system_type=None),
    ]
    sa = [
        SimpleNamespace(id=21, name="Первая синхронная зона"),
        SimpleNamespace(id=22, name="Вторая синхронная зона"),
        SimpleNamespace(id=23, name="Синхронная зона Калининградской области"),
    ]
    with patch(
        "app.energy_balance.services.power_balance_page_services.get_energy_system_type_list_full",
        return_value=est,
    ), patch(
        "app.energy_balance.services.power_balance_page_services.get_union_energy_system_list_full",
        return_value=ues,
    ), patch(
        "app.energy_balance.services.power_balance_page_services.get_synchronous_area_list_full",
        return_value=sa,
    ):
        sheets = get_power_balance_sheets()
    names = [sheet["sheet_name"] for sheet in sheets]
    assert names == [
        "ЕЭС России",
        "Первая синхронная зона",
        "Вторая синхронная зона",
        "Синхронная зона Калининградской области",
        "ОЭС Центра",
        "ОЭС Сибири",
        "ТИТЭС Востока",
    ]
    assert "ОЭС Востока" not in names
    assert "Новые территории" not in names
    by_slug = {sheet["slug"]: sheet for sheet in sheets}
    assert by_slug["ees-rossii"]["group"] == GROUP_EES
    assert by_slug["1-sz-ees"]["layout"] == "sz1"
    assert by_slug["2-sz-ees-vostok"]["layout"] == "oes_vostok"
    assert by_slug["kaliningradskaya-sz-ees"]["layout"] == "kaliningrad"
    assert by_slug["centr"]["layout"] == "oes_standard"
    assert "vostok" not in by_slug
    assert by_slug["sibir"]["layout"] == "oes_sibir"
    assert "2-sz-ees-vostok" in by_slug["ees-rossii"]["source_slugs"]
    assert "vostok" not in by_slug["ees-rossii"]["source_slugs"]
    assert "centr" in by_slug["1-sz-ees"]["source_slugs"]
    assert "sibir" in by_slug["1-sz-ees"]["source_slugs"]
    assert "vostok" not in by_slug["1-sz-ees"]["source_slugs"]
    assert "2-sz-ees-vostok" not in by_slug["1-sz-ees"]["source_slugs"]


def test_sz_layout_keeps_first_and_second_after_name_tweak():
    from app.energy_balance.services.power_balance_page_services import _sz_layout_and_slug

    assert _sz_layout_and_slug("2-ая СЗ", 22) == ("oes_vostok", "2-sz-ees-vostok")
    assert _sz_layout_and_slug("1-ая синхронная зона", 21) == ("sz1", "1-sz-ees")
    assert _sz_layout_and_slug("СЗ Востока", 22, number="2") == ("oes_vostok", "2-sz-ees-vostok")
    assert _sz_layout_and_slug("СЗ", 21, name_full="Первая синхронная зона") == ("sz1", "1-sz-ees")
    assert _sz_layout_and_slug("Калининградская СЗ", 23) == (
        "kaliningrad",
        "kaliningradskaya-sz-ees",
    )


def test_sheets_keep_sz_layout_when_sa_name_tweaked():
    est = [SimpleNamespace(id=1, name="ЕЭС России")]
    ues = [
        SimpleNamespace(id=11, name="ОЭС Центра", id_energy_system_type=1),
        SimpleNamespace(id=12, name="ОЭС Востока", id_energy_system_type=1),
        SimpleNamespace(id=13, name="ОЭС Сибири", id_energy_system_type=1),
    ]
    sa = [
        SimpleNamespace(id=21, name="1-ая СЗ", name_full="Первая синхронная зона", number="1"),
        SimpleNamespace(id=22, name="2-ая СЗ", name_full="Вторая синхронная зона", number="2"),
        SimpleNamespace(id=23, name="Синхронная зона Калининградской области"),
    ]
    with patch(
        "app.energy_balance.services.power_balance_page_services.get_energy_system_type_list_full",
        return_value=est,
    ), patch(
        "app.energy_balance.services.power_balance_page_services.get_union_energy_system_list_full",
        return_value=ues,
    ), patch(
        "app.energy_balance.services.power_balance_page_services.get_synchronous_area_list_full",
        return_value=sa,
    ):
        sheets = get_power_balance_sheets()
    names = [sheet["sheet_name"] for sheet in sheets]
    by_slug = {sheet["slug"]: sheet for sheet in sheets}
    assert names == [
        "ЕЭС России",
        "1-ая СЗ",
        "2-ая СЗ",
        "Синхронная зона Калининградской области",
        "ОЭС Центра",
        "ОЭС Сибири",
    ]
    assert "ОЭС Востока" not in names
    assert "2-я СЗ ЕЭС (ОЭС Востока)" not in names
    assert "Сибирь" not in names
    assert by_slug["1-sz-ees"]["layout"] == "sz1"
    assert by_slug["2-sz-ees-vostok"]["layout"] == "oes_vostok"
    assert by_slug["kaliningradskaya-sz-ees"]["layout"] == "kaliningrad"
    assert "2-sz-ees-vostok" in by_slug["ees-rossii"]["source_slugs"]


def test_broken_sa_row_does_not_switch_to_fallback_catalog():
    class _ExpiredSa:
        @property
        def id(self):
            raise RuntimeError("detached")

    est = [SimpleNamespace(id=1, name="ЕЭС России")]
    ues = [
        SimpleNamespace(id=11, name="ОЭС Центра", id_energy_system_type=1),
        SimpleNamespace(id=13, name="ОЭС Сибири", id_energy_system_type=1),
    ]
    sa = [
        _ExpiredSa(),
        SimpleNamespace(id=21, name="Первая синхронная зона"),
        SimpleNamespace(id=22, name="Вторая синхронная зона"),
    ]
    with patch(
        "app.energy_balance.services.power_balance_page_services.get_energy_system_type_list_full",
        return_value=est,
    ), patch(
        "app.energy_balance.services.power_balance_page_services.get_union_energy_system_list_full",
        return_value=ues,
    ), patch(
        "app.energy_balance.services.power_balance_page_services.get_synchronous_area_list_full",
        return_value=sa,
    ):
        sheets = get_power_balance_sheets()
    names = [sheet["sheet_name"] for sheet in sheets]
    assert "ОЭС Сибири" in names
    assert "ОЭС Центра" in names
    assert "Сибирь" not in names
    assert "Центр" not in names
    assert "2-я СЗ ЕЭС (ОЭС Востока)" not in names
    assert "Первая синхронная зона" in names
    assert "Вторая синхронная зона" in names


def test_persistable_slug_accepts_dynamic_sz_id():
    assert is_persistable_power_balance_slug("sz-112") is True
    assert is_persistable_power_balance_slug("oes-15") is True
    assert is_persistable_power_balance_slug("sibir") is True
    assert is_persistable_power_balance_slug("nope") is False
    assert is_persistable_power_balance_slug("") is False


def test_get_sheet_sz_id_when_catalog_falls_back():
    sa = SimpleNamespace(id=112, name="Синхронная зона X", name_full=None, number=None)
    with patch(
        "app.energy_balance.services.power_balance_page_services._sheets_from_refdata",
        return_value=None,
    ), patch(
        "app.energy_balance.services.power_balance_page_services.get_synchronous_area_list_full",
        return_value=[sa],
    ):
        sheet = get_power_balance_sheet("sz-112")
        names = [item["sheet_name"] for item in get_power_balance_sheets()]
    assert "Сибирь" in names
    assert sheet is not None
    assert sheet["slug"] == "sz-112"
    assert sheet["sheet_name"] == "Синхронная зона X"
    assert sheet["group"] == GROUP_SZ
    assert sheet["territory"] == {"kind": "sa", "id": 112, "name": "Синхронная зона X"}


def test_table_context_for_dynamic_sz_slug():
    sa = SimpleNamespace(id=112, name="Синхронная зона X", name_full=None, number=None)
    with patch(
        "app.energy_balance.services.power_balance_page_services._sheets_from_refdata",
        return_value=None,
    ), patch(
        "app.energy_balance.services.power_balance_page_services.get_synchronous_area_list_full",
        return_value=[sa],
    ), patch(
        "app.energy_balance.services.power_balance_page_services.get_sipr_start_year",
        return_value=2026,
    ), patch(
        "app.energy_balance.services.power_balance_page_services.get_sipr_end_year",
        return_value=2027,
    ), patch(
        "app.energy_balance.services.power_balance_page_services.get_year_feature_dict",
        return_value={2026: "Отчет", 2027: "План"},
    ):
        context = build_power_balance_table_context("sz-112")
    assert context is not None
    assert context["sheet"]["slug"] == "sz-112"
    assert context["page_title"] == "Баланс мощности Синхронная зона X"
    export = next(row for row in context["rows"] if row["key"] == "export")
    assert export["editable_values"] is True


def test_station_list_query_uses_oes_sz_ees_and_years():
    est = [SimpleNamespace(id=1, name="ЕЭС России")]
    ues = [
        SimpleNamespace(id=11, name="ОЭС Центра", id_energy_system_type=1),
        SimpleNamespace(id=12, name="ОЭС Востока", id_energy_system_type=1),
        SimpleNamespace(id=13, name="ОЭС Сибири", id_energy_system_type=1),
    ]
    sa = [
        SimpleNamespace(id=21, name="Первая синхронная зона"),
        SimpleNamespace(id=22, name="Вторая синхронная зона"),
        SimpleNamespace(id=23, name="Синхронная зона Калининградской области"),
    ]
    with patch(
        "app.energy_balance.services.power_balance_page_services.get_energy_system_type_list_full",
        return_value=est,
    ), patch(
        "app.energy_balance.services.power_balance_page_services.get_union_energy_system_list_full",
        return_value=ues,
    ), patch(
        "app.energy_balance.services.power_balance_page_services.get_synchronous_area_list_full",
        return_value=sa,
    ), patch(
        "app.energy_balance.services.power_balance_page_services._regional_district_ids_for_sa",
        return_value=[77],
    ):
        sheets = get_power_balance_sheets()
        by_slug = {sheet["slug"]: sheet for sheet in sheets}
        ees_q = power_balance_station_list_query(by_slug["ees-rossii"], sheets, 2026, 2031)
        oes_q = power_balance_station_list_query(by_slug["centr"], sheets, 2026, 2031)
        sz1_q = power_balance_station_list_query(by_slug["1-sz-ees"], sheets, 2026, 2031)
        sz2_q = power_balance_station_list_query(by_slug["2-sz-ees-vostok"], sheets, 2026, 2031)
        kal_q = power_balance_station_list_query(
            by_slug["kaliningradskaya-sz-ees"], sheets, 2028, 2029
        )

    assert ees_q["energy_system_type_filter"] == 1
    assert ees_q["start_year"] == 2026
    assert ees_q["end_year"] == 2031
    assert oes_q["union_energy_system_filter"] == 11
    assert 11 in sz1_q["union_energy_system_filter"]
    assert 13 in sz1_q["union_energy_system_filter"]
    assert 12 not in sz1_q["union_energy_system_filter"]
    assert sz2_q["union_energy_system_filter"] == 12
    assert kal_q["regional_district_filter"] == [77]
    assert kal_q["start_year"] == 2028
    url = build_power_balance_station_list_url(oes_q)
    assert "union_energy_system_filter=11" in url
    assert "start_year=2026" in url
    assert "end_year=2031" in url


def test_custom_flow_rows_sum_into_parent_and_flow_total():
    tables = build_power_balance_tables(
        [2026],
        inputs={"centr": {"demand_max": {2026: 0}}},
        custom_flows={
            "centr": [
                {
                    "id": 1,
                    "direction": "flow_in",
                    "label": "из Казахстана",
                    "sort_order": 0,
                    "values": {2026: 10},
                },
                {
                    "id": 2,
                    "direction": "flow_out",
                    "label": "в Белоруссию",
                    "sort_order": 0,
                    "values": {2026: -4},
                },
            ]
        },
    )
    keys = [row["key"] for row in tables["centr"]["rows"]]
    assert "flow_in_custom_1" in keys
    assert "flow_out_custom_2" in keys
    assert keys.index("flow_in") < keys.index("flow_in_custom_1") < keys.index("flow_out")
    assert keys.index("flow_out") < keys.index("flow_out_custom_2")
    flow_in = next(row for row in tables["centr"]["rows"] if row["key"] == "flow_in")
    assert flow_in["can_add_custom_flow"] is True
    assert any(
        term.get("row_key") == "flow_in_custom_1" for term in flow_in["formula"]["terms"]
    )
    assert _row_display(tables, "centr", "flow_in_custom_1", 2026) == "10"
    assert _row_display(tables, "centr", "flow_in", 2026) == "10"
    assert _row_display(tables, "centr", "flow_out", 2026) == "-4"
    assert _row_display(tables, "centr", "flow_total", 2026) == "6"


def test_custom_flow_adds_to_yug_flow_out():
    tables = build_power_balance_tables(
        [2026],
        inputs={"yug": {}},
        custom_flows={
            "yug": [
                {
                    "id": 9,
                    "direction": "flow_out",
                    "label": "прочее",
                    "sort_order": 0,
                    "values": {2026: -10},
                }
            ]
        },
    )
    keys = [row["key"] for row in tables["yug"]["rows"]]
    assert "flow_out_lnr_dnr" not in keys
    assert "flow_out_kherson_zaporozhye" not in keys
    assert keys.index("flow_out") < keys.index("flow_out_custom_9")
    assert _row_display(tables, "yug", "flow_out", 2026) == "-10"


def test_without_custom_rows_flow_in_stays_leaf_input():
    tables = build_power_balance_tables(
        [2026],
        inputs={"centr": {"flow_in": {2026: 7}, "flow_out": {2026: -3}}},
        custom_flows={},
    )
    flow_in = next(row for row in tables["centr"]["rows"] if row["key"] == "flow_in")
    assert flow_in.get("formula") is None
    assert flow_in["can_add_custom_flow"] is True
    assert _row_display(tables, "centr", "flow_in", 2026) == "7"
    assert _row_display(tables, "centr", "flow_total", 2026) == "4"


def test_custom_flow_row_key_format():
    assert custom_flow_row_key("flow_in", 12) == "flow_in_custom_12"
    assert custom_flow_row_key("flow_out", 3) == "flow_out_custom_3"


def test_sibir_two_level_custom_group_sums_children():
    tables = build_power_balance_tables(
        [2026],
        inputs={"sibir": {}},
        custom_flows={
            "sibir": [
                {
                    "id": 1,
                    "direction": "flow_in",
                    "parent_key": "flow_in",
                    "label": "из ОЭС Востока",
                    "sort_order": 0,
                    "values": {},
                },
                {
                    "id": 2,
                    "direction": "flow_in",
                    "parent_key": "flow_in_custom_1",
                    "label": "питание Удоканского ГОКа",
                    "sort_order": 0,
                    "values": {2026: 176},
                },
                {
                    "id": 3,
                    "direction": "flow_in",
                    "parent_key": "flow_in_custom_1",
                    "label": "питание тяговых ПС АО «РЖД»",
                    "sort_order": 1,
                    "values": {2026: 64},
                },
            ]
        },
    )
    keys = [row["key"] for row in tables["sibir"]["rows"]]
    assert "flow_in_vostok" not in keys
    assert keys.index("flow_in") < keys.index("flow_in_custom_1") < keys.index("flow_in_custom_2")
    assert keys.index("flow_in_custom_2") < keys.index("flow_in_custom_3") < keys.index("flow_out")
    group = next(row for row in tables["sibir"]["rows"] if row["key"] == "flow_in_custom_1")
    child = next(row for row in tables["sibir"]["rows"] if row["key"] == "flow_in_custom_2")
    assert group["indent"] == 2
    assert group["italic"] is False
    assert group["can_add_custom_flow"] is True
    assert group["editable_values"] is False
    assert child["indent"] == 3
    assert child["italic"] is True
    assert child["editable_values"] is True
    assert child["can_add_custom_flow"] is False
    assert _row_display(tables, "sibir", "flow_in_custom_1", 2026) == "240"
    assert _row_display(tables, "sibir", "flow_in", 2026) == "240"


def test_two_level_custom_group_aggregates_into_parent():
    tables = build_power_balance_tables(
        [2026],
        inputs={},
        custom_flows={
            "centr": [
                {
                    "id": 1,
                    "direction": "flow_in",
                    "parent_key": "flow_in",
                    "label": "из Казахстана",
                    "sort_order": 0,
                    "values": {},
                },
                {
                    "id": 2,
                    "direction": "flow_in",
                    "parent_key": "flow_in_custom_1",
                    "label": "Северный Казахстан",
                    "sort_order": 0,
                    "values": {2026: 8},
                },
            ]
        },
    )
    group = next(row for row in tables["centr"]["rows"] if row["key"] == "flow_in_custom_1")
    child = next(row for row in tables["centr"]["rows"] if row["key"] == "flow_in_custom_2")
    assert group["indent"] == 2
    assert group["can_add_custom_flow"] is True
    assert group["editable_values"] is False
    assert child["indent"] == 3
    assert child["editable_values"] is True
    assert child["can_add_custom_flow"] is False
    keys = [row["key"] for row in tables["centr"]["rows"]]
    assert keys.index("flow_in") < keys.index("flow_in_custom_1") < keys.index("flow_in_custom_2")
    assert _row_display(tables, "centr", "flow_in_custom_1", 2026) == "8"
    assert _row_display(tables, "centr", "flow_in", 2026) == "8"


def test_legacy_vostok_layout_rows_become_deletable_custom_groups():
    tables = build_power_balance_tables(
        [2026],
        inputs={"2-sz-ees-vostok": {}},
        custom_flows={
            "2-sz-ees-vostok": [
                {
                    "id": 11,
                    "direction": "flow_in",
                    "parent_key": "flow_in_peleduy",
                    "label": "питание ПС 220 кВ Пеледуй и НПС-10, Чаяндинский НГКМ, НПС-11 от ОЭС Сибири",
                    "sort_order": 0,
                    "values": {2026: 38},
                },
                {
                    "id": 12,
                    "direction": "flow_out",
                    "parent_key": "flow_out_udokan",
                    "label": "питание Удоканского ГОКа",
                    "sort_order": 0,
                    "values": {2026: -176},
                },
                {
                    "id": 13,
                    "direction": "flow_out",
                    "parent_key": "flow_out_rzd",
                    "label": 'питание тяговых ПС АО "РЖД"',
                    "sort_order": 1,
                    "values": {2026: -64},
                },
                {
                    "id": 99,
                    "direction": "flow_in",
                    "parent_key": VOSTOK_LAYOUT_SEED_PARENT,
                    "label": "",
                    "sort_order": -1,
                    "values": {},
                },
            ]
        },
    )
    rows = tables["2-sz-ees-vostok"]["rows"]
    by_key = {row["key"]: row for row in rows}
    assert "flow_in_peleduy" not in by_key
    assert "flow_in_custom_99" not in by_key
    peleduy = by_key["flow_in_custom_11"]
    udokan = by_key["flow_out_custom_12"]
    assert peleduy["is_custom"] is True
    assert peleduy["indent"] == 2
    assert peleduy["can_add_custom_flow"] is True
    assert peleduy["custom_parent_key"] == "flow_in"
    assert udokan["is_custom"] is True
    assert udokan["custom_parent_key"] == "flow_out"
    assert _row_display(tables, "2-sz-ees-vostok", "flow_in", 2026) == "38"
    assert _row_display(tables, "2-sz-ees-vostok", "flow_out", 2026) == "-240"


def test_sz1_has_no_hardcoded_transfer_children():
    keys = {row["key"] for row in build_power_balance_rows("sz1")}
    assert "flow_out_vostok" not in keys
    assert "flow_out_south" not in keys
    tables = build_power_balance_tables([2026], inputs={}, custom_flows={})
    by_key = {row["key"]: row for row in tables["1-sz-ees"]["rows"]}
    assert by_key["flow_in"]["can_add_custom_flow"] is True
    assert by_key["flow_out"]["can_add_custom_flow"] is True


def test_sz1_and_ees_accumulate_member_oes_custom_flows():
    tables = build_power_balance_tables(
        [2026],
        inputs={},
        custom_flows={
            "centr": [
                {
                    "id": 1,
                    "direction": "flow_in",
                    "parent_key": "flow_in",
                    "label": "из Казахстана",
                    "sort_order": 0,
                    "values": {2026: 10},
                }
            ],
            "sibir": [
                {
                    "id": 2,
                    "direction": "flow_out",
                    "parent_key": "flow_out",
                    "label": "в ОЭС Востока",
                    "sort_order": 0,
                    "values": {2026: -38},
                }
            ],
            "yug": [
                {
                    "id": 3,
                    "direction": "flow_out",
                    "parent_key": "flow_out",
                    "label": "на юг",
                    "sort_order": 0,
                    "values": {2026: -100},
                }
            ],
            "2-sz-ees-vostok": [
                {
                    "id": 4,
                    "direction": "flow_in",
                    "parent_key": "flow_in",
                    "label": "Пеледуй",
                    "sort_order": 0,
                    "values": {2026: 5},
                }
            ],
        },
    )
    sz1 = {row["key"]: row for row in tables["1-sz-ees"]["rows"]}
    assert sz1["centr__flow_in_custom_1"]["is_custom"] is True
    assert sz1["centr__flow_in_custom_1"]["custom_origin_slug"] == "centr"
    assert sz1["centr__flow_in_custom_1"]["label"] == "из Казахстана"
    assert "2-sz-ees-vostok__flow_in_custom_4" not in sz1
    assert _row_display(tables, "1-sz-ees", "flow_in", 2026) == "10"
    assert _row_display(tables, "1-sz-ees", "flow_out", 2026) == "-138"
    ees = {row["key"]: row for row in tables["ees-rossii"]["rows"]}
    assert ees["centr__flow_in_custom_1"]["custom_origin_slug"] == "centr"
    assert ees["2-sz-ees-vostok__flow_in_custom_4"]["label"] == "Пеледуй"
    assert _row_display(tables, "ees-rossii", "flow_in", 2026) == "15"
    assert _row_display(tables, "ees-rossii", "flow_out", 2026) == "-138"


def test_export_row_is_editable_on_aggregated_layouts():
    for layout in ("ees_rossii", "sz1"):
        rows = build_power_balance_rows(layout, source_slugs=("centr", "yug"))
        export = next(row for row in rows if row["key"] == "export")
        assert export["editable_values"] is True
        assert not export.get("formula")


def test_export_inputs_fill_row_and_demand_total(monkeypatch):
    monkeypatch.setattr(
        "app.energy_balance.services.power_balance_page_services.load_power_balance_export_inputs",
        lambda years, sheets=None: {"centr": {"export": {2026: 15}}},
    )
    tables = build_power_balance_tables([2026])
    export = next(row for row in tables["centr"]["rows"] if row["key"] == "export")
    assert export["editable_values"] is True
    assert _row_display(tables, "centr", "export", 2026) == "15"
    assert _row_display(tables, "centr", "demand_total", 2026) == "15"

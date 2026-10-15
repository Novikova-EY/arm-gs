# -*- coding: utf-8 -*-
"""Юнит-тесты каркаса страниц расчета балансов электрической энергии."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from app.energy_balance.services import ee_balance_page_services as balance_page_services
from app.energy_balance.services.ee_balance_page_services import (
    EE_BALANCE_TITLE_PREFIX,
    EE_BALANCE_UNIT,
    HYDRO_YEAR_AVERAGE,
    HYDRO_YEAR_LOW,
    build_ee_balance_rows,
    build_ee_balance_table_context,
    build_ee_balance_tables,
    format_ee_balance_browser_title,
    format_ee_balance_page_title,
    get_ee_balance_sheet,
    get_ee_balance_sheets,
    resolve_ee_balance_hydro_year,
    sheet_has_ges_or_gaes_capacity,
    URAL_WITHOUT_TYUMEN_SLUG,
    _append_ural_without_tyumen_table,
    _ee_transfer_filters,
    _overlay_ural_without_tyumen_manual_generation,
    _severo_zapad_region_sheets,
    _severo_zapad_subtab_sheets,
    _append_severo_zapad_center_table,
    SEVERO_ZAPAD_CENTER_SLUG,
    _append_european_ees_table,
    EUROPEAN_EES_SLUG,
    EUROPEAN_EES_SOURCE_SLUGS,
    EUROPEAN_EES_WITHOUT_SOUTH_URAL_SLUG,
    EUROPEAN_EES_WITHOUT_SOUTH_URAL_SOURCE_SLUGS,
    EUROPEAN_EES_WITHOUT_SOUTH_URAL_NAME,
    EES_RUSSIA_WITH_TITES_SLUG,
    EES_RUSSIA_WITH_TITES_NAME,
    SYNCHRONOUS_ZONES_SLUG,
    SYNCHRONOUS_ZONES_NAME,
    _european_ees_subtab_sheets,
    _ees_rossii_with_tites_source_slugs,
    _ee_balance_navigation_sheets,
    group_ee_balance_sheets,
    _ural_subtab_sheets,
)
from app.energy_balance.services.ee_balance_generation_services import (
    hydro_year_for_balance_sheet,
)
from app.energy_balance.services.power_balance_page_services import (
    GROUP_EES,
    GROUP_OES,
    GROUP_RES,
    GROUP_SZ,
    POWER_BALANCE_SHEETS,
    group_power_balance_sheets,
)


@pytest.fixture(autouse=True)
def _stable_station_types_and_no_db_load(monkeypatch):
    monkeypatch.setattr(
        "app.energy_balance.services.power_balance_installed_capacity_services.get_station_type_list_full",
        lambda: [],
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.load_ee_balance_generation_inputs",
        lambda years, sheets=None, hydro_year=None: {},
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.load_ee_balance_consumption_inputs",
        lambda years, sheets=None: {},
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.load_ee_balance_gaes_charge_inputs",
        lambda years, sheets=None: {},
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.load_ee_balance_custom_flows",
        lambda sheets=None: {},
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.load_ee_balance_export_inputs",
        lambda years, sheets=None: {},
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.load_power_balance_installed_capacity_inputs",
        lambda years, sheets=None: {},
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.attach_balance_sheet_notes",
        lambda tables, kind: None,
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.overlay_tes_forecast_generation_inputs",
        lambda inputs, sheets=None, years=None: inputs or {},
    )


def test_ee_balance_sheets_reuse_power_catalog_with_energy_titles():
    sheets = get_ee_balance_sheets()
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
    groups = group_power_balance_sheets(sheets)
    assert [item["group"] for item in groups] == [GROUP_EES, GROUP_SZ, GROUP_OES]
    for sheet in sheets:
        assert sheet["title"] == f"Баланс электрической энергии {sheet['sheet_name']}"
        assert sheet["unit"] == EE_BALANCE_UNIT


def test_get_ee_balance_sheet_unknown_returns_none():
    assert get_ee_balance_sheet("unknown") is None
    assert get_ee_balance_sheet("sibir")["table_number"] == 10


def test_vostok_tab_follows_sibir_without_adding_a_calculation_sheet():
    sheets = get_ee_balance_sheets()
    original_slugs = [sheet["slug"] for sheet in sheets]
    groups = balance_page_services.group_ee_balance_sheets(sheets)
    oes = next(group["sheets"] for group in groups if group["group"] == GROUP_OES)
    slugs = [sheet["slug"] for sheet in oes]
    assert slugs[slugs.index("sibir") + 1] == "vostok"
    assert oes[slugs.index("vostok")]["sheet_name"] == "ОЭС Востока"
    assert [sheet["slug"] for sheet in sheets] == original_slugs
    assert "vostok" not in original_slugs
    power_groups = group_power_balance_sheets(sheets)
    power_oes = next(group["sheets"] for group in power_groups if group["group"] == GROUP_OES)
    power_slugs = [sheet["slug"] for sheet in power_oes]
    assert power_slugs[power_slugs.index("sibir") + 1] == "vostok"


def test_vostok_tab_is_available_without_siberia_sheet():
    sheets = [
        {"slug": "ees-rossii", "sheet_name": "ЕЭС России", "group": GROUP_EES},
        {
            "slug": "2-sz-ees-vostok",
            "sheet_name": "Вторая синхронная зона",
            "group": GROUP_SZ,
        },
    ]

    groups = balance_page_services.group_ee_balance_sheets(sheets)

    oes = next(group["sheets"] for group in groups if group["group"] == GROUP_OES)
    assert oes == [
        {"slug": "vostok", "sheet_name": "ОЭС Востока", "group": GROUP_OES}
    ]


def test_vostok_context_shares_second_zone_data_and_editing(monkeypatch):
    monkeypatch.setattr(
        balance_page_services, "get_ee_balance_year_columns", lambda *args: [2026, 2027]
    )
    monkeypatch.setattr(
        balance_page_services, "get_ee_balance_year_features",
        lambda: {2026: "План", 2027: "План"},
    )
    monkeypatch.setattr(
        balance_page_services, "get_ee_balance_filter_year_list", lambda: [2026, 2027]
    )
    monkeypatch.setattr(
        balance_page_services, "load_ee_balance_consumption_inputs",
        lambda years, sheets=None: {
            "2-sz-ees-vostok": {"consumption": {2026: Decimal("123.4")}}
        },
    )
    monkeypatch.setattr(
        balance_page_services, "load_power_balance_installed_capacity_inputs",
        lambda years, sheets=None: {
            "2-sz-ees-vostok": {"installed_ges": {2026: Decimal("100")}}
        },
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_ves_ses_page_services._can_edit_ves_ses_energy",
        lambda: True,
    )
    second_zone = build_ee_balance_table_context("2-sz-ees-vostok", rounding_digits=1)
    vostok = build_ee_balance_table_context("vostok", rounding_digits=1)
    assert vostok is not None and second_zone is not None
    assert vostok["page_slug"] == "vostok"
    assert vostok["first_row_active_slug"] == "vostok"
    assert second_zone["first_row_active_slug"] == SYNCHRONOUS_ZONES_SLUG
    assert [
        item["slug"] for item in second_zone["synchronous_zone_subtab_sheets"]
    ] == ["1-sz-ees", "2-sz-ees-vostok", "kaliningradskaya-sz-ees"]
    assert vostok["page_title"] == (
        "Баланс электрической энергии ОЭС Востока (маловодный год)"
    )
    presentation_keys = {
        "page_slug",
        "first_row_active_slug",
        "synchronous_zone_subtab_sheets",
        "page_title",
        "browser_title",
    }
    assert {key: value for key, value in vostok.items() if key not in presentation_keys} == {
        key: value for key, value in second_zone.items() if key not in presentation_keys
    }
    consumption = next(row for row in vostok["rows"] if row["key"] == "consumption")
    assert consumption["year_values"][2026] == "123,4"
    assert vostok["sheet"]["slug"] == "2-sz-ees-vostok"
    assert vostok["can_edit"] is True


@pytest.mark.parametrize("sheet", list(POWER_BALANCE_SHEETS))
def test_each_layout_has_energy_rows_and_units(sheet):
    rows = build_ee_balance_rows(sheet["layout"])
    keys = [row["key"] for row in rows]
    assert keys
    assert len(keys) == len(set(keys))
    assert "consumption" in keys
    assert "gaes_charge" in keys
    assert keys[keys.index("consumption") + 1] == "gaes_charge"
    gaes_charge = next(row for row in rows if row["key"] == "gaes_charge")
    assert gaes_charge["label"] == "Заряд ГАЭС"
    assert gaes_charge["unit"] == EE_BALANCE_UNIT
    assert "generation_aes" in keys
    assert "generation_ses_ves" in keys
    assert "generation_ses" in keys
    assert "generation_ves" in keys
    assert "generation_total" in keys
    assert "flow_in" in keys
    assert "flow_out" in keys
    assert "installed_total" in keys
    assert "installed_aes" in keys
    assert "installed_ses_ves" in keys
    assert "installed_ses" in keys
    assert "installed_ves" in keys
    assert "chiim_total" in keys
    assert "chiim_aes" in keys
    assert "chiim_ses_ves" in keys
    assert "chiim_ses" in keys
    assert "chiim_ves" in keys
    installed_start = keys.index("installed_total")
    chiim_start = keys.index("chiim_total")
    assert keys[installed_start - 1] == "surplus_deficit_with_flow"
    assert chiim_start == keys.index("installed_ves") + 1
    assert keys.index("generation_ses") == keys.index("generation_ses_ves") + 1
    assert keys.index("generation_ves") == keys.index("generation_ses") + 1
    assert keys.index("chiim_ses") == keys.index("chiim_ses_ves") + 1
    assert keys.index("chiim_ves") == keys.index("chiim_ses") + 1
    gen_ses_ves = next(row for row in rows if row["key"] == "generation_ses_ves")
    gen_ses = next(row for row in rows if row["key"] == "generation_ses")
    assert gen_ses_ves.get("collapsible") is True
    assert gen_ses.get("is_group_child") is True
    assert gen_ses.get("parent_group_key") == "generation_ses_ves"
    assert gen_ses["label"] == "СЭС"
    assert all(k.startswith("installed_") for k in keys[installed_start:chiim_start])
    assert all(k.startswith("chiim_") for k in keys[chiim_start:])
    energy_rows = [
        row
        for row in rows
        if not str(row["key"]).startswith("installed_")
        and not str(row["key"]).startswith("chiim_")
    ]
    capacity_rows = [row for row in rows if str(row["key"]).startswith("installed_")]
    chiim_rows = [row for row in rows if str(row["key"]).startswith("chiim_")]
    assert all(row["unit"] == EE_BALANCE_UNIT for row in energy_rows)
    assert all(row["unit"] == "МВт" for row in capacity_rows)
    assert all(row["unit"] == "ч." for row in chiim_rows)
    assert "demand_max" not in keys
    installed_total = next(row for row in rows if row["key"] == "installed_total")
    chiim_total = next(row for row in rows if row["key"] == "chiim_total")
    chiim_aes = next(row for row in rows if row["key"] == "chiim_aes")
    assert installed_total["kind"] == "total"
    assert chiim_total["kind"] == "total"
    assert chiim_total["label"] == "ЧЧИУМ"
    assert chiim_aes["rounding_digits"] == -1
    assert "Выработка электрической энергии АЭС" in (chiim_aes.get("formula") or {}).get("tooltip", "")
    assert "Установленная мощность АЭС" in (chiim_aes.get("formula") or {}).get("tooltip", "")


def test_unknown_layout_raises():
    with pytest.raises(KeyError):
        build_ee_balance_rows("missing")


def test_balance_import_export_rows_use_saved_oes_values(monkeypatch):
    received_kwargs = {}
    monkeypatch.setattr(
        balance_page_services,
        "power_balance_station_list_query",
        lambda *args, **kwargs: {"union_energy_system_filter": 4},
    )

    def load_import_export_page(**kwargs):
        received_kwargs.update(kwargs)
        return {
            "hierarchy": [
                {
                    "ues_id": 4,
                    "rows": [
                        {
                            "direction": "import",
                            "country_id": 9,
                            "country_name": "Беларусь",
                            "periods": {2030: Decimal("12.5")},
                        },
                        {
                            "direction": "export",
                            "country_id": 10,
                            "country_name": "Казахстан",
                            "periods": {2030: Decimal("-3.5")},
                        },
                    ]
                }
            ]
        }

    monkeypatch.setattr(
        balance_page_services,
        "get_ee_import_export_page_data",
        load_import_export_page,
    )
    sheet = {"slug": "sibir", "layout": "oes_sibir"}

    rows, inputs = balance_page_services._ee_import_export_rows_for_sheet(
        sheet, [sheet], [2030], 1
    )

    assert received_kwargs.get("saved_values_only", False) is False
    assert received_kwargs["filters"]["union_energy_system_filter"] == [4]
    assert [row["key"] for row in rows] == [
        "ee_export_total",
        "ee_export_country_10",
        "ee_import_total",
        "ee_import_country_9",
    ]
    assert inputs == {
        "ee_import_total": {2030: Decimal("12.5")},
        "ee_import_country_9": {2030: Decimal("12.5")},
        "ee_export_total": {2030: Decimal("3.5")},
        "ee_export_country_10": {2030: Decimal("3.5")},
    }


def test_balance_transfer_rows_are_loaded_from_receive_transfer_oes_page(monkeypatch):
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.get_ee_import_export_page_data",
        lambda **kwargs: {"hierarchy": []},
    )
    monkeypatch.setattr(
        balance_page_services,
        "get_ee_receive_transfer_oes_page_data",
        lambda **kwargs: {
            "hierarchy": [
                {
                    "ues_id": 4,
                    "ues_name": "ОЭС Сибири",
                    "rows": [
                        {
                            "direction": "receive",
                            "country_id": 8,
                            "country_name": "ОЭС Востока",
                            "periods": {2026: Decimal("12.5")},
                        },
                        {
                            "direction": "transfer",
                            "country_id": 9,
                            "country_name": "ОЭС Урала",
                            "periods": {2026: Decimal("-3.5")},
                        },
                    ],
                }
            ]
        },
    )
    sheet = {
        "slug": "sibir",
        "sheet_name": "Сибирь",
        "layout": "oes_sibir",
        "territory": {"kind": "ues", "id": 4, "name": "ОЭС Сибири"},
    }

    tables = build_ee_balance_tables(
        [2026], inputs={}, custom_flows={}, sheets=[sheet], rounding_digits=1
    )

    rows = {row["key"]: row for row in tables["sibir"]["rows"]}
    assert rows["flow_in_oes_4_8"]["label"] == "ОЭС Востока"
    assert rows["flow_out_oes_4_9"]["label"] == "ОЭС Урала"
    assert rows["flow_in"]["collapsible"] is True
    assert rows["flow_out"]["collapsible"] is True
    assert rows["flow_in_oes_4_8"]["indent"] == 2
    assert rows["flow_in_oes_4_8"]["parent_group_key"] == "flow_in"
    assert rows["flow_in_oes_4_8"]["is_group_child"] is True
    assert rows["flow_out_oes_4_9"]["parent_group_key"] == "flow_out"
    assert rows["flow_out_oes_4_9"]["is_group_child"] is True
    assert rows["flow_out_oes_4_9"]["year_values_raw"][2026] == Decimal("-3.5")
    assert rows["flow_in"]["year_values_raw"][2026] == Decimal("12.5")
    assert rows["flow_out"]["year_values_raw"][2026] == Decimal("-3.5")
    assert rows["flow_total"]["year_values_raw"][2026] == Decimal("9.0")


def test_severo_zapad_archangelsk_and_komi_keep_only_receive_transfer_rows(monkeypatch):
    years = [2026]
    sheets = [
        {
            "slug": slug,
            "sheet_name": label,
            "layout": "oes_standard",
            "group": GROUP_RES,
            "parent_slug": "severo-zapad",
            "territory": {"kind": "res", "id": res_id},
            "ee_balance_receive_transfer": enabled,
        }
        for slug, label, res_id, enabled in (
            ("res-2759", "ЭС Архангельской области", 2759, True),
            ("res-2775", "ЭС Калининградской области", 2775, False),
            ("res-2806", "ЭС Республики Коми", 2806, True),
        )
    ]
    received_filters = []
    monkeypatch.setattr(
        balance_page_services, "get_ee_balance_year_features", lambda: {}
    )
    monkeypatch.setattr(
        balance_page_services,
        "classify_ee_balance_generation_years",
        lambda *args: (years, []),
    )
    monkeypatch.setattr(
        balance_page_services, "mark_manual_plan_generation_rows", lambda *args: None
    )
    monkeypatch.setattr(
        balance_page_services,
        "_ee_import_export_rows_for_sheet",
        lambda *args: pytest.fail("region tabs must not gain import/export rows"),
    )

    def load_receive_transfer(sheet, all_sheets, selected_years, digits, plan_years):
        filters = balance_page_services._ee_transfer_filters(sheet, all_sheets, selected_years)
        received_filters.append((sheet["slug"], filters))
        return (
            [
                {
                    **balance_page_services._ee_row(
                        "flow_in_oes_410_413", "ОЭС Центра", indent=2
                    ),
                    "flow_section": "flow_in",
                    "row_key": "flow_in_oes_410_413",
                    "source_ues_id": 410,
                    "target_ues_id": 413,
                    "value_save_kind": "receive_transfer",
                },
                {
                    **balance_page_services._ee_row(
                        "flow_out_oes_410_414", "ОЭС Урала", indent=2
                    ),
                    "flow_section": "flow_out",
                    "row_key": "flow_out_oes_410_414",
                    "source_ues_id": 410,
                    "target_ues_id": 414,
                    "value_save_kind": "receive_transfer",
                },
            ],
            {
                "flow_in_oes_410_413": {2026: Decimal("12.5")},
                "flow_out_oes_410_414": {2026: Decimal("-3.5")},
            },
        )

    monkeypatch.setattr(
        balance_page_services,
        "_ee_receive_transfer_rows_for_sheet",
        load_receive_transfer,
    )
    tables = build_ee_balance_tables(
        years,
        inputs={},
        custom_flows={},
        sheets=sheets,
        rounding_digits=1,
    )

    assert [slug for slug, _filters in received_filters] == ["res-2759", "res-2806"]
    assert received_filters == [
        (
            "res-2759",
            {
                "start_year": 2026,
                "end_year": 2026,
                "regional_energy_system_filter": [2759],
            },
        ),
        (
            "res-2806",
            {
                "start_year": 2026,
                "end_year": 2026,
                "regional_energy_system_filter": [2806],
            },
        ),
    ]
    for slug in ("res-2759", "res-2806"):
        rows = {row["key"]: row for row in tables[slug]["rows"]}
        assert {"flow_in", "flow_out", "flow_in_oes_410_413", "flow_out_oes_410_414"} <= rows.keys()
        assert "ee_import" not in rows
        assert "ee_export" not in rows
        assert rows["flow_in"]["year_values_raw"][2026] == Decimal("12.5")
        assert rows["flow_out"]["year_values_raw"][2026] == Decimal("-3.5")
    komi_keys = {row["key"] for row in tables["res-2806"]["rows"]}
    assert "surplus_deficit_with_flow" in komi_keys
    kaliningrad_keys = {row["key"] for row in tables["res-2775"]["rows"]}
    assert not any(key.startswith("flow_") for key in kaliningrad_keys)


@pytest.mark.parametrize(
    "sheet, isolated",
    [
        ({"slug": "oes-15", "sheet_name": "ТИТЭС Востока"}, True),
        ({"slug": "oes-318", "sheet_name": "ТИТЭС Сибири"}, True),
        (
            {
                "slug": "eu-258",
                "sheet_name": "Центральный энергорайон Камчатского края",
                "group": "eu",
                "parent_slug": "oes-15",
            },
            True,
        ),
        (
            {
                "slug": "res-42",
                "sheet_name": "Дочерняя энергосистема ТИТЭС Востока",
                "group": "res",
                "parent_slug": "oes-15",
            },
            True,
        ),
        (
            {
                "slug": "kaliningradskaya-sz-ees",
                "sheet_name": "Калининградская СЗ ЕЭС",
                "layout": "kaliningrad",
            },
            True,
        ),
        ({"slug": "sibir", "sheet_name": "Сибирь"}, False),
        ({"slug": "vostok", "sheet_name": "Восток"}, False),
    ],
    ids=[
        "tites-east", "tites-siberia", "kamchatka", "east-child", "kaliningrad",
        "oes-siberia", "oes-east",
    ],
)
def test_balances_without_flows_omit_trade_and_flows_from_rows_and_totals(monkeypatch, sheet, isolated):
    years = [2018, 2031]
    sheet = {"layout": "oes_standard", **sheet}
    slug = sheet["slug"]
    monkeypatch.setattr(balance_page_services, "get_ee_balance_year_features", lambda: {})
    monkeypatch.setattr(
        balance_page_services, "classify_ee_balance_generation_years", lambda *args: (years, [])
    )
    monkeypatch.setattr(balance_page_services, "mark_manual_plan_generation_rows", lambda *args: None)
    monkeypatch.setattr(
        balance_page_services,
        "power_balance_station_list_query",
        lambda *args: {"union_energy_system_filter": 4},
    )
    monkeypatch.setattr(
        balance_page_services,
        "get_ee_import_export_page_data",
        lambda **kwargs: {
            "hierarchy": [{"ues_id": 4, "rows": [
                {"direction": "export", "country_id": 1, "country_name": "Казахстан",
                 "periods": dict.fromkeys(years, Decimal("-7"))},
                {"direction": "import", "country_id": 2, "country_name": "Монголия",
                 "periods": dict.fromkeys(years, Decimal("2"))},
            ]}]
        },
    )
    monkeypatch.setattr(
        balance_page_services,
        "get_ee_receive_transfer_oes_page_data",
        lambda **kwargs: {
            "hierarchy": [{"ues_id": 4, "ues_name": "ОЭС Сибири", "rows": [
                {"direction": "receive", "country_id": 8, "country_name": "ОЭС Востока",
                 "periods": dict.fromkeys(years, Decimal("9"))},
                {"direction": "transfer", "country_id": 9, "country_name": "ОЭС Урала",
                 "periods": dict.fromkeys(years, Decimal("-4"))},
            ]}]
        },
    )
    row_inputs = {
        "consumption": dict.fromkeys(years, Decimal("100")),
        "gaes_charge": dict.fromkeys(years, Decimal("5")),
        "generation_tes": dict.fromkeys(years, Decimal("150")),
    }
    for key in ("export", "ee_export", "ee_import", "ee_export_total", "ee_import_total", "flow_in", "flow_out"):
        row_inputs[key] = dict.fromkeys(years, Decimal("1000"))
    tables = build_ee_balance_tables(
        years,
        sheets=[sheet],
        inputs={slug: row_inputs},
        custom_flows={slug: [
            {"id": 1, "direction": "flow_in", "label": "Сохраненный прием",
             "values": dict.fromkeys(years, Decimal("5"))},
            {"id": 2, "direction": "flow_out", "label": "Сохраненная передача",
             "values": dict.fromkeys(years, Decimal("-3"))},
        ]},
        rounding_digits=1,
    )
    rows = {row["key"]: row for row in tables[slug]["rows"]}
    if isolated:
        assert not any(key.startswith(("ee_export", "ee_import", "flow_")) for key in rows)
        assert "surplus_deficit_with_flow" not in rows
        assert {term["row_key"] for term in rows["demand_total"]["formula"]["terms"]} == {
            "consumption", "gaes_charge"
        }
        for year in years:
            assert rows["demand_total"]["year_values_raw"][year] == Decimal("105")
            assert rows["surplus_deficit"]["year_values_raw"][year] == Decimal("45")
    else:
        assert "ee_export_country_1" in rows
        assert "ee_import_country_2" in rows
        assert "flow_in_oes_4_8" in rows
        assert "flow_out_oes_4_9" in rows
        assert "flow_in_custom_1" in rows
        assert "flow_out_custom_2" in rows
        for year in years:
            assert rows["demand_total"]["year_values_raw"][year] == Decimal("110")
            assert rows["flow_total"]["year_values_raw"][year] == Decimal("7")
            assert rows["surplus_deficit_with_flow"]["year_values_raw"][year] == Decimal("47")


def _row_display(tables, slug, key, year):
    row = next(item for item in tables[slug]["rows"] if item["key"] == key)
    return row["year_values"][year]


@pytest.mark.parametrize("import_amount, expected_demand, expected_surplus", [
    ("0", "115", "15"),
    ("3", "112", "18"),
])
def test_oes_energy_formulas(monkeypatch, import_amount, expected_demand, expected_surplus):
    years = [2026]
    sheet = {
        "slug": "centr", "sheet_name": "Центр", "layout": "oes_standard",
        "territory": {"kind": "ues", "id": 20},
    }
    monkeypatch.setattr(
        balance_page_services, "get_ee_import_export_page_data",
        lambda **_kwargs: {"hierarchy": [{"ues_id": 20, "rows": [
            {"direction": "export", "country_id": 1, "country_name": "Беларусь",
             "periods": {2026: Decimal("10")}},
            {"direction": "import", "country_id": 1, "country_name": "Беларусь",
             "periods": {2026: Decimal(import_amount)}},
        ]}]},
    )
    monkeypatch.setattr(
        balance_page_services, "get_ee_receive_transfer_oes_page_data",
        lambda **_kwargs: {"hierarchy": []},
    )
    tables = build_ee_balance_tables(
        years,
        sheets=[sheet],
        inputs={
            "centr": {
                "consumption": {2026: "100"},
                "gaes_charge": {2026: "5"},
                "generation_aes": {2026: "40"},
                "generation_ges": {2026: "20"},
                "generation_gaes": {2026: "5"},
                "generation_tes": {2026: "50"},
                "generation_snee": {2026: "0"},
                "generation_ses": {2026: "10"},
                "generation_ves": {2026: "5"},
                "installed_aes": {2026: 40},
                "installed_ges": {2026: 10},
                "installed_gaes": {2026: 5},
                "installed_tes": {2026: 30},
                "installed_snee": {2026: 2},
                "installed_ses": {2026: 2},
                "installed_ves": {2026: 1},
            }
        },
        rounding_digits=1,
    )
    rows = {row["key"]: row for row in tables["centr"]["rows"]}
    assert rows["ee_export_total"]["year_values_raw"][2026] == Decimal("10")
    assert rows["ee_import_total"]["year_values_raw"][2026] == Decimal(import_amount)
    assert rows["demand_total"]["year_values_raw"][2026] == Decimal(expected_demand)
    assert {"row_key": "ee_export_total", "coeff": 1} in rows["demand_total"]["formula"]["terms"]
    assert {"row_key": "ee_import_total", "coeff": -1} in rows["demand_total"]["formula"]["terms"]
    assert _row_display(tables, "centr", "demand_total", 2026) == expected_demand
    assert _row_display(tables, "centr", "gaes_charge", 2026) == "5"
    assert _row_display(tables, "centr", "generation_total", 2026) == "130"
    assert _row_display(tables, "centr", "coverage_total", 2026) == "130"
    assert _row_display(tables, "centr", "surplus_deficit", 2026) == expected_surplus
    assert _row_display(tables, "centr", "installed_total", 2026) == "90"
    aes = next(row for row in tables["centr"]["rows"] if row["key"] == "installed_aes")
    total = next(row for row in tables["centr"]["rows"] if row["key"] == "installed_total")
    assert aes["unit"] == "МВт"
    assert total["unit"] == "МВт"
    assert _row_display(tables, "centr", "chiim_aes", 2026) == "1 000"
    assert _row_display(tables, "centr", "chiim_ges", 2026) == "2 000"
    assert _row_display(tables, "centr", "chiim_gaes", 2026) == "1 000"
    assert _row_display(tables, "centr", "chiim_tes", 2026) == "1 667"
    assert _row_display(tables, "centr", "chiim_ses_ves", 2026) == "5 000"
    assert _row_display(tables, "centr", "chiim_total", 2026) == "1 444"
    chiim_aes = next(row for row in tables["centr"]["rows"] if row["key"] == "chiim_aes")
    chiim_total = next(row for row in tables["centr"]["rows"] if row["key"] == "chiim_total")
    assert chiim_aes["unit"] == "ч."
    assert chiim_total["unit"] == "ч."
    assert chiim_aes["year_values_raw"][2026] == 1000
    assert _row_display(tables, "centr", "chiim_snee", 2026) == "0"
    assert "Выработка электрической энергии АЭС" in chiim_aes["formula_tooltip"]
    assert "Установленная мощность АЭС" in chiim_aes["formula_tooltip"]


def test_selected_eu_plan_tes_equals_consumption_minus_other_generation(monkeypatch):
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_year_features",
        lambda: {2024: "факт", 2026: "план"},
    )
    residual_inputs = {
        "consumption": {2024: "100", 2026: "200"},
        "generation_aes": {2024: "1", 2026: "2"},
        "generation_ges": {2024: "3", 2026: "4"},
        "generation_gaes": {2024: "0", 2026: "0"},
        "generation_tes": {2024: "80", 2026: "999"},
        "generation_snee": {2024: "5", 2026: "6"},
        "generation_ses": {2024: "7", 2026: "8"},
        "generation_ves": {2024: "9", 2026: "10"},
    }
    sheets = [
        {
            "slug": "eu-255",
            "sheet_name": "Анадырский энергорайон",
            "layout": "oes_standard",
            "territory": {"kind": "eu", "id": 255, "name": "Анадырский энергорайон"},
        },
        {
            "slug": "eu-256",
            "sheet_name": "Центральный энергорайон Сахалинской области",
            "layout": "oes_standard",
            "territory": {
                "kind": "eu",
                "id": 256,
                "name": "Центральный энергорайон Сахалинской области",
            },
        },
        {
            "slug": "eu-254",
            "sheet_name": "Чаун-Билибинский энергорайон",
            "layout": "oes_standard",
            "territory": {"kind": "eu", "id": 254, "name": "Чаун-Билибинский энергорайон"},
        },
        {
            "slug": "eu-258",
            "sheet_name": "Центральный энергорайон Камчатского края",
            "layout": "oes_standard",
            "territory": {
                "kind": "eu",
                "id": 258,
                "name": "Центральный энергорайон Камчатского края",
            },
        },
        {
            "slug": "eu-257",
            "sheet_name": "Центральный энергорайон Магаданской области",
            "layout": "oes_standard",
            "territory": {
                "kind": "eu",
                "id": 257,
                "name": "Центральный энергорайон Магаданской области",
            },
        },
    ]
    tables = build_ee_balance_tables(
        [2024, 2026],
        inputs={
            "eu-255": dict(residual_inputs),
            "eu-256": dict(residual_inputs),
            "eu-254": dict(residual_inputs),
            "eu-258": dict(residual_inputs),
            "eu-257": dict(residual_inputs),
        },
        rounding_digits=1,
        sheets=sheets,
    )
    for slug in ("eu-255", "eu-256", "eu-254", "eu-258"):
        assert _row_display(tables, slug, "generation_tes", 2024) == "80"
        assert _row_display(tables, slug, "generation_tes", 2026) == "170"
        assert _row_display(tables, slug, "generation_total", 2026) == "200"
        tes = next(row for row in tables[slug]["rows"] if row["key"] == "generation_tes")
        assert tes["formula_tooltip"].startswith("В прогнозном периоде: ТЭС =")
        assert "Потребление электрической энергии" in tes["formula_tooltip"]
        assert "СЭС" in tes["formula_tooltip"]
        assert "ВЭС" in tes["formula_tooltip"]
    assert _row_display(tables, "eu-257", "generation_tes", 2026) == "999"
    magadan_tes = next(
        row for row in tables["eu-257"]["rows"] if row["key"] == "generation_tes"
    )
    assert "помесячного расчёта" in magadan_tes["formula_tooltip"]


def test_tites_siberia_plan_tes_uses_consumption_residual_after_monthly_overlay(monkeypatch):
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_year_features",
        lambda: {2024: "факт", 2026: "план"},
    )

    def monthly_overlay(inputs, sheets, years):
        inputs["oes-318"]["generation_tes"][2026] = "999"
        return inputs

    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.overlay_tes_forecast_generation_inputs",
        monthly_overlay,
    )
    sheets = [
        {
            "slug": "oes-318",
            "sheet_name": "ТИТЭС Сибири",
            "layout": "oes_standard",
            "territory": {"kind": "ues", "id": 318, "name": "ТИТЭС Сибири"},
        }
    ]
    tables = build_ee_balance_tables(
        [2024, 2026],
        inputs={
            "oes-318": {
                "consumption": {2024: "100", 2026: "200"},
                "generation_aes": {2024: "1", 2026: "2"},
                "generation_ges": {2024: "3", 2026: "4"},
                "generation_gaes": {2024: "0", 2026: "0"},
                "generation_tes": {2024: "80", 2026: "48"},
                "generation_snee": {2024: "5", 2026: "6"},
                "generation_ses": {2024: "7", 2026: "8"},
                "generation_ves": {2024: "9", 2026: "10"},
            }
        },
        rounding_digits=1,
        sheets=sheets,
    )

    assert _row_display(tables, "oes-318", "generation_tes", 2024) == "80"
    assert _row_display(tables, "oes-318", "generation_tes", 2026) == "170"
    assert _row_display(tables, "oes-318", "generation_total", 2026) == "200"
    tes = next(row for row in tables["oes-318"]["rows"] if row["key"] == "generation_tes")
    assert tes["formula_tooltip"].startswith("В прогнозном периоде: ТЭС =")
    assert "Потребление электрической энергии" in tes["formula_tooltip"]


def test_plan_tes_from_consumption_is_not_negative_when_consumption_unset(monkeypatch):
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_year_features",
        lambda: {2026: "план"},
    )
    sheets = [
        {
            "slug": "eu-254",
            "sheet_name": "Чаун-Билибинский энергорайон",
            "layout": "oes_standard",
        }
    ]
    tables = build_ee_balance_tables(
        [2026],
        inputs={
            "eu-254": {
                "consumption": {2026: "0"},
                "generation_aes": {2026: "350"},
                "generation_tes": {2026: "48"},
            }
        },
        rounding_digits=1,
        sheets=sheets,
    )
    assert _row_display(tables, "eu-254", "generation_tes", 2026) == "0"
    assert _row_display(tables, "eu-254", "generation_aes", 2026) == "350"


def test_anadyr_plan_tes_uses_ses_ves_parent_when_children_empty(monkeypatch):
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_year_features",
        lambda: {2026: "план"},
    )
    sheets = [
        {
            "slug": "eu-255",
            "sheet_name": "Анадырский энергорайон",
            "layout": "oes_standard",
        }
    ]
    tables = build_ee_balance_tables(
        [2026],
        inputs={
            "eu-255": {
                "consumption": {2026: "100"},
                "generation_aes": {2026: "10"},
                "generation_tes": {2026: "1"},
                "generation_ses_ves": {2026: "15"},
            }
        },
        rounding_digits=1,
        sheets=sheets,
    )
    assert _row_display(tables, "eu-255", "generation_tes", 2026) == "75"


def test_oes_plan_years_make_snee_and_ses_ves_generation_editable(monkeypatch):
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_manual_generation_services.classify_ee_balance_generation_years",
        lambda years, year_features=None: ([], [2026]),
    )
    tables = build_ee_balance_tables(
        [2026],
        inputs={
            "centr": {
                "generation_snee": {2026: "1"},
                "generation_ses_ves": {2026: "2"},
            }
        },
        rounding_digits=1,
    )
    snee = next(row for row in tables["centr"]["rows"] if row["key"] == "generation_snee")
    ses_ves = next(
        row for row in tables["centr"]["rows"] if row["key"] == "generation_ses_ves"
    )
    ses = next(row for row in tables["centr"]["rows"] if row["key"] == "generation_ses")
    ves = next(row for row in tables["centr"]["rows"] if row["key"] == "generation_ves")
    tes = next(row for row in tables["centr"]["rows"] if row["key"] == "generation_tes")
    ees_snee = next(
        row for row in tables["ees-rossii"]["rows"] if row["key"] == "generation_snee"
    )
    assert snee["editable_values"] is True
    assert snee["editable_years"] == [2026]
    assert snee["value_save_kind"] == "generation"
    assert ses_ves.get("formula")
    assert ses_ves.get("editable_values") is not True
    assert ses.get("editable_values") is not True
    assert ves.get("editable_values") is not True
    assert tes["editable_values"] is True
    assert tes["editable_years"] == [2026]
    assert tes["value_save_kind"] == "generation"
    assert ees_snee.get("formula")
    assert ees_snee.get("editable_values") is not True
    installed_ses = next(
        row for row in tables["centr"]["rows"] if row["key"] == "installed_ses"
    )
    assert installed_ses.get("editable_values") is not True


def test_sibir_tes_generation_is_editable_in_plan_year(monkeypatch):
    monkeypatch.setattr(
        balance_page_services, "classify_ee_balance_generation_years",
        lambda years, year_features=None: ([], [2026]),
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_manual_generation_services.classify_ee_balance_generation_years",
        lambda years, year_features=None: ([], [2026]),
    )
    monkeypatch.setattr(
        balance_page_services, "load_ee_balance_manual_generation_inputs",
        lambda years, sheets=None: {"sibir": {"generation_tes": {2026: Decimal("12.5")}}},
    )
    tables = build_ee_balance_tables(
        [2026],
        rounding_digits=1,
        sheets=[
            {
                "slug": "sibir",
                "sheet_name": "Сибирь",
                "group": GROUP_OES,
                "layout": "oes_sibir",
            }
        ],
    )

    tes = next(
        row for row in tables["sibir"]["rows"] if row["key"] == "generation_tes"
    )
    assert tes["editable_values"] is True
    assert tes["editable_years"] == [2026]
    assert tes["value_save_kind"] == "generation"
    assert tes["year_values"][2026] == "12,5"


@pytest.mark.parametrize("sheet", [
    sheet for sheet in POWER_BALANCE_SHEETS
    if sheet.get("group") == GROUP_OES or sheet.get("layout") == "oes_vostok"
] + [
    {"slug": "vostok", "sheet_name": "ОЭС Востока", "group": GROUP_OES, "layout": "oes_vostok"},
    {"slug": "oes-999", "sheet_name": "ТИТЭС Сибири", "group": GROUP_OES, "layout": "oes_standard"},
], ids=lambda sheet: sheet["slug"])
def test_all_oes_plan_generation_uses_only_manual_values(monkeypatch, sheet):
    slug = sheet["slug"]
    keys = ("generation_tes", "generation_ges", "generation_gaes")
    monkeypatch.setattr(
        balance_page_services, "classify_ee_balance_generation_years",
        lambda years, year_features=None: ([2024], [2026, 2027]),
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_manual_generation_services.classify_ee_balance_generation_years",
        lambda years, year_features=None: ([2024], [2026, 2027]),
    )
    monkeypatch.setattr(
        balance_page_services, "get_ee_balance_year_features",
        lambda: {2024: "факт", 2026: "план", 2027: "план"},
    )
    monkeypatch.setattr(
        balance_page_services, "load_ee_balance_generation_inputs",
        lambda years, sheets=None: {slug: {
            key: {2024: Decimal("10"), 2026: Decimal("99"), 2027: Decimal("100")}
            for key in keys
        }},
    )
    manual = {slug: {
        "generation_tes": {2026: Decimal("12.5")},
        "generation_ges": {2026: Decimal("0")},
        "generation_gaes": {2026: Decimal("3")},
    }}
    monkeypatch.setattr(
        balance_page_services, "load_ee_balance_manual_generation_inputs",
        lambda years, sheets=None: manual,
    )

    def monthly_overlay(inputs, sheets, years):
        for key in keys:
            inputs[slug][key][2026] = Decimal("999")
        return inputs

    monkeypatch.setattr(
        balance_page_services, "overlay_tes_forecast_generation_inputs", monthly_overlay,
    )
    tables = build_ee_balance_tables([2024, 2026, 2027], sheets=[sheet], rounding_digits=1)
    rows = {row["key"]: row for row in tables[slug]["rows"]}
    for key in keys:
        assert rows[key]["year_values_raw"][2024] == Decimal("10")
        assert rows[key]["editable_years"] == [2026, 2027]
        assert rows[key]["value_save_kind"] == "generation"
        assert rows[key]["year_values_raw"].get(2027) is None
        assert not rows[key].get("formula_tooltip")
    assert rows["generation_tes"]["year_values_raw"][2026] == Decimal("12.5")
    assert rows["generation_ges"]["year_values_raw"][2026] == Decimal("0")
    assert rows["generation_gaes"]["year_values_raw"][2026] == Decimal("3")
    assert rows["generation_total"]["year_values_raw"][2026] == Decimal("15.5")
    manual.clear()
    tables = build_ee_balance_tables([2024, 2026, 2027], sheets=[sheet], rounding_digits=1)
    rows = {row["key"]: row for row in tables[slug]["rows"]}
    for key in keys:
        assert rows[key]["year_values_raw"].get(2026) is None
        assert rows[key]["year_values_raw"][2024] == Decimal("10")


def test_manual_oes_generation_is_used_in_ees_and_sz1_totals(monkeypatch):
    monkeypatch.setattr(
        balance_page_services, "classify_ee_balance_generation_years",
        lambda years, year_features=None: ([], [2026]),
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_manual_generation_services.classify_ee_balance_generation_years",
        lambda years, year_features=None: ([], [2026]),
    )
    sheets = [
        {"slug": "centr", "sheet_name": "Центр", "group": GROUP_OES, "layout": "oes_standard"},
        {"slug": "sibir", "sheet_name": "Сибирь", "group": GROUP_OES, "layout": "oes_sibir"},
        {"slug": "ees-rossii", "sheet_name": "ЕЭС", "group": GROUP_EES, "layout": "ees_rossii",
         "source_slugs": ["centr", "sibir"]},
        {"slug": "1-sz-ees", "sheet_name": "1-я СЗ", "group": GROUP_SZ, "layout": "sz1",
         "source_slugs": ["centr", "sibir"], "subtract_slugs": []},
    ]
    keys = ("generation_tes", "generation_ges", "generation_gaes")
    monkeypatch.setattr(
        balance_page_services, "load_ee_balance_generation_inputs",
        lambda years, sheets=None: {
            slug: {key: {2026: Decimal("999")} for key in keys}
            for slug in ("centr", "sibir")
        },
    )
    monkeypatch.setattr(
        balance_page_services, "load_ee_balance_manual_generation_inputs",
        lambda years, sheets=None: {
            "centr": {key: {2026: amount} for key, amount in zip(keys, (10, 0, 2))},
            "sibir": {key: {2026: amount} for key, amount in zip(keys, (20, 5, 3))},
        },
    )
    tables = build_ee_balance_tables([2026], sheets=sheets, rounding_digits=1)
    for slug in ("ees-rossii", "1-sz-ees"):
        rows = {row["key"]: row for row in tables[slug]["rows"]}
        for key, expected in zip(keys, (30, 5, 5)):
            assert rows[key]["year_values_raw"][2026] == Decimal(expected)
            assert rows[key].get("formula")
            assert not rows[key].get("editable_values")
        assert rows["generation_total"]["year_values_raw"][2026] == Decimal("40")


def test_table_context_for_known_slug():
    with patch(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_year_columns",
        return_value=[2026, 2027],
    ), patch(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_year_features",
        return_value={2026: "Отчет", 2027: "План"},
    ), patch(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_filter_year_list",
        return_value=[2026, 2027],
    ), patch(
        "app.energy_balance.services.ee_balance_page_services.get_ee_import_export_page_data",
        return_value={"hierarchy": []},
    ), patch(
        "app.energy_balance.services.ee_balance_page_services.get_ee_receive_transfer_oes_page_data",
        return_value={"hierarchy": []},
    ), patch(
        "app.energy_balance.services.ee_balance_ves_ses_page_services._can_edit_ves_ses_energy",
        return_value=False,
    ):
        context = build_ee_balance_table_context("centr")
    assert context is not None
    assert context["sheet"]["sheet_name"] == "Центр"
    assert context["page_title"] == "Баланс электрической энергии Центр"
    assert context["browser_title"] == "Баланс ЭЭ Центр"
    assert context["years"] == [2026, 2027]
    consumption = next(row for row in context["rows"] if row["key"] == "consumption")
    export = next(row for row in context["rows"] if row["key"] == "ee_export")
    installed_total = next(row for row in context["rows"] if row["key"] == "installed_total")
    assert consumption["unit"] == EE_BALANCE_UNIT
    assert export["unit"] == EE_BALANCE_UNIT
    assert not export.get("editable_values")
    demand = next(row for row in context["rows"] if row["key"] == "demand_total")
    assert {"row_key": "ee_export", "coeff": 1} in demand["formula"]["terms"]
    assert installed_total["unit"] == "МВт"
    assert installed_total["label"] == "Установленная мощность"
    chiim_total = next(row for row in context["rows"] if row["key"] == "chiim_total")
    assert chiim_total["unit"] == "ч."
    assert chiim_total["label"] == "ЧЧИУМ"
    assert context["show_hydro_year_nav"] is False
    assert context["hydro_year"] is None
    assert context["hydro_year_buttons"] == []
    assert context["can_edit"] is False


def test_sheet_has_ges_or_gaes_capacity_true_when_ges_positive_in_one_year():
    rows = [
        {"key": "installed_ges", "year_values_raw": {2026: 0, 2027: 12.5}},
        {"key": "installed_gaes", "year_values_raw": {2026: 0, 2027: 0}},
    ]
    assert sheet_has_ges_or_gaes_capacity(rows, [2026, 2027]) is True


def test_sheet_has_ges_or_gaes_capacity_true_when_only_gaes_positive():
    rows = [
        {"key": "installed_ges", "year_values_raw": {2026: 0}},
        {"key": "installed_gaes", "year_values_raw": {2026: 1}},
    ]
    assert sheet_has_ges_or_gaes_capacity(rows, [2026]) is True


def test_sheet_has_ges_or_gaes_capacity_false_when_zero_or_empty():
    rows = [
        {"key": "installed_ges", "year_values_raw": {2026: 0}},
        {"key": "installed_gaes", "year_values_raw": {2026: None}},
        {"key": "installed_aes", "year_values_raw": {2026: 100}},
    ]
    assert sheet_has_ges_or_gaes_capacity(rows, [2026]) is False
    assert sheet_has_ges_or_gaes_capacity(rows, []) is False
    assert sheet_has_ges_or_gaes_capacity(None, [2026]) is False


def test_resolve_ee_balance_hydro_year_defaults_to_average():
    assert resolve_ee_balance_hydro_year(None) == HYDRO_YEAR_AVERAGE
    assert resolve_ee_balance_hydro_year("average") == HYDRO_YEAR_AVERAGE
    assert resolve_ee_balance_hydro_year("low") == HYDRO_YEAR_LOW
    assert resolve_ee_balance_hydro_year("маловодный") == HYDRO_YEAR_LOW


def test_hydro_year_for_balance_sheet_average_only_for_five_oes():
    sheets = [
        {
            "slug": "centr",
            "group": "oes",
            "layout": "oes_standard",
            "sheet_name": "ОЭС Центра",
            "territory": {"kind": "ues", "id": 2, "name": "Центр"},
        },
        {
            "slug": "sibir",
            "group": "oes",
            "layout": "oes_sibir",
            "sheet_name": "ОЭС Сибири",
            "territory": {"kind": "ues", "id": 6, "name": "Сибирь"},
        },
        {
            "slug": "ees-rossii",
            "group": "ees",
            "layout": "ees_rossii",
            "sheet_name": "ЕЭС России",
        },
        {
            "slug": "1-sz-ees",
            "group": "sz",
            "layout": "sz1",
            "sheet_name": "1-я СЗ ЕЭС",
        },
        {
            "slug": "eu-258",
            "group": "eu",
            "layout": "oes_standard",
            "sheet_name": "Энергорайон",
            "parent_slug": "oes-2",
        },
        {
            "slug": "eu-101",
            "group": "eu",
            "layout": "oes_standard",
            "sheet_name": "Центральный энергорайон Камчатского края",
            "parent_slug": "sibir",
        },
    ]
    by_slug = {item["slug"]: item for item in sheets}
    assert hydro_year_for_balance_sheet(by_slug["centr"], sheets) == HYDRO_YEAR_AVERAGE
    assert hydro_year_for_balance_sheet(
        {
            "slug": "severo-zapad",
            "group": "oes",
            "layout": "oes_standard",
            "sheet_name": "ОЭС Северо-Запада",
        },
        sheets,
    ) == HYDRO_YEAR_AVERAGE
    assert hydro_year_for_balance_sheet(
        {
            "slug": "srednyaya-volga",
            "group": "oes",
            "sheet_name": "ОЭС Волги",
        },
        sheets,
    ) == HYDRO_YEAR_AVERAGE
    assert hydro_year_for_balance_sheet(
        {"slug": "ural", "group": "oes", "sheet_name": "ОЭС Урала"},
        sheets,
    ) == HYDRO_YEAR_AVERAGE
    assert hydro_year_for_balance_sheet(
        {"slug": "yug", "group": "oes", "layout": "oes_yug", "sheet_name": "ОЭС Юга"},
        sheets,
    ) == HYDRO_YEAR_AVERAGE
    assert hydro_year_for_balance_sheet(by_slug["sibir"], sheets) == HYDRO_YEAR_LOW
    assert hydro_year_for_balance_sheet(by_slug["ees-rossii"], sheets) is None
    assert hydro_year_for_balance_sheet(by_slug["1-sz-ees"], sheets) is None
    assert hydro_year_for_balance_sheet(by_slug["eu-258"], sheets) == HYDRO_YEAR_AVERAGE
    assert hydro_year_for_balance_sheet(by_slug["eu-101"], sheets) == HYDRO_YEAR_LOW


def test_format_ee_balance_browser_title():
    assert (
        format_ee_balance_browser_title("Баланс электрической энергии Северо-Запад")
        == "Баланс ЭЭ Северо-Запад"
    )
    assert format_ee_balance_browser_title("Другой заголовок") == "Другой заголовок"


def test_format_ee_balance_page_title_appends_hydro_year():
    base = "Баланс электрической энергии Северо-Запад"
    assert format_ee_balance_page_title(base) == base
    assert format_ee_balance_page_title(base, hydro_year=None) == base
    assert (
        format_ee_balance_page_title(base, hydro_year=HYDRO_YEAR_AVERAGE)
        == "Баланс электрической энергии Северо-Запад (средневодный год)"
    )
    assert (
        format_ee_balance_page_title(base, hydro_year=HYDRO_YEAR_LOW)
        == "Баланс электрической энергии Северо-Запад (маловодный год)"
    )
    already = "Баланс электрической энергии Северо-Запад (маловодный год)"
    assert format_ee_balance_page_title(already, hydro_year=HYDRO_YEAR_LOW) == already


def test_table_context_hydro_year_in_title_without_buttons(monkeypatch):
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.load_power_balance_installed_capacity_inputs",
        lambda years, sheets=None: {
            "severo-zapad": {"installed_ges": {2026: 100, 2027: 0}},
            "sibir": {"installed_ges": {2026: 80, 2027: 0}},
            "ees-rossii": {"installed_ges": {2026: 180, 2027: 0}},
        },
    )
    with patch(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_year_columns",
        return_value=[2026, 2027],
    ), patch(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_year_features",
        return_value={2026: "Отчет", 2027: "План"},
    ), patch(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_filter_year_list",
        return_value=[2026, 2027],
    ):
        context_nw = build_ee_balance_table_context(
            "severo-zapad", hydro_year=HYDRO_YEAR_LOW
        )
        context_sibir = build_ee_balance_table_context("sibir")
        context_ees = build_ee_balance_table_context("ees-rossii")
    assert context_nw is not None
    assert context_sibir is not None
    assert context_ees is not None
    assert context_nw["show_hydro_year_nav"] is False
    assert context_nw["hydro_year_buttons"] == []
    assert context_nw["hydro_year"] == HYDRO_YEAR_AVERAGE
    assert context_nw["page_title"] == (
        "Баланс электрической энергии Северо-Запад (средневодный год)"
    )
    assert context_nw["browser_title"] == "Баланс ЭЭ Северо-Запад (средневодный год)"
    assert context_sibir["hydro_year"] == HYDRO_YEAR_LOW
    assert context_sibir["page_title"] == (
        "Баланс электрической энергии Сибирь (маловодный год)"
    )
    assert context_ees["hydro_year"] is None
    assert context_ees["page_title"] == "Баланс электрической энергии ЕЭС России"
    assert context_ees["browser_title"] == "Баланс ЭЭ ЕЭС России"


def test_table_context_does_not_pass_global_hydro_year_to_generation(monkeypatch):
    captured: dict[str, object] = {}

    def fake_gen(years, sheets=None, hydro_year=None):
        captured["called"] = True
        captured["hydro_year"] = hydro_year
        return {}

    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.load_ee_balance_generation_inputs",
        fake_gen,
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.load_power_balance_installed_capacity_inputs",
        lambda years, sheets=None: {
            "severo-zapad": {"installed_ges": {2026: 100, 2027: 0}}
        },
    )
    with patch(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_year_columns",
        return_value=[2026, 2027],
    ), patch(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_year_features",
        return_value={2026: "Отчет", 2027: "План"},
    ), patch(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_filter_year_list",
        return_value=[2026, 2027],
    ):
        context = build_ee_balance_table_context(
            "severo-zapad", hydro_year=HYDRO_YEAR_LOW
        )
    assert context is not None
    assert captured["called"] is True
    assert captured["hydro_year"] is None


def test_sheet_nav_template_has_no_hydro_year_buttons():
    from jinja2 import Environment, FileSystemLoader

    env = Environment(
        loader=FileSystemLoader("app/templates"),
        autoescape=True,
    )
    def _url_for(endpoint, **kwargs):
        slug = kwargs.get("slug", "")
        if endpoint == "energy_balance_bp.power_balance_table":
            return "/energy_balance/power_balance/{slug}/".format(slug=slug)
        return "/energy_balance/ee_balance/{slug}/".format(slug=slug)

    env.globals["url_for"] = _url_for
    html = env.get_template("energy_balance/ee_balance/_sheet_nav.html").render(
        current_slug="severo-zapad",
        sheet_groups=[
            {
                "group": "oes",
                "sheets": [
                    {"slug": "severo-zapad", "sheet_name": "ОЭС Северо-Запада"},
                    {"slug": "centr", "sheet_name": "ОЭС Центра"},
                ],
            }
        ],
        start_year=2026,
        end_year=2031,
        rounding_digits=1,
        show_hydro_year_nav=True,
        hydro_year=HYDRO_YEAR_AVERAGE,
        hydro_year_buttons=[
            {
                "key": HYDRO_YEAR_AVERAGE,
                "label": "ОЭС Северо-Запада (средневодный год)",
            },
            {"key": HYDRO_YEAR_LOW, "label": "ОЭС Северо-Запада (маловодный год)"},
        ],
    )
    assert "ОЭС Северо-Запада (средневодный год)" not in html
    assert "ОЭС Северо-Запада (маловодный год)" not in html
    assert "hydro_year=" not in html
    assert "Вариант водохозяйственного года" not in html
    assert "Балансы мощности" in html
    assert "Балансы ЭЭ" not in html
    assert "Балансы ЭМ" not in html
    assert "/energy_balance/power_balance/severo-zapad/" in html
    assert html.count('class="btn btn-secondary fs-5 text-nowrap flex-shrink-0"') == 1
    oes_at = html.find("ОЭС Северо-Запада")
    power_at = html.find("Балансы мощности")
    assert 0 <= oes_at < power_at


def test_ee_balance_nav_renders_east_button_next_to_second_zone_with_filters():
    from jinja2 import Environment, FileSystemLoader

    calls = []
    env = Environment(
        loader=FileSystemLoader("app/templates"),
        autoescape=True,
    )

    def _url_for(endpoint, **kwargs):
        calls.append((endpoint, kwargs))
        slug = kwargs.get("slug", "")
        query = "&".join(
            f"{key}={kwargs[key]}"
            for key in ("start_year", "end_year", "rounding_digits")
            if key in kwargs
        )
        return f"/energy_balance/ee_balance/{slug}/?{query}"

    env.globals["url_for"] = _url_for
    html = env.get_template("energy_balance/ee_balance/_sheet_nav.html").render(
        current_slug="ees-rossii",
        first_row_active_slug="ees-rossii",
        sheet_groups=[
            {
                "group": "sz",
                "sheets": [
                    {"slug": "2-sz-ees-vostok", "sheet_name": "2-я СЗ"},
                ],
            },
            {
                "group": "oes",
                "sheets": [
                    {"slug": "sibir", "sheet_name": "ОЭС Сибири"},
                    {"slug": "vostok", "sheet_name": "ОЭС Востока"},
                ],
            },
        ],
        synchronous_zone_subtab_sheets=[
            {"slug": "2-sz-ees-vostok", "sheet_name": "2-я СЗ"}
        ],
        start_year=2018,
        end_year=2031,
        rounding_digits=1,
    )

    assert html.count(">ОЭС Востока</a>") == 1
    assert "/energy_balance/ee_balance/vostok/?start_year=2018&amp;end_year=2031&amp;rounding_digits=1" in html
    assert html.index("ОЭС Востока") < html.index("ОЭС Сибири") < html.index("2-я СЗ")
    assert any(
        endpoint == "energy_balance_bp.ee_balance_table"
        and kwargs == {
            "slug": "vostok",
            "start_year": 2018,
            "end_year": 2031,
            "rounding_digits": 1,
        }
        for endpoint, kwargs in calls
    )


def test_tites_east_child_buttons_render_without_hydro_year():
    from jinja2 import Environment, FileSystemLoader

    env = Environment(
        loader=FileSystemLoader("app/templates"),
        autoescape=True,
    )
    def _url_for(endpoint, **kwargs):
        slug = kwargs.get("slug", "")
        if endpoint == "energy_balance_bp.power_balance_table":
            return "/energy_balance/power_balance/{slug}/".format(slug=slug)
        return "/energy_balance/ee_balance/{slug}/".format(slug=slug)

    env.globals["url_for"] = _url_for
    html = env.get_template("energy_balance/ee_balance/_sheet_nav.html").render(
        current_slug="eu-104",
        first_row_active_slug="oes-15",
        sheet_groups=[
            {
                "group": "oes",
                "sheets": [
                    {
                        "slug": "oes-15",
                        "sheet_name": "ТИТЭС Востока",
                        "first_child_slug": "eu-101",
                    }
                ],
            }
        ],
        tites_east_child_sheets=[
            {"slug": "eu-101", "sheet_name": "Центральный энергорайон Камчатского края"},
            {"slug": "eu-104", "sheet_name": "Чаун-Билибинский энергорайон"},
            {"slug": "eu-105", "sheet_name": "Анадырский энергорайон"},
        ],
        start_year=2026,
        end_year=2031,
        rounding_digits=1,
        show_hydro_year_nav=True,
        hydro_year=HYDRO_YEAR_AVERAGE,
        hydro_year_buttons=[
            {"key": HYDRO_YEAR_AVERAGE, "label": "Камчатская ЭС (средневодный год)"},
            {"key": HYDRO_YEAR_LOW, "label": "Камчатская ЭС (маловодный год)"},
        ],
    )
    power_at = html.find("Балансы мощности")
    kamchatka_at = html.find("Центральный энергорайон Камчатского края")
    chaun_at = html.find("Чаун-Билибинский энергорайон")
    anadyr_at = html.find("Анадырский энергорайон")
    assert 0 < power_at < kamchatka_at < chaun_at < anadyr_at
    assert "Камчатская ЭС (средневодный год)" not in html
    assert "hydro_year=" not in html
    assert "Балансы ЭЭ" not in html
    assert "/energy_balance/power_balance/eu-104/" in html
    assert "/energy_balance/ee_balance/eu-101/" in html
    assert "/energy_balance/ee_balance/eu-104/" in html
    assert "/energy_balance/ee_balance/eu-105/" in html
    assert html.count("btn-primary") >= 2


def test_ees_and_sz1_generation_sums_mixed_hydro_years():
    years = [2026]
    tables = build_ee_balance_tables(
        years,
        inputs={
            "severo-zapad": {"generation_ges": {2026: 10}},
            "centr": {"generation_ges": {2026: 20}},
            "srednyaya-volga": {"generation_ges": {2026: 4}},
            "yug": {"generation_ges": {2026: 5}},
            "ural": {"generation_ges": {2026: 6}},
            "sibir": {"generation_ges": {2026: 7}},
            "2-sz-ees-vostok": {"generation_ges": {2026: 8}},
            "kaliningradskaya-sz-ees": {"generation_ges": {2026: 3}},
        },
        rounding_digits=1,
    )
    assert _row_display(tables, "ees-rossii", "generation_ges", 2026) == "60"
    assert _row_display(tables, "1-sz-ees", "generation_ges", 2026) == "49"


def test_ees_and_sz1_installed_capacity_cross_sheet_formulas():
    years = [2026]
    tables = build_ee_balance_tables(
        years,
        inputs={
            "severo-zapad": {"installed_aes": {2026: 10}},
            "centr": {"installed_aes": {2026: 20}},
            "srednyaya-volga": {"installed_aes": {2026: 4}},
            "yug": {"installed_aes": {2026: 5}},
            "ural": {"installed_aes": {2026: 6}},
            "sibir": {"installed_aes": {2026: 7}},
            "2-sz-ees-vostok": {"installed_aes": {2026: 8}},
            "kaliningradskaya-sz-ees": {"installed_aes": {2026: 3}},
        },
        rounding_digits=1,
    )
    assert _row_display(tables, "ees-rossii", "installed_aes", 2026) == "60"
    assert _row_display(tables, "1-sz-ees", "installed_aes", 2026) == "49"
    ees_aes = next(
        row for row in tables["ees-rossii"]["rows"] if row["key"] == "installed_aes"
    )
    assert ees_aes["unit"] == "МВт"
    assert "Северо-Запад" in ees_aes["formula_tooltip"]
    assert "ОЭС Востока" in ees_aes["formula_tooltip"]
    assert "2-я СЗ" not in ees_aes["formula_tooltip"]


def test_ural_without_tyumen_subtracts_inputs_and_recalculates_formula_rows():
    source_sheet = {"slug": "ural", "sheet_name": "Урал"}
    tyumen_sheet = {"slug": "res-2827", "sheet_name": "Тюменская ЭС"}
    tables = {
        "ural": {
            "sheet": source_sheet,
            "rows": [
                {
                    "key": "consumption",
                    "formula": None,
                    "year_values_raw": {2026: Decimal("100.25")},
                    "year_values": {2026: "100,3"},
                    "editable_values": True,
                    "editable_years": [2026],
                    "value_save_kind": "manual_generation",
                    "row_key": "consumption",
                },
                {
                    "key": "ee_export_country_1",
                    "formula": None,
                    "year_values_raw": {2026: Decimal("30")},
                    "year_values": {2026: "30"},
                },
                {
                    "key": "flow_out_oes_413_414",
                    "formula": None,
                    "year_values_raw": {2026: Decimal("12")},
                    "year_values": {2026: "12"},
                },
                {
                    "key": "demand_total",
                    "formula": {"terms": [{"row_key": "consumption"}]},

                    "year_values_raw": {2026: Decimal("100.25")},
                    "year_values": {2026: "100,3"},
                    "editable_values": False,
                },
            ],
        },
        "res-2827": {
            "sheet": tyumen_sheet,
            "rows": [
                {
                    "key": "consumption",
                    "formula": None,
                    "year_values_raw": {2026: Decimal("25.05")},
                    "year_values": {2026: "25,1"},
                },
                {
                    "key": "ee_export_country_1",
                    "formula": None,
                    "year_values_raw": {2026: Decimal("8")},
                    "year_values": {2026: "8"},
                },
                {
                    "key": "flow_out_oes_413_414",
                    "formula": None,
                    "year_values_raw": {2026: Decimal("3")},
                    "year_values": {2026: "3"},
                },
            ],
        },
    }

    _append_ural_without_tyumen_table(
        tables, "res-2827", [2026], rounding_digits=1
    )

    rows = {row["key"]: row for row in tables[URAL_WITHOUT_TYUMEN_SLUG]["rows"]}
    assert rows["consumption"]["year_values_raw"][2026] == Decimal("75.20")
    assert rows["consumption"]["year_values"][2026] == "75,2"
    assert rows["ee_export_country_1"]["year_values_raw"][2026] == Decimal("22")
    assert rows["flow_out_oes_413_414"]["year_values_raw"][2026] == Decimal("9")
    assert rows["demand_total"]["year_values_raw"][2026] == Decimal("75.20")
    assert rows["consumption"]["editable_values"] is False
    assert "value_save_kind" not in rows["consumption"]


def test_ural_without_tyumen_manual_generation_overrides_and_enables_plan_cells(monkeypatch):
    sheet = {
        "slug": URAL_WITHOUT_TYUMEN_SLUG,
        "group": GROUP_OES,
        "layout": "oes_standard",
    }
    tables = {
        URAL_WITHOUT_TYUMEN_SLUG: {
            "sheet": sheet,
            "rows": [
                {
                    "key": key,
                    "label": label,
                    "formula": None,
                    "year_values_raw": {2026: Decimal("20")},
                    "year_values": {2026: "20"},
                    "editable_values": False,
                }
                for key, label in (
                    ("generation_tes", "ТЭС"),
                    ("generation_ges", "ГЭС"),
                    ("generation_gaes", "ГАЭС"),
                )
            ],
        }
    }
    monkeypatch.setattr(
        balance_page_services,
        "load_ee_balance_manual_generation_inputs",
        lambda years, sheets=None: {
            URAL_WITHOUT_TYUMEN_SLUG: {
                "generation_tes": {2026: Decimal("12.5")},
                "generation_ges": {2026: Decimal("10")},
                "generation_gaes": {2026: Decimal("5")},
            }
        },
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_manual_generation_services.classify_ee_balance_generation_years",
        lambda years: ([], [2026]),
    )

    _overlay_ural_without_tyumen_manual_generation(tables, [2026], rounding_digits=1)

    rows = {
        row["key"]: row for row in tables[URAL_WITHOUT_TYUMEN_SLUG]["rows"]
    }
    assert rows["generation_tes"]["year_values_raw"][2026] == Decimal("12.5")
    assert rows["generation_tes"]["year_values"][2026] == "12,5"
    for key in ("generation_tes", "generation_ges", "generation_gaes"):
        assert rows[key]["editable_values"] is True
        assert rows[key]["editable_years"] == [2026]
        assert rows[key]["value_save_kind"] == "generation"


def test_ee_transfer_filters_normalize_regional_energy_system_id(monkeypatch):
    monkeypatch.setattr(
        balance_page_services,
        "power_balance_station_list_query",
        lambda *args, **kwargs: {"regional_energy_system_filter": 2827},
    )

    assert _ee_transfer_filters({}, [], [2026]) == {
        "regional_energy_system_filter": [2827]
    }


def test_ural_subtabs_link_to_ural_total_excluded_and_tyumen_system():
    assert _ural_subtab_sheets({"slug": "res-2827"}) == [
        {"slug": "ural", "sheet_name": "ОЭС Урала (с Тюменской ЭС)"},
        {
            "slug": URAL_WITHOUT_TYUMEN_SLUG,
            "sheet_name": "ОЭС Урала (без Тюменской ЭС)",
        },
        {"slug": "res-2827", "sheet_name": "Тюменская ЭС"},
    ]


def test_ural_subtabs_render_as_navigation_and_preserve_selected_period():
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader("app/templates"), autoescape=True)
    env.globals["url_for"] = lambda _endpoint, **kwargs: (
        f"/energy_balance/ee_balance/{kwargs['slug']}/?"
        f"start_year={kwargs['start_year']}&end_year={kwargs['end_year']}"
        f"&rounding_digits={kwargs['rounding_digits']}"
    )
    html = env.get_template("energy_balance/ee_balance/_sheet_nav.html").render(
        current_slug="ural",
        first_row_active_slug="ural",
        sheet_groups=[
            {"group": "oes", "sheets": [{"slug": "ural", "sheet_name": "Урал"}]}
        ],
        ural_subtab_sheets=_ural_subtab_sheets({"slug": "res-2827"}),
        tites_east_child_sheets=[],
        start_year=2026,
        end_year=2031,
        rounding_digits=1,
    )

    assert "ОЭС Урала (с Тюменской ЭС)" in html
    assert "ОЭС Урала (без Тюменской ЭС)" in html
    assert "Тюменская ЭС" in html
    assert "/energy_balance/ee_balance/ural-without-tyumen/?start_year=2026&amp;end_year=2031&amp;rounding_digits=1" in html
    assert html.count('class="btn btn-primary') == 2


def test_severo_zapad_region_sheets_resolve_three_requested_res(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.common.services.get_services.energy_systems.regional_energy_system_get_services.get_regional_energy_system_list_full",
        lambda: [
            SimpleNamespace(id=2806, id_union_energy_system=410, name="ЭС Республики Коми"),
            SimpleNamespace(id=2759, id_union_energy_system=410, name="ЭС Архангельской области и Ненецкого АО"),
            SimpleNamespace(id=2775, id_union_energy_system=410, name="ЭС Калининградской области"),
            SimpleNamespace(id=9999, id_union_energy_system=411, name="ЭС Республики Коми"),
        ],
    )
    monkeypatch.setattr(
        "app.energy_balance.services.power_balance_page_services._synthetic_sheet_for_slug",
        lambda slug: {
            "slug": slug,
            "sheet_name": slug,
            "group": "res",
            "territory": {"kind": "res", "id": int(slug.split("-")[1])},
        },
    )

    regions = _severo_zapad_region_sheets([
        {"slug": "severo-zapad", "territory": {"id": 410}}
    ])

    assert [sheet["slug"] for sheet in regions] == ["res-2759", "res-2775", "res-2806"]
    assert [sheet["sheet_name"] for sheet in regions] == [
        "ЭС Архангельской области",
        "ЭС Калининградской области",
        "ЭС Республики Коми",
    ]
    assert [sheet["ee_balance_receive_transfer"] for sheet in regions] == [
        True,
        False,
        True,
    ]
    subtabs = _severo_zapad_subtab_sheets(regions)
    assert subtabs[0] == {
        "slug": "severo-zapad",
        "sheet_name": "ЭС ОЭС Северо-Запада",
    }
    assert subtabs[1] == {
        "slug": SEVERO_ZAPAD_CENTER_SLUG,
        "sheet_name": "ОЭС Северо-Запада (центр)",
    }
    assert [tab["slug"] for tab in subtabs[2:]] == [
        "res-2759", "res-2775", "res-2806"
    ]


def test_severo_zapad_center_subtracts_regions_and_recalculates_formulas():
    def values(slug, consumption, export, demand=None):
        rows = [
            {
                "key": "consumption",
                "formula": None,
                "year_values_raw": {2026: Decimal(consumption)},
                "year_values": {2026: consumption},
                "editable_values": True,
                "value_save_kind": "manual_generation",
            },
            {
                "key": "ee_export",
                "formula": None,
                "year_values_raw": {2026: Decimal(export)},
                "year_values": {2026: export},
            },
            {
                "key": "demand_total",
                "formula": {"terms": [{"row_key": "consumption"}]},
                "year_values_raw": {2026: Decimal(demand or consumption)},
                "year_values": {2026: demand or consumption},
            },
        ]
        return {"sheet": {"slug": slug}, "rows": rows}

    tables = {
        "severo-zapad": values("severo-zapad", "100", "50"),
        "res-2759": values("res-2759", "10", "2"),
        "res-2775": values("res-2775", "20", "3"),
        "res-2806": values("res-2806", "3", "4"),
    }

    _append_severo_zapad_center_table(
        tables, ["res-2759", "res-2775", "res-2806"], [2026], 1
    )

    rows = {
        row["key"]: row for row in tables[SEVERO_ZAPAD_CENTER_SLUG]["rows"]
    }
    assert rows["consumption"]["year_values_raw"][2026] == Decimal("67")
    assert rows["ee_export"]["year_values_raw"][2026] == Decimal("41")
    assert rows["demand_total"]["year_values_raw"][2026] == Decimal("67")
    assert rows["consumption"]["editable_values"] is False
    assert "value_save_kind" not in rows["consumption"]


def test_severo_zapad_subtabs_render_as_navigation_and_preserve_period():
    from jinja2 import Environment, FileSystemLoader

    regions = [
        {"slug": "res-2759", "sheet_name": "ЭС Архангельской области"},
        {"slug": "res-2775", "sheet_name": "ЭС Калининградской области"},
        {"slug": "res-2806", "sheet_name": "ЭС Республики Коми"},
    ]
    env = Environment(loader=FileSystemLoader("app/templates"), autoescape=True)
    env.globals["url_for"] = lambda _endpoint, **kwargs: (
        f"/energy_balance/ee_balance/{kwargs['slug']}/?"
        f"start_year={kwargs['start_year']}&end_year={kwargs['end_year']}"
        f"&rounding_digits={kwargs['rounding_digits']}"
    )
    html = env.get_template("energy_balance/ee_balance/_sheet_nav.html").render(
        current_slug=SEVERO_ZAPAD_CENTER_SLUG,
        first_row_active_slug="severo-zapad",
        sheet_groups=[
            {"group": "oes", "sheets": [{"slug": "severo-zapad", "sheet_name": "Северо-Запад"}]}
        ],
        tites_east_child_sheets=[],
        ural_subtab_sheets=[],
        severo_zapad_subtabs=_severo_zapad_subtab_sheets(regions),
        start_year=2018,
        end_year=2031,
        rounding_digits=1,
    )

    for label in (
        "ЭС ОЭС Северо-Запада",
        "ОЭС Северо-Запада (центр)",
        "ЭС Архангельской области",
        "ЭС Калининградской области",
        "ЭС Республики Коми",
    ):
        assert label in html
    assert "/energy_balance/ee_balance/severo-zapad-center/?start_year=2018&amp;end_year=2031&amp;rounding_digits=1" in html


def test_severo_zapad_subtabs_render_only_on_the_oes_sheet(monkeypatch):
    regions = [
        {
            "slug": "res-2759",
            "sheet_name": "ЭС Архангельской области",
            "title": "Баланс электрической энергии ЭС Архангельской области",
            "group": GROUP_RES,
            "layout": "oes_standard",
            "territory": {"kind": "res", "id": 2759},
        },
        {
            "slug": "res-2775",
            "sheet_name": "ЭС Калининградской области",
            "title": "Баланс электрической энергии ЭС Калининградской области",
            "group": GROUP_RES,
            "layout": "oes_standard",
            "territory": {"kind": "res", "id": 2775},
        },
        {
            "slug": "res-2806",
            "sheet_name": "ЭС Республики Коми",
            "title": "Баланс электрической энергии ЭС Республики Коми",
            "group": GROUP_RES,
            "layout": "oes_standard",
            "territory": {"kind": "res", "id": 2806},
        },
    ]
    base_sheet = {
        "slug": "severo-zapad",
        "sheet_name": "Северо-Запад",
        "title": "Баланс электрической энергии Северо-Запад",
        "group": GROUP_OES,
        "layout": "oes_standard",
        "territory": {"kind": "ues", "id": 410, "name": "ОЭС Северо-Запада"},
    }
    monkeypatch.setattr(balance_page_services, "get_ee_balance_sheets", lambda: [base_sheet])
    monkeypatch.setattr(
        balance_page_services, "_severo_zapad_region_sheets", lambda sheets: regions
    )
    monkeypatch.setattr(balance_page_services, "_ural_tyumen_energy_system", lambda sheets: None)
    monkeypatch.setattr(
        balance_page_services, "get_ee_balance_year_columns", lambda *args: [2026]
    )
    monkeypatch.setattr(
        balance_page_services, "get_ee_balance_year_features", lambda: {2026: "План"}
    )
    monkeypatch.setattr(
        balance_page_services, "get_ee_balance_filter_year_list", lambda: [2026]
    )
    monkeypatch.setattr(
        balance_page_services,
        "classify_ee_balance_generation_years",
        lambda years, year_features=None: ([], [2026]),
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_manual_generation_services.classify_ee_balance_generation_years",
        lambda years: ([], [2026]),
    )
    monkeypatch.setattr(
        balance_page_services, "load_ee_balance_manual_generation_inputs", lambda *args, **kwargs: {}
    )
    monkeypatch.setattr(
        balance_page_services, "power_balance_station_list_query", lambda *args: {}
    )
    monkeypatch.setattr(
        balance_page_services, "build_power_balance_station_list_url", lambda query: "#"
    )
    monkeypatch.setattr(
        balance_page_services, "hydro_year_for_balance_sheet", lambda *args: None
    )

    oes_context = build_ee_balance_table_context("severo-zapad", rounding_digits=1)
    child_context = build_ee_balance_table_context("res-2759", rounding_digits=1)
    center_context = build_ee_balance_table_context(
        SEVERO_ZAPAD_CENTER_SLUG, rounding_digits=1
    )

    assert oes_context is not None
    assert child_context is not None
    assert center_context is not None
    expected_subtab_slugs = [
        "severo-zapad",
        SEVERO_ZAPAD_CENTER_SLUG,
        "res-2759",
        "res-2775",
        "res-2806",
    ]
    for context in (oes_context, child_context, center_context):
        assert [tab["slug"] for tab in context["severo_zapad_subtabs"]] == expected_subtab_slugs
        assert context["tites_east_child_sheets"] == []
        assert context["first_row_active_slug"] == "severo-zapad"


def test_ees_chiim_uses_aggregated_generation_and_capacity():
    years = [2026]
    tables = build_ee_balance_tables(
        years,
        inputs={
            "severo-zapad": {"generation_aes": {2026: 10}, "installed_aes": {2026: 10}},
            "centr": {"generation_aes": {2026: 20}, "installed_aes": {2026: 20}},
            "srednyaya-volga": {"generation_aes": {2026: 4}, "installed_aes": {2026: 4}},
            "yug": {"generation_aes": {2026: 5}, "installed_aes": {2026: 5}},
            "ural": {"generation_aes": {2026: 6}, "installed_aes": {2026: 6}},
            "sibir": {"generation_aes": {2026: 7}, "installed_aes": {2026: 7}},
            "2-sz-ees-vostok": {"generation_aes": {2026: 8}, "installed_aes": {2026: 8}},
            "kaliningradskaya-sz-ees": {"generation_aes": {2026: 3}, "installed_aes": {2026: 3}},
        },
        rounding_digits=1,
    )
    assert _row_display(tables, "ees-rossii", "generation_aes", 2026) == "60"
    assert _row_display(tables, "ees-rossii", "installed_aes", 2026) == "60"
    assert _row_display(tables, "ees-rossii", "chiim_aes", 2026) == "1 000"
    assert _row_display(tables, "1-sz-ees", "chiim_aes", 2026) == "1 000"


def test_european_ees_aggregates_only_five_requested_oes():
    years = [2026]
    tables = {}
    for index, slug in enumerate(EUROPEAN_EES_SOURCE_SLUGS, start=1):
        child_key = f"flow_in_{slug}"
        rows = [
            {
                "key": "consumption",
                "formula": None,
                "year_values_raw": {2026: Decimal(index)},
                "year_values": {2026: str(index)},
            },
            {
                "key": "demand_total",
                "formula": {"terms": [{"row_key": "consumption"}]},
                "year_values_raw": {2026: Decimal(index)},
                "year_values": {2026: str(index)},
            },
            {
                "key": "flow_in",
                "formula": {"terms": [{"row_key": child_key}]},
                "year_values_raw": {2026: Decimal(index)},
                "year_values": {2026: str(index)},
            },
            {
                "key": child_key,
                "formula": None,
                "indent": 2,
                "is_group_child": True,
                "parent_group_key": "flow_in",
                "year_values_raw": {2026: Decimal(index)},
                "year_values": {2026: str(index)},
            },
        ]
        tables[slug] = {
            "sheet": {"slug": slug, "sheet_name": slug},
            "rows": rows,
        }
    tables["sibir"] = {
        "sheet": {"slug": "sibir"},
        "rows": [
            {
                "key": "consumption",
                "formula": None,
                "year_values_raw": {2026: Decimal(1000)},
                "year_values": {2026: "1000"},
            }
        ],
    }

    _append_european_ees_table(tables, years, rounding_digits=1)

    aggregate = tables[EUROPEAN_EES_SLUG]
    rows = {row["key"]: row for row in aggregate["rows"]}
    assert aggregate["sheet"]["source_slugs"] == EUROPEAN_EES_SOURCE_SLUGS
    assert rows["consumption"]["year_values_raw"][2026] == Decimal(15)
    assert rows["demand_total"]["year_values_raw"][2026] == Decimal(15)
    assert rows["flow_in"]["year_values_raw"][2026] == Decimal(15)
    assert all(rows[f"flow_in_{slug}"]["year_values_raw"][2026] == Decimal(index)
               for index, slug in enumerate(EUROPEAN_EES_SOURCE_SLUGS, start=1))
    assert rows["consumption"]["editable_values"] is False
    assert "sibir" not in aggregate["sheet"]["source_slugs"]

    _append_european_ees_table(
        tables,
        years,
        rounding_digits=1,
        slug=EUROPEAN_EES_WITHOUT_SOUTH_URAL_SLUG,
        sheet_name=EUROPEAN_EES_WITHOUT_SOUTH_URAL_NAME,
        source_slugs=EUROPEAN_EES_WITHOUT_SOUTH_URAL_SOURCE_SLUGS,
    )
    reduced_aggregate = tables[EUROPEAN_EES_WITHOUT_SOUTH_URAL_SLUG]
    reduced_rows = {row["key"]: row for row in reduced_aggregate["rows"]}
    assert reduced_aggregate["sheet"]["source_slugs"] == (
        EUROPEAN_EES_WITHOUT_SOUTH_URAL_SOURCE_SLUGS
    )
    assert reduced_rows["consumption"]["year_values_raw"][2026] == Decimal(7)
    assert EUROPEAN_EES_WITHOUT_SOUTH_URAL_SOURCE_SLUGS == (
        "severo-zapad",
        "centr",
        "srednyaya-volga",
    )


def test_european_ees_tab_precedes_synchronous_zones_and_keeps_period():
    from jinja2 import Environment, FileSystemLoader

    sheets = [
        {"slug": "ees-rossii", "sheet_name": "ЕЭС России", "group": GROUP_EES},
        {"slug": "1-sz-ees", "sheet_name": "1-я СЗ ЕЭС", "group": GROUP_SZ},
        {"slug": "2-sz-ees-vostok", "sheet_name": "2-я СЗ ЕЭС", "group": GROUP_SZ},
        {"slug": "severo-zapad", "sheet_name": "Северо-Запад", "group": GROUP_OES},
    ]
    nav_sheets = _ee_balance_navigation_sheets(sheets)
    groups = group_ee_balance_sheets(nav_sheets)
    ees_tabs = next(group["sheets"] for group in groups if group["group"] == GROUP_EES)
    assert [tab["slug"] for tab in ees_tabs] == [
        EES_RUSSIA_WITH_TITES_SLUG,
        "ees-rossii",
    ]
    sz_tabs = next(group["sheets"] for group in groups if group["group"] == GROUP_SZ)
    assert [tab["slug"] for tab in sz_tabs] == [
        EUROPEAN_EES_SLUG,
        SYNCHRONOUS_ZONES_SLUG,
        "1-sz-ees",
        "2-sz-ees-vostok",
    ]

    env = Environment(loader=FileSystemLoader("app/templates"), autoescape=True)
    env.globals["url_for"] = lambda _endpoint, **kwargs: (
        f"/energy_balance/ee_balance/{kwargs['slug']}/?"
        f"start_year={kwargs['start_year']}&end_year={kwargs['end_year']}"
        f"&rounding_digits={kwargs['rounding_digits']}"
    )
    html = env.get_template("energy_balance/ee_balance/_sheet_nav.html").render(
        current_slug=EUROPEAN_EES_SLUG,
        first_row_active_slug=EUROPEAN_EES_SLUG,
        sheet_groups=groups,
        european_ees_subtab_sheets=_european_ees_subtab_sheets(),
        synchronous_zone_subtab_sheets=balance_page_services._synchronous_zone_subtab_sheets(
            groups
        ),
        start_year=2018,
        end_year=2031,
        rounding_digits=1,
    )
    assert EES_RUSSIA_WITH_TITES_NAME in html
    assert html.index(EES_RUSSIA_WITH_TITES_NAME) < html.index("ЕЭС России")
    assert (
        f"/energy_balance/ee_balance/{EES_RUSSIA_WITH_TITES_SLUG}/?start_year=2018"
        "&amp;end_year=2031&amp;rounding_digits=1"
    ) in html
    assert "Европейская часть ЕЭС" in html
    assert html.index("Европейская часть ЕЭС") < html.index("1-я СЗ ЕЭС")
    assert SYNCHRONOUS_ZONES_NAME in html
    assert html.index(SYNCHRONOUS_ZONES_NAME) < html.index("1-я СЗ ЕЭС")
    assert "Синхронные зоны" in html
    assert EUROPEAN_EES_WITHOUT_SOUTH_URAL_NAME in html
    assert (
        f"/energy_balance/ee_balance/{EUROPEAN_EES_WITHOUT_SOUTH_URAL_SLUG}/"
        "?start_year=2018&amp;end_year=2031&amp;rounding_digits=1"
    ) in html
    assert (
        f"/energy_balance/ee_balance/{EUROPEAN_EES_SLUG}/?start_year=2018"
        "&amp;end_year=2031&amp;rounding_digits=1"
    ) in html


def test_ees_rossii_with_tites_uses_ees_and_tites_sources():
    sheets = [
        {
            "slug": "ees-rossii",
            "layout": "ees_rossii",
            "source_slugs": ("severo-zapad", "sibir"),
        },
        {"slug": "severo-zapad"},
        {"slug": "sibir"},
        {"slug": "oes-tites-east", "is_tites_east_hub": True, "skip_table": True},
        {
            "slug": "eu-tites-east-central",
            "parent_slug": "oes-tites-east",
            "station_capacity_breakdown": True,
        },
        {
            "slug": "oes-tites-sibir",
            "sheet_name": "ТИТЭС Сибири",
            "station_capacity_breakdown": True,
        },
        {"slug": "decentralized-system", "sheet_name": "Децентрализованная система"},
    ]

    source_slugs = _ees_rossii_with_tites_source_slugs(sheets)

    assert source_slugs == (
        "severo-zapad",
        "sibir",
        "eu-tites-east-central",
        "oes-tites-sibir",
    )


def test_ees_rossii_with_tites_context_builds_the_aggregate_sheet(monkeypatch):
    ees_sheet = {
        "slug": "ees-rossii",
        "sheet_name": "ЕЭС России",
        "title": "Баланс электрической энергии ЕЭС России",
        "group": GROUP_EES,
        "layout": "ees_rossii",
        "source_slugs": ("severo-zapad",),
    }
    tites_hub = {
        "slug": "tites-east",
        "sheet_name": "ТИТЭС Востока",
        "group": GROUP_OES,
        "is_tites_east_hub": True,
        "skip_table": True,
    }
    sheets = [
        ees_sheet,
        {"slug": "severo-zapad", "sheet_name": "Северо-Запад", "group": GROUP_OES},
        tites_hub,
        {
            "slug": "tites-east-child",
            "sheet_name": "Энергорайон ТИТЭС Востока",
            "group": "eu",
            "parent_slug": "tites-east",
            "station_capacity_breakdown": True,
        },
    ]
    monkeypatch.setattr(balance_page_services, "get_ee_balance_sheets", lambda: sheets)
    monkeypatch.setattr(
        balance_page_services, "get_ee_balance_year_columns", lambda *args: [2026]
    )
    monkeypatch.setattr(
        balance_page_services, "power_balance_station_list_query", lambda *args: {}
    )
    monkeypatch.setattr(
        balance_page_services, "build_power_balance_station_list_url", lambda query: "#"
    )
    monkeypatch.setattr(
        balance_page_services, "hydro_year_for_balance_sheet", lambda *args: None
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_ves_ses_page_services._can_edit_ves_ses_energy",
        lambda: False,
    )
    built = {}

    def build_tables(years, *, rounding_digits, sheets):
        aggregate = next(item for item in sheets if item["slug"] == EES_RUSSIA_WITH_TITES_SLUG)
        built["aggregate"] = aggregate
        return {aggregate["slug"]: {"sheet": aggregate, "rows": []}}

    monkeypatch.setattr(balance_page_services, "build_ee_balance_tables", build_tables)

    context = build_ee_balance_table_context(EES_RUSSIA_WITH_TITES_SLUG)

    assert context is not None
    assert built["aggregate"]["source_slugs"] == (
        "severo-zapad",
        "tites-east-child",
    )
    assert context["sheet"]["sheet_name"] == EES_RUSSIA_WITH_TITES_NAME
    assert context["sheet"]["title"] == f"{EE_BALANCE_TITLE_PREFIX} ЭЭС России"
    assert context["first_row_active_slug"] == EES_RUSSIA_WITH_TITES_SLUG

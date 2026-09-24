# -*- coding: utf-8 -*-
"""Юнит-тесты сборки строк ГИС ТЭК."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from app.ecology.services.gis_tek_constants import (
    PG_VALUE_COLUMN_GROUPS,
    REPORT_ZV,
    ZV_VALUE_COLUMN_GROUPS,
    ZV_VALUE_COLUMNS,
)
from app.ecology.services.gis_tek_page_services import (
    IDENTITY_COLUMNS,
    apply_zv_derived_metrics,
    attach_gis_tek_region_summaries,
    build_rows_from_equipment_groups,
    collect_numb_filter_choices,
    linked_generation_stations,
    metrics_are_empty,
    normalize_numb_filter,
    parse_show_empty_rows_arg,
    parse_show_totals_arg,
    sum_gaseous_and_liquid,
    sum_row_metrics,
)


def test_pg_value_column_groups_second_row_is_fuel_agnostic():
    for _group, cols in PG_VALUE_COLUMN_GROUPS:
        labels = [label for _attr, label in cols]
        assert labels == [
            "Расход топлива, тут",
            "Выбросы СО2 от сжигания топлива, т",
        ]


def test_zv_gaseous_group_spans_seven_columns_with_total():
    assert [label for attr, label in ZV_VALUE_COLUMNS if attr == "gaseous_and_liquid"] == [
        "всего"
    ]
    groups = list(ZV_VALUE_COLUMN_GROUPS)
    assert groups[0][0] == "всего"
    assert groups[0][1] == [("total", "")]
    assert groups[1][0] == "Твердые вещества"
    assert groups[1][1] == [("solid_substances", "")]
    group_label, cols = groups[2]
    assert group_label == "Газообразные и жидкие вещества"
    assert [attr for attr, _label in cols] == [
        "gaseous_and_liquid",
        "sulfur_dioxide",
        "carbon_monoxide",
        "nitrogen_oxides",
        "hydrocarbons",
        "voc",
        "other_gaseous_and_liquid",
    ]
    assert cols[0][1] == "всего"


def test_identity_columns_include_generation_station():
    keys = [key for key, _label, _num in IDENTITY_COLUMNS]
    assert keys.index("gis_tek_station_name") < keys.index("generation_station_name")
    assert keys.index("generation_station_name") < keys.index("equipment_group_name")
    labels = dict((key, label) for key, label, _num in IDENTITY_COLUMNS)
    assert labels["station_numb"] == "Код группы оборудования (numb)"


def test_linked_generation_stations_unique_and_sorted():
    group = SimpleNamespace(
        equipment_group_links_v2=[
            SimpleNamespace(
                equipment_group_set_station=SimpleNamespace(
                    database_version_id=1,
                    station=SimpleNamespace(id=20, name="  Беловская ГРЭС "),
                )
            ),
            SimpleNamespace(
                equipment_group_set_station=SimpleNamespace(
                    database_version_id=1,
                    station=SimpleNamespace(id=10, name="Абаканская ТЭЦ"),
                )
            ),
            SimpleNamespace(
                equipment_group_set_station=SimpleNamespace(
                    database_version_id=1,
                    station=SimpleNamespace(id=20, name="Беловская ГРЭС"),
                )
            ),
            SimpleNamespace(
                equipment_group_set_station=SimpleNamespace(
                    database_version_id=2,
                    station=SimpleNamespace(id=99, name="Другая версия"),
                )
            ),
        ]
    )
    stations = linked_generation_stations(group, version_id=1)
    assert [s["id"] for s in stations] == [10, 20]
    assert [s["name"] for s in stations] == ["Абаканская ТЭЦ", "Беловская ГРЭС"]


def test_linked_generation_stations_empty_without_group():
    assert linked_generation_stations(None) == []
    assert linked_generation_stations(SimpleNamespace(equipment_group_links_v2=[])) == []


def test_normalize_numb_filter_unique_ints():
    assert normalize_numb_filter(None) is None
    assert normalize_numb_filter([]) is None
    assert normalize_numb_filter(["1706", "1706", "612", "x"]) == [1706, 612]


def test_collect_numb_filter_choices_sorted():
    rows = [
        {"station_numb": 612},
        {"station_numb": None},
        {"station_numb": 1706},
        {"station_numb": 612},
    ]
    assert collect_numb_filter_choices(rows) == [612, 1706]


def test_sum_gaseous_and_liquid_adds_six_parts():
    assert sum_gaseous_and_liquid(None) is None
    assert sum_gaseous_and_liquid({}) is None
    assert sum_gaseous_and_liquid(
        {
            "sulfur_dioxide": None,
            "carbon_monoxide": None,
            "nitrogen_oxides": None,
            "hydrocarbons": None,
            "voc": None,
            "other_gaseous_and_liquid": None,
        }
    ) is None
    total = sum_gaseous_and_liquid(
        {
            "sulfur_dioxide": Decimal("1.5"),
            "carbon_monoxide": None,
            "nitrogen_oxides": "2",
            "hydrocarbons": Decimal("0.25"),
            "voc": Decimal("0.25"),
            "other_gaseous_and_liquid": Decimal("100"),
        }
    )
    assert total == Decimal("104.0")


def test_apply_zv_derived_metrics_overwrites_stored_total():
    values = apply_zv_derived_metrics(
        {
            "gaseous_and_liquid": Decimal("999"),
            "sulfur_dioxide": Decimal("10"),
            "carbon_monoxide": Decimal("20"),
            "nitrogen_oxides": Decimal("30"),
            "hydrocarbons": Decimal("40"),
            "voc": Decimal("50"),
            "other_gaseous_and_liquid": Decimal("6"),
        }
    )
    assert values["gaseous_and_liquid"] == Decimal("156")
    assert values["total"] == Decimal("156")

    with_solids = apply_zv_derived_metrics(
        {
            "solid_substances": Decimal("10"),
            "sulfur_dioxide": Decimal("1"),
            "carbon_monoxide": Decimal("2"),
            "nitrogen_oxides": Decimal("3"),
            "hydrocarbons": Decimal("4"),
            "voc": Decimal("5"),
            "other_gaseous_and_liquid": Decimal("6"),
        }
    )
    assert with_solids["gaseous_and_liquid"] == Decimal("21")
    assert with_solids["total"] == Decimal("31")


def test_build_rows_from_equipment_groups_lists_all_groups():
    group_with_data = SimpleNamespace(
        id=1,
        numb=1706,
        name="Группа А",
        regional_energy_system=None,
        equipment_group_links_v2=[],
        database_version_id=1,
    )
    group_without_data = SimpleNamespace(
        id=2,
        numb=612,
        name="Группа Б",
        regional_energy_system=None,
        equipment_group_links_v2=[],
        database_version_id=1,
    )
    report = SimpleNamespace(
        id=10,
        station_numb=1706,
        gis_tek_station_name="Станция ГИС",
        station_type="ТЭЦ",
        year_number=2022,
        database_version_id=1,
        equipment_group_id=1,
        solid_substances=Decimal("1"),
        sulfur_dioxide=Decimal("2"),
        carbon_monoxide=Decimal("3"),
        nitrogen_oxides=Decimal("4"),
        hydrocarbons=Decimal("5"),
        voc=Decimal("6"),
        other_gaseous_and_liquid=Decimal("7"),
        gaseous_and_liquid=None,
    )
    leftover = SimpleNamespace(
        id=11,
        station_numb=999,
        gis_tek_station_name="Только отчёт",
        station_type="КЭС",
        year_number=2022,
        database_version_id=1,
        equipment_group=None,
        equipment_group_id=None,
        solid_substances=None,
        sulfur_dioxide=None,
        carbon_monoxide=None,
        nitrogen_oxides=None,
        hydrocarbons=None,
        voc=None,
        other_gaseous_and_liquid=None,
        gaseous_and_liquid=None,
    )
    rows = build_rows_from_equipment_groups(
        [group_with_data, group_without_data],
        [report, leftover],
        REPORT_ZV,
        2022,
    )
    by_numb = {row["station_numb"]: row for row in rows}
    assert set(by_numb) == {1706, 612, 999}
    assert by_numb[1706]["gis_tek_station_name"] == "Станция ГИС"
    assert by_numb[1706]["metrics"]["gaseous_and_liquid"] == Decimal("27")
    assert by_numb[612]["equipment_group_name"] == "Группа Б"
    assert by_numb[612]["gis_tek_station_name"] == "—"
    assert by_numb[612]["metrics"]["gaseous_and_liquid"] is None
    assert by_numb[999]["gis_tek_station_name"] == "Только отчёт"


def test_parse_show_totals_and_empty_rows_args():
    assert parse_show_totals_arg({"show_totals": "1"}) is True
    assert parse_show_totals_arg({"show_totals": "0"}) is False
    assert parse_show_totals_arg({}) is False
    assert parse_show_empty_rows_arg({}) is False
    assert parse_show_empty_rows_arg({"show_empty_rows": "1"}) is True
    assert parse_show_empty_rows_arg({"show_empty_rows": "0"}) is False


def test_metrics_are_empty_treats_zero_as_empty():
    assert metrics_are_empty({}, REPORT_ZV) is True
    assert metrics_are_empty({"solid_substances": Decimal("0")}, REPORT_ZV) is True
    assert metrics_are_empty({"solid_substances": Decimal("1")}, REPORT_ZV) is False


def test_sum_row_metrics_recomputes_zv_derived():
    rows = [
        {
            "metrics": {
                "solid_substances": Decimal("1"),
                "sulfur_dioxide": Decimal("2"),
                "carbon_monoxide": Decimal("3"),
                "nitrogen_oxides": Decimal("4"),
                "hydrocarbons": Decimal("5"),
                "voc": Decimal("6"),
                "other_gaseous_and_liquid": Decimal("7"),
            }
        },
        {
            "metrics": {
                "solid_substances": Decimal("10"),
                "sulfur_dioxide": Decimal("1"),
                "carbon_monoxide": None,
                "nitrogen_oxides": None,
                "hydrocarbons": None,
                "voc": None,
                "other_gaseous_and_liquid": None,
            }
        },
    ]
    summed = sum_row_metrics(rows, REPORT_ZV)
    assert summed["solid_substances"] == Decimal("11")
    assert summed["sulfur_dioxide"] == Decimal("3")
    assert summed["gaseous_and_liquid"] == Decimal("28")
    assert summed["total"] == Decimal("39")


def test_attach_gis_tek_region_summaries_on_last_page_row():
    res_a = {
        "id": 1,
        "equipment_group_id": 1,
        "station_numb": 1,
        "gis_tek_station_name": "A",
        "year_number": 2022,
        "ues_name": "Центр",
        "res_name": "Москва",
        "metrics": {"solid_substances": Decimal("2"), "sulfur_dioxide": Decimal("3")},
    }
    res_b = {
        "id": 2,
        "equipment_group_id": 2,
        "station_numb": 2,
        "gis_tek_station_name": "B",
        "year_number": 2022,
        "ues_name": "Центр",
        "res_name": "Москва",
        "metrics": {"solid_substances": Decimal("5"), "sulfur_dioxide": Decimal("1")},
    }
    other = {
        "id": 3,
        "equipment_group_id": 3,
        "station_numb": 3,
        "gis_tek_station_name": "C",
        "year_number": 2022,
        "ues_name": "Сибирь",
        "res_name": "Красноярск",
        "metrics": {"solid_substances": Decimal("9")},
    }
    hierarchy = [
        {
            "ues_name": "Центр",
            "summary": None,
            "res_list": [
                {"res_name": "Москва", "rows": [res_a], "summary": None},
            ],
        }
    ]
    attach_gis_tek_region_summaries(
        hierarchy,
        [res_a, res_b, other],
        [res_a, res_b, other],
        [res_a],
        REPORT_ZV,
    )
    assert hierarchy[0]["res_list"][0]["summary"] is None
    assert hierarchy[0]["summary"] is None

    hierarchy = [
        {
            "ues_name": "Центр",
            "summary": None,
            "res_list": [
                {"res_name": "Москва", "rows": [res_b], "summary": None},
            ],
        }
    ]
    attach_gis_tek_region_summaries(
        hierarchy,
        [res_a, res_b, other],
        [res_a, res_b, other],
        [res_b],
        REPORT_ZV,
    )
    summary = hierarchy[0]["res_list"][0]["summary"]
    assert summary["label"] == "Москва, всего"
    assert summary["metrics"]["solid_substances"] == Decimal("7")
    assert summary["metrics"]["sulfur_dioxide"] == Decimal("4")
    assert summary["metrics"]["gaseous_and_liquid"] == Decimal("4")
    ues_summary = hierarchy[0]["summary"]
    assert ues_summary["label"] == "Центр, всего"
    assert ues_summary["metrics"]["solid_substances"] == Decimal("7")


def test_apply_gis_tek_territory_filters_by_station_and_company():
    from app.ecology.services.gis_tek_page_services import apply_gis_tek_territory_filters

    rows = [
        {
            "equipment_group_id": 1,
            "gis_tek_station_name": "Беловская ГРЭС",
            "generation_station_name": "Беловская ГРЭС",
            "generation_stations": [{"id": 10, "name": "Беловская ГРЭС"}],
            "equipment_group_name": "Группа А",
            "station_numb": 1706,
            "gen_company_name": "Сибирская генерирующая компания",
        },
        {
            "equipment_group_id": 2,
            "gis_tek_station_name": "Абаканская ТЭЦ",
            "generation_station_name": "Абаканская ТЭЦ",
            "generation_stations": [{"id": 11, "name": "Абаканская ТЭЦ"}],
            "equipment_group_name": "Группа Б",
            "station_numb": 612,
            "gen_company_name": "Другая компания",
        },
    ]
    by_station = apply_gis_tek_territory_filters(
        rows, {"station_name_filter": "белов"}
    )
    assert [row["equipment_group_id"] for row in by_station] == [1]
    by_company = apply_gis_tek_territory_filters(
        rows, {"gen_company_filter": "сибирская"}
    )
    assert [row["equipment_group_id"] for row in by_company] == [1]
    by_ids = apply_gis_tek_territory_filters(
        rows, {}, matching_eg_ids={2}
    )
    assert [row["equipment_group_id"] for row in by_ids] == [2]
    by_ved = apply_gis_tek_territory_filters(
        rows, {}, matching_ved_eg_ids={1}
    )
    assert [row["equipment_group_id"] for row in by_ved] == [1]


def test_parse_gis_tek_territory_filters_uses_q_fallback():
    from app.ecology.services.gis_tek_page_services import _parse_gis_tek_territory_filters

    parsed = _parse_gis_tek_territory_filters({"q": "Белово"})
    assert parsed["station_name_filter"] == "Белово"
    parsed_named = _parse_gis_tek_territory_filters(
        {"station_name_filter": "ТЭЦ", "q": "ignored"}
    )
    assert parsed_named["station_name_filter"] == "ТЭЦ"


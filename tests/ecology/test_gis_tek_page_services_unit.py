# -*- coding: utf-8 -*-
"""Юнит-тесты сборки строк ГИС ТЭК."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from app.ecology.services.gis_tek_constants import (
    PG_VALUE_COLUMN_GROUPS,
    REPORT_ZV,
    ZV_NORM_ATTR,
    ZV_NORM_DEFAULT_PARTS,
    ZV_NORM_PARTS,
    ZV_VALUE_COLUMN_GROUPS,
    ZV_VALUE_COLUMNS,
)
from app.ecology.services.gis_tek_page_services import (
    IDENTITY_COLUMNS,
    apply_gis_tek_header_filters,
    apply_zv_derived_metrics,
    attach_gis_tek_region_summaries,
    build_rows_from_equipment_groups,
    collect_numb_filter_choices,
    header_filter_choices,
    header_filter_selected,
    linked_generation_stations,
    metrics_are_empty,
    norm_zv_caption,
    norm_zv_options,
    normalize_numb_filter,
    parse_norm_zv_parts,
    parse_show_empty_rows_arg,
    parse_show_totals_arg,
    sum_gaseous_and_liquid,
    sum_norm_zv,
    sum_row_metrics,
)


def test_pg_value_column_groups_second_row_is_fuel_agnostic():
    for _group, cols in PG_VALUE_COLUMN_GROUPS:
        labels = [label for _attr, label in cols]
        assert labels == [
            "Расход топлива, т у.т.",
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
    assert keys.index("generation_station_name") < keys.index("station_affiliation")
    labels = dict((key, label) for key, label, _num in IDENTITY_COLUMNS)
    assert labels["station_numb"] == "Код группы оборудования (numb)"
    assert labels["station_affiliation"] == "Принадлежность"
    # «Группа оборудования (Топливо)» и «Тип станции» на страницах не показываются.
    assert "equipment_group_name" not in keys
    assert "station_type" not in keys


def test_numb_column_visible_only_for_admin_role():
    from app.ecology.services.gis_tek_page_services import (
        identity_columns_for,
        is_admin_user,
    )

    admin = SimpleNamespace(is_authenticated=True, role_names=["admin"])
    russian_admin = SimpleNamespace(is_authenticated=True, role_names=["Админ"])
    reader = SimpleNamespace(is_authenticated=True, role_names=["ecology-reader"])
    generation_admin = SimpleNamespace(is_authenticated=True, role_names=["Генерация-админ"])

    assert is_admin_user(admin) is True
    assert is_admin_user(russian_admin) is True
    assert is_admin_user(reader) is False
    assert is_admin_user(generation_admin) is False
    assert is_admin_user(None) is False

    admin_keys = [key for key, _label, _num in identity_columns_for(admin)]
    reader_keys = [key for key, _label, _num in identity_columns_for(reader)]
    assert admin_keys == [key for key, _label, _num in IDENTITY_COLUMNS]
    assert reader_keys == ["gis_tek_station_name", "generation_station_name", "station_affiliation"]
    assert [key for key, _label, _num in identity_columns_for(russian_admin)] == admin_keys


def test_resolve_year_picks_single_selected_year():
    from app.ecology.services.gis_tek_page_services import _resolve_year

    years = [2020, 2021, 2022, 2023]
    assert _resolve_year({"year": "2021"}, years, 2022) == 2021
    assert _resolve_year({}, years, 2022) == 2022
    # Ссылки с диапазоном от старой версии фильтра отдают год начала.
    assert _resolve_year({"start_year": "2020", "end_year": "2023"}, years, 2022) == 2020
    # Недоступный год заменяется ближайшим из списка фильтра.
    assert _resolve_year({"year": "2015"}, years, 2022) == 2020
    assert _resolve_year({"year": "2040"}, years, 2022) == 2023
    assert _resolve_year({"year": "abc"}, years, 2022) == 2022


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
    # «Принадлежность» не берётся из отчёта (там station_type = «ТЭЦ»), только из VED.
    assert by_numb[1706]["station_affiliation"] == "—"
    assert by_numb[999]["station_affiliation"] == "—"


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


def test_norm_zv_parts_are_zv_columns_without_totals():
    """Столбец «Нормируемые ЗВ» складывает все столбцы ЗВ, кроме «всего»."""
    assert [attr for attr, _label in ZV_VALUE_COLUMNS if _label != "всего"] == list(ZV_NORM_PARTS)
    assert set(ZV_NORM_DEFAULT_PARTS) <= set(ZV_NORM_PARTS)
    assert norm_zv_options() == [
        (attr, label) for attr, label in ZV_VALUE_COLUMNS if attr in ZV_NORM_PARTS
    ]
    assert "total" not in [attr for attr, _label in norm_zv_options()]
    assert "gaseous_and_liquid" not in [attr for attr, _label in norm_zv_options()]


def test_parse_norm_zv_parts_default_empty_and_ordered():
    assert parse_norm_zv_parts({}) == list(ZV_NORM_DEFAULT_PARTS)
    assert parse_norm_zv_parts({"year": "2024"}) == list(ZV_NORM_DEFAULT_PARTS)
    # Пустое значение — сознательно очищенный выбор.
    assert parse_norm_zv_parts({"norm_zv": ""}) == []
    # Порядок — как у столбцов ЗВ, повторы и неизвестные имена отбрасываются.
    assert parse_norm_zv_parts({"norm_zv": ["voc", "solid_substances", "voc"]}) == [
        "solid_substances",
        "voc",
    ]
    assert parse_norm_zv_parts({"norm_zv": "carbon_monoxide,nitrogen_oxides"}) == [
        "carbon_monoxide",
        "nitrogen_oxides",
    ]
    # Столбцы «всего» в сумму не входят.
    assert parse_norm_zv_parts({"norm_zv": ["total", "gaseous_and_liquid"]}) == []


def test_sum_norm_zv_adds_only_selected_parts():
    metrics = {
        "solid_substances": Decimal("1.5"),
        "sulfur_dioxide": Decimal("2"),
        "carbon_monoxide": None,
        "nitrogen_oxides": Decimal("0.5"),
        "total": Decimal("999"),
        "gaseous_and_liquid": Decimal("999"),
    }
    assert sum_norm_zv(metrics, ["solid_substances", "sulfur_dioxide"]) == Decimal("3.5")
    assert sum_norm_zv(metrics, ["carbon_monoxide"]) is None
    assert sum_norm_zv(metrics, []) is None
    assert sum_norm_zv(None, ["solid_substances"]) is None


def test_region_summary_gets_norm_zv_only_for_zv_page():
    def row(row_id, equipment_group_id, metrics):
        return {
            "id": row_id,
            "equipment_group_id": equipment_group_id,
            "station_numb": equipment_group_id,
            "gis_tek_station_name": f"Станция {equipment_group_id}",
            "year_number": 2024,
            "ues_name": "Центр",
            "res_name": "Москва",
            "metrics": metrics,
        }

    res_a = row(1, 1, {"solid_substances": Decimal("2"), "sulfur_dioxide": Decimal("3")})
    res_b = row(2, 2, {"solid_substances": Decimal("5"), "nitrogen_oxides": Decimal("1")})

    def hierarchy_for_last(row_b):
        return [
            {
                "ues_name": "Центр",
                "summary": None,
                "res_list": [{"res_name": "Москва", "rows": [row_b], "summary": None}],
            }
        ]

    hierarchy = hierarchy_for_last(res_b)
    attach_gis_tek_region_summaries(
        hierarchy,
        [res_a, res_b],
        [res_a, res_b],
        [res_b],
        REPORT_ZV,
        norm_zv_parts=["solid_substances", "nitrogen_oxides"],
    )
    summary = hierarchy[0]["res_list"][0]["summary"]
    assert summary["metrics"][ZV_NORM_ATTR] == Decimal("8")
    assert hierarchy[0]["summary"]["metrics"][ZV_NORM_ATTR] == Decimal("8")

    without_selection = hierarchy_for_last(res_b)
    attach_gis_tek_region_summaries(
        without_selection, [res_a, res_b], [res_a, res_b], [res_b], REPORT_ZV
    )
    assert ZV_NORM_ATTR not in without_selection[0]["res_list"][0]["summary"]["metrics"]


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


def test_header_filter_selected_choices_and_matching():
    rows = [
        {
            "gis_tek_station_name": "Беловская ГРЭС",
            "station_affiliation": "отрасль",
            "generation_stations": [
                {"id": 10, "name": "Беловская ГРЭС"},
                {"id": 12, "name": "ТЭЦ-1"},
            ],
        },
        {
            "gis_tek_station_name": "Абаканская ТЭЦ",
            "station_affiliation": "промпредприятие",
            "generation_stations": [{"id": 11, "name": "Абаканская ТЭЦ"}],
        },
        {
            "gis_tek_station_name": "—",
            "station_affiliation": "—",
            "generation_stations": [],
        },
    ]
    assert header_filter_choices(rows) == {
        "gis_tek_station_name": ["Абаканская ТЭЦ", "Беловская ГРЭС"],
        "generation_station_name": ["Абаканская ТЭЦ", "Беловская ГРЭС", "ТЭЦ-1"],
        "station_affiliation": ["отрасль", "промпредприятие"],
    }
    assert header_filter_selected(
        {"gis_tek_station_name_filter": "Беловская ГРЭС"}
    ) == {
        "gis_tek_station_name": "Беловская ГРЭС",
        "generation_station_name": "",
        "station_affiliation": "",
    }
    assert [
        row["gis_tek_station_name"]
        for row in apply_gis_tek_header_filters(
            rows, {"gis_tek_station_name": "Беловская ГРЭС"}
        )
    ] == ["Беловская ГРЭС"]
    assert [
        row["gis_tek_station_name"]
        for row in apply_gis_tek_header_filters(
            rows, {"generation_station_name": "ТЭЦ-1"}
        )
    ] == ["Беловская ГРЭС"]
    assert [
        row["gis_tek_station_name"]
        for row in apply_gis_tek_header_filters(
            rows, {"station_affiliation": "промпредприятие"}
        )
    ] == ["Абаканская ТЭЦ"]
    assert apply_gis_tek_header_filters(rows, {}) == rows


def test_parse_gis_tek_territory_filters_uses_q_fallback():
    from app.ecology.services.gis_tek_page_services import _parse_gis_tek_territory_filters

    parsed = _parse_gis_tek_territory_filters({"q": "Белово"})
    assert parsed["station_name_filter"] == "Белово"
    parsed_named = _parse_gis_tek_territory_filters(
        {"station_name_filter": "ТЭЦ", "q": "ignored"}
    )
    assert parsed_named["station_name_filter"] == "ТЭЦ"


def test_station_type_from_ved_labels_by_code():
    from app.ecology.services.gis_tek_page_services import station_type_from_ved

    assert station_type_from_ved(1) == "КЭС, отрасль"
    assert station_type_from_ved(2) == "ТЭЦ, отрасль"
    assert station_type_from_ved(3) == "ТЭЦ, промпредприятия"
    assert station_type_from_ved(4) == "КЭС, промпредприятия"
    for empty in (None, 0, 99, "", "x"):
        assert station_type_from_ved(empty) == "—"


def test_station_affiliation_follows_station_type():
    from app.ecology.services.gis_tek_page_services import station_affiliation

    assert station_affiliation("КЭС, отрасль") == "отрасль"
    assert station_affiliation("ТЭЦ, отрасль") == "отрасль"
    assert station_affiliation("ТЭЦ, промпредприятия") == "промпредприятие"
    assert station_affiliation("КЭС, промпредприятия") == "промпредприятие"
    assert station_affiliation("—") == "—"
    assert station_affiliation("ТЭЦ") == "—"


def test_build_rows_takes_station_type_from_ved_not_report():
    group = SimpleNamespace(
        id=7,
        numb=1706,
        name="Группа А",
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
        value=Decimal("1"),
    )
    rows = build_rows_from_equipment_groups(
        [group],
        [report],
        REPORT_ZV,
        2022,
        station_types={7: "ТЭЦ, промпредприятия"},
    )
    by_numb = {row["station_numb"]: row for row in rows}
    assert by_numb[1706]["station_type"] == "ТЭЦ, промпредприятия"
    assert by_numb[1706]["station_affiliation"] == "промпредприятие"

    without_ved = build_rows_from_equipment_groups([group], [report], REPORT_ZV, 2022)
    assert without_ved[0]["station_type"] == "—"
    assert without_ved[0]["station_affiliation"] == "—"


def test_station_types_by_equipment_group_skips_unmapped_ved(monkeypatch):
    import app.fuel.services.equipment_groups.equipment_group_fuel_params_services as svc
    from app.ecology.services.gis_tek_page_services import station_types_by_equipment_group

    captured = {}

    def fake_loader(ids, start_year=None, end_year=None, version_id=None):
        captured["ids"] = sorted(ids)
        captured["years"] = (start_year, end_year)
        captured["version_id"] = version_id
        return {
            1: [SimpleNamespace(ved=0), SimpleNamespace(ved=2)],
            2: [SimpleNamespace(ved=0)],
            3: [SimpleNamespace(ved=4)],
            4: [SimpleNamespace(ved=1)],
            5: [SimpleNamespace(ved=3)],
            6: [SimpleNamespace(ved=0)],
            7: [SimpleNamespace(ved=2)],
        }

    monkeypatch.setattr(svc, "load_equipment_group_fuel_params_for_groups", fake_loader)
    groups = [
        SimpleNamespace(id=1, numb=10, main=None),
        SimpleNamespace(id=2, numb=20, main=None),
        SimpleNamespace(id=3, numb=30, main=None),
        SimpleNamespace(id=4, numb=40, main=20),
        SimpleNamespace(id=5, numb=50, main=20),
        SimpleNamespace(id=6, numb=60, main=None),
        SimpleNamespace(id=7, numb=70, main=60),
    ]
    result = station_types_by_equipment_group(groups, 2023, 5)
    assert result == {
        1: "ТЭЦ, отрасль",
        3: "КЭС, промпредприятия",
        4: "КЭС, отрасль",
        5: "ТЭЦ, промпредприятия",
        # оболочка 60: тип берём у её единственного ребёнка
        6: "ТЭЦ, отрасль",
        7: "ТЭЦ, отрасль",
    }
    # оболочка 20: у детей разные типы (КЭС и ТЭЦ) — тип не определить
    assert 2 not in result
    assert captured == {
        "ids": [1, 2, 3, 4, 5, 6, 7],
        "years": (2023, 2023),
        "version_id": 5,
    }

    assert station_types_by_equipment_group(groups, None, 5) == {}
    assert station_types_by_equipment_group([], 2023, 5) == {}


def test_norm_zv_caption_lists_only_selected_parts():
    assert norm_zv_caption(["solid_substances", "sulfur_dioxide"]) == (
        "Нормируемые ЗВ (Твердые вещества + диоксид серы)"
    )
    assert norm_zv_caption([]) == "Нормируемые ЗВ (слагаемые не выбраны)"


def test_drop_float_noise_keeps_significant_digits():
    from app.common.services.help_services import format_decimal_for_display
    from app.ecology.services.ecology_decimal_helpers import drop_float_noise

    # Хвост из double исходного Excel/Access — артефакт, а не данные.
    assert drop_float_noise(Decimal("105.1000000000000100")) == Decimal("105.1")
    assert drop_float_noise(Decimal("1844.7233930000002")) == Decimal("1844.723393")
    assert drop_float_noise(Decimal("446.5270000000000400")) == Decimal("446.527")
    # Значение короче предела не меняется — в т.ч. все 15 знаков.
    assert drop_float_noise(Decimal("1.02963561999219")) == Decimal("1.02963561999219")
    assert drop_float_noise(Decimal("863585")) == Decimal("863585")
    assert drop_float_noise(None) is None
    assert drop_float_noise("") is None
    # То, что видит пользователь при «Не округлять».
    assert format_decimal_for_display(
        drop_float_noise(Decimal("991895.2000000001000000")), 0
    ) == "991 895,2"


def test_drop_float_noise_in_hierarchy_covers_rows_and_summaries():
    from app.ecology.services.gis_tek_page_services import (
        drop_float_noise_in_hierarchy,
    )

    row = {
        "metrics": {
            "solid_substances": Decimal("3.1300000000000003"),
            "sulfur_dioxide": Decimal("1.522"),
        }
    }
    res_summary = {
        "label": "Москва, всего",
        "metrics": {"solid_substances": Decimal("4.6520000000000003")},
    }
    ues_summary = {
        "label": "Центр, всего",
        "metrics": {"solid_substances": Decimal("8.8100000000000001")},
    }
    hierarchy = [
        {
            "ues_name": "Центр",
            "summary": ues_summary,
            "res_list": [{"res_name": "Москва", "rows": [row], "summary": res_summary}],
        }
    ]

    drop_float_noise_in_hierarchy(hierarchy)

    assert row["metrics"]["solid_substances"] == Decimal("3.13")
    assert row["metrics"]["sulfur_dioxide"] == Decimal("1.522")
    assert res_summary["metrics"]["solid_substances"] == Decimal("4.652")
    assert ues_summary["metrics"]["solid_substances"] == Decimal("8.81")
    # Сводки без метрик и пустая иерархия не ломают обход.
    drop_float_noise_in_hierarchy([{"ues_name": "x", "summary": None, "res_list": []}])
    drop_float_noise_in_hierarchy([])


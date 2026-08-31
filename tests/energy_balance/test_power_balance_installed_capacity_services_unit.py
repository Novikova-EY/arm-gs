# -*- coding: utf-8 -*-
"""Юнит-тесты установленной мощности для балансов (типы станций и территория)."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from app.energy_balance.services.power_balance_installed_capacity_services import (
    accumulate_q4_p_ust_by_territory,
    available_row_key,
    _build_station_capacity_items,
    _constraints_year_values,
    _groups_from_station_types,
    _machine_capacity_label,
    _match_named_object,
    get_power_balance_station_type_groups,
    load_power_balance_installed_capacity_inputs,
    resolve_station_balance_territory,
    station_capacity_breakdown_to_inputs,
    station_capacity_row_key,
)
from app.energy_balance.services.power_balance_page_services import build_power_balance_tables


def _st(type_id: int, name: str, display_order: int | None = None):
    return SimpleNamespace(id=type_id, name=name, display_order=display_order)


def test_groups_skip_unspecified_merge_ves_ses_keep_display_order():
    groups = _groups_from_station_types(
        [
            _st(0, "не указано", 0),
            _st(1, "АЭС", 1),
            _st(2, "ВЭС", 2),
            _st(3, "ГЭС", 3),
            _st(4, "СЭС", 4),
            _st(5, "ТЭС", 5),
        ]
    )
    assert [group["key"] for group in groups] == [
        "installed_aes",
        "installed_ses_ves",
        "installed_ges",
        "installed_tes",
    ]
    ses_ves = next(group for group in groups if group["key"] == "installed_ses_ves")
    assert ses_ves["label"] == "СЭС, ВЭС"
    assert ses_ves["type_ids"] == (2, 4)


def test_groups_gaes_not_confused_with_ges():
    groups = _groups_from_station_types([_st(10, "ГАЭС", 1), _st(11, "ГЭС", 2)])
    assert [group["key"] for group in groups] == ["installed_gaes", "installed_ges"]


def test_default_groups_when_refdata_empty():
    with patch(
        "app.energy_balance.services.power_balance_installed_capacity_services.get_station_type_list_full",
        return_value=[],
    ):
        keys = [group["key"] for group in get_power_balance_station_type_groups()]
    assert keys == [
        "installed_aes",
        "installed_ges",
        "installed_gaes",
        "installed_tes",
        "installed_snee",
        "installed_ses_ves",
    ]


def test_match_ues_center_excludes_northwest():
    objects = [
        SimpleNamespace(id=1, name="ОЭС Северо-Запада", name_full="ОЭС Северо-Запада"),
        SimpleNamespace(id=2, name="ОЭС Центра", name_full="ОЭС Центра"),
        SimpleNamespace(id=0, name="не указано", name_full="не указано"),
    ]
    matched = _match_named_object(objects, needles=("центр",), exclude=("северо",))
    assert matched.id == 2
    matched_nw = _match_named_object(objects, needles=("северо-запад",))
    assert matched_nw.id == 1


def test_load_inputs_from_ues_and_sync_area_aggregates():
    types = [_st(1, "АЭС", 1), _st(2, "ТЭС", 2), _st(3, "ВЭС", 3), _st(4, "СЭС", 4)]
    ues_list = [SimpleNamespace(id=10, name="ОЭС Центра", name_full="ОЭС Центра")]
    sa_list = [SimpleNamespace(id=7, name="Калининградская СЗ", number="3")]
    ues_p_ust = {
        10: {
            1: {2026: Decimal("40")},
            2: {2026: Decimal("30")},
            3: {2026: Decimal("5")},
            4: {2026: Decimal("7")},
        }
    }
    ues_p_rasp = {
        10: {
            1: {2026: Decimal("35")},
            2: {2026: Decimal("25")},
            3: {2026: Decimal("4")},
            4: {2026: Decimal("6")},
        }
    }
    sa_p_ust = {7: {2: {2026: Decimal("500")}}}
    sa_p_rasp = {7: {2: {2026: Decimal("475")}}}
    aggregated = {
        "aggregate_union_energy_systems_by_station_types": {
            "aggregated": {"p_ust": ues_p_ust, "p_rasp": ues_p_rasp}
        },
        "aggregate_synchronous_areas_by_station_types": {
            "aggregated": {"p_ust": sa_p_ust, "p_rasp": sa_p_rasp}
        },
        "aggregate_power_by_union_energy_systems": {
            "aggregated": {
                "p_ust": {10: {2026: Decimal("82")}},
                "p_ogr": {10: {2026: Decimal("15")}},
                "p_rasp": {10: {2026: Decimal("67")}},
            }
        },
        "aggregate_power_by_synchronous_areas": {
            "aggregated": {
                "p_ust": {7: {2026: Decimal("500")}},
                "p_ogr": {7: {2026: Decimal("25")}},
                "p_rasp": {7: {2026: Decimal("475")}},
            }
        },
    }
    with patch(
        "app.energy_balance.services.power_balance_installed_capacity_services.get_station_type_list_full",
        return_value=types,
    ), patch(
        "app.energy_balance.services.power_balance_installed_capacity_services.get_union_energy_system_list_full",
        return_value=ues_list,
    ), patch(
        "app.energy_balance.services.power_balance_installed_capacity_services.get_synchronous_area_list_full",
        return_value=sa_list,
    ), patch(
        "app.generation.services.station_services.station_services.get_filtered_station_ids",
        return_value=[101],
    ), patch(
        "app.generation.services.station_services.aggregation_station_services.aggregation_rows.get_full_aggregation_rows",
        return_value=["row"],
    ), patch(
        "app.generation.services.station_services.aggregation_station_services.optimized_aggregation.aggregate_all_at_once",
        return_value=aggregated,
    ), patch(
        "app.energy_balance.services.power_balance_installed_capacity_services._load_q4_commissioning_p_ust_maps",
        return_value={
            "ues": {10: {2026: Decimal("4")}},
            "sa": {7: {2026: Decimal("1")}},
        },
    ):
        inputs = load_power_balance_installed_capacity_inputs([2026])

    assert inputs["centr"]["installed_aes"][2026] == Decimal("40")
    assert inputs["centr"]["installed_tes"][2026] == Decimal("30")
    assert inputs["centr"]["installed_ses_ves"][2026] == Decimal("12")
    assert inputs["centr"]["available_aes"][2026] == Decimal("35")
    assert inputs["centr"]["available_tes"][2026] == Decimal("25")
    assert inputs["centr"]["available_ses_ves"][2026] == Decimal("10")
    assert inputs["centr"]["constraints"][2026] == Decimal("15")
    assert inputs["centr"]["commissioning_after_max"][2026] == Decimal("4")
    assert inputs["kaliningradskaya-sz-ees"]["installed_tes"][2026] == Decimal("500")
    assert inputs["kaliningradskaya-sz-ees"]["available_tes"][2026] == Decimal("475")
    assert inputs["kaliningradskaya-sz-ees"]["constraints"][2026] == Decimal("25")
    assert inputs["kaliningradskaya-sz-ees"]["commissioning_after_max"][2026] == Decimal("1")


def test_constraints_use_p_ogr_or_p_ust_minus_p_rasp():
    years = [2026, 2027]
    assert _constraints_year_values(
        {2026: Decimal("11")},
        {2026: Decimal("40")},
        {2026: Decimal("29")},
        years,
    ) == {2026: Decimal("11"), 2027: Decimal("0")}
    assert _constraints_year_values(
        {2026: Decimal("0")},
        {2026: Decimal("40"), 2027: Decimal("50")},
        {2026: Decimal("29"), 2027: Decimal("44")},
        years,
    ) == {2026: Decimal("11"), 2027: Decimal("6")}


def test_resolve_station_territory_prefers_direct_res():
    ues_id, sa_id = resolve_station_balance_territory(
        id_regional_energy_system=5,
        id_regional_district=9,
        res_to_ues={5: 10},
        district_to_ues={9: 11},
        district_to_sa={9: 7},
    )
    assert ues_id == 10
    assert sa_id == 7


def test_q4_p_ust_sums_by_ues_and_sa_and_dedupes_machine_year():
    rows = [
        SimpleNamespace(
            id=1,
            machine_id=100,
            year=2026,
            p_ust=Decimal("10"),
            id_regional_energy_system=5,
            id_regional_district=9,
        ),
        SimpleNamespace(
            id=3,
            machine_id=100,
            year=2026,
            p_ust=Decimal("12"),
            id_regional_energy_system=5,
            id_regional_district=9,
        ),
        SimpleNamespace(
            id=2,
            machine_id=101,
            year=2027,
            p_ust=Decimal("4"),
            id_regional_energy_system=None,
            id_regional_district=9,
        ),
        SimpleNamespace(
            id=4,
            machine_id=102,
            year=2026,
            p_ust=Decimal("8"),
            id_regional_energy_system=6,
            id_regional_district=20,
        ),
    ]
    maps = accumulate_q4_p_ust_by_territory(
        rows,
        res_to_ues={5: 10, 6: 11},
        district_to_ues={9: 10, 20: 11},
        district_to_sa={9: 7, 20: 8},
    )
    assert maps["ues"][10][2026] == Decimal("12")
    assert maps["ues"][10][2027] == Decimal("4")
    assert maps["ues"][11][2026] == Decimal("8")
    assert maps["sa"][7][2026] == Decimal("12")
    assert maps["sa"][7][2027] == Decimal("4")
    assert maps["sa"][8][2026] == Decimal("8")


def test_page_uses_station_list_p_ust_for_oes_and_formulas_for_ees():
    years = [2026]
    tables = build_power_balance_tables(
        years,
        inputs={
            "centr": {
                "installed_aes": {2026: 20},
                "installed_tes": {2026: 10},
            },
            "severo-zapad": {"installed_aes": {2026: 10}},
            "srednyaya-volga": {"installed_aes": {2026: 4}},
            "yug": {"installed_aes": {2026: 5}},
            "ural": {"installed_aes": {2026: 6}},
            "sibir": {"installed_aes": {2026: 7}},
            "2-sz-ees-vostok": {"installed_aes": {2026: 8}},
        },
    )
    centr_aes = next(row for row in tables["centr"]["rows"] if row["key"] == "installed_aes")
    centr_total = next(row for row in tables["centr"]["rows"] if row["key"] == "installed_total")
    assert centr_aes["year_values"][2026] == "20"
    assert centr_total["year_values"][2026] == "30"
    ees_aes = next(row for row in tables["ees-rossii"]["rows"] if row["key"] == "installed_aes")
    assert ees_aes["year_values"][2026] == "60"


def test_page_constraints_use_station_list_totals_and_sum_for_ees():
    years = [2026]
    tables = build_power_balance_tables(
        years,
        inputs={
            "centr": {"constraints": {2026: 15}},
            "severo-zapad": {"constraints": {2026: 4}},
            "srednyaya-volga": {"constraints": {2026: 3}},
            "yug": {"constraints": {2026: 2}},
            "ural": {"constraints": {2026: 6}},
            "sibir": {"constraints": {2026: 7}},
            "2-sz-ees-vostok": {"constraints": {2026: 8}},
            "kaliningradskaya-sz-ees": {"constraints": {2026: 25}},
        },
    )
    centr = next(row for row in tables["centr"]["rows"] if row["key"] == "constraints")
    kal = next(row for row in tables["kaliningradskaya-sz-ees"]["rows"] if row["key"] == "constraints")
    ees = next(row for row in tables["ees-rossii"]["rows"] if row["key"] == "constraints")
    sz1 = next(row for row in tables["1-sz-ees"]["rows"] if row["key"] == "constraints")
    assert centr["year_values"][2026] == "15"
    assert kal["year_values"][2026] == "25"
    # ЕЭС: 15+4+3+2+6+7+8 = 45 (без Калининграда)
    assert ees["year_values"][2026] == "45"
    # 1-я СЗ: 15+4+3+2+6+7 − 25 = 12
    assert sz1["year_values"][2026] == "12"


def test_page_commissioning_after_max_sums_for_ees_and_sz1():
    years = [2026]
    tables = build_power_balance_tables(
        years,
        inputs={
            "centr": {"commissioning_after_max": {2026: 4}},
            "severo-zapad": {"commissioning_after_max": {2026: 1}},
            "srednyaya-volga": {"commissioning_after_max": {2026: 2}},
            "yug": {"commissioning_after_max": {2026: 3}},
            "ural": {"commissioning_after_max": {2026: 5}},
            "sibir": {"commissioning_after_max": {2026: 6}},
            "2-sz-ees-vostok": {"commissioning_after_max": {2026: 7}},
            "kaliningradskaya-sz-ees": {"commissioning_after_max": {2026: 1}},
        },
    )
    centr = next(row for row in tables["centr"]["rows"] if row["key"] == "commissioning_after_max")
    ees = next(row for row in tables["ees-rossii"]["rows"] if row["key"] == "commissioning_after_max")
    sz1 = next(row for row in tables["1-sz-ees"]["rows"] if row["key"] == "commissioning_after_max")
    assert centr["year_values"][2026] == "4"
    # ЕЭС: 4+1+2+3+5+6+7 = 28
    assert ees["year_values"][2026] == "28"
    # 1-я СЗ: 4+1+2+3+5+6 − 1 = 20
    assert sz1["year_values"][2026] == "20"


def test_machine_capacity_label_prefers_number_and_name():
    assert _machine_capacity_label("1", "Турбина") == "1 Турбина"
    assert _machine_capacity_label("1", "ст. №1 Турбина") == "ст. №1 Турбина"
    assert _machine_capacity_label("8", "LM6000 PF Sprint") == "8 LM6000 PF Sprint"
    assert _machine_capacity_label("1", "ПТ-60-130/13") == "1 ПТ-60-130/13"
    assert _machine_capacity_label("3", "Т-110/120-130") == "3 Т-110/120-130"
    assert _machine_capacity_label("6", "LM6000 PF Sprint") == "6 LM6000 PF Sprint"
    assert _machine_capacity_label("8", "8 LM6000 PF Sprint") == "8 LM6000 PF Sprint"
    assert _machine_capacity_label("", "Турбина") == "Турбина"
    assert _machine_capacity_label(None, None) == "Агрегат"


def test_available_row_key_replaces_installed_prefix():
    assert available_row_key("installed_aes") == "available_aes"
    assert available_row_key("installed_station_10") == "available_station_10"
    assert available_row_key("installed_machine_1") == "available_machine_1"
    assert available_row_key("other") == "available_other"


def test_build_station_capacity_items_groups_machines_and_sums_years():
    rows = [
        SimpleNamespace(
            station_id=10,
            station_name="Станция А",
            machine_id=1,
            machine_number="2",
            machine_name="Турбина",
            year=2026,
            p_ust=Decimal("4"),
            p_rasp=Decimal("3"),
        ),
        SimpleNamespace(
            station_id=10,
            station_name="Станция А",
            machine_id=2,
            machine_number="1",
            machine_name="Турбина",
            year=2026,
            p_ust=Decimal("6"),
            p_rasp=Decimal("5"),
        ),
        SimpleNamespace(
            station_id=11,
            station_name="Станция Б",
            machine_id=3,
            machine_number="1",
            machine_name="Г-1",
            year=2026,
            p_ust=Decimal("8"),
        ),
        SimpleNamespace(
            station_id=11,
            station_name="Станция Б",
            machine_id=3,
            machine_number="1",
            machine_name="Г-1",
            year=2027,
            p_ust=Decimal("9"),
        ),
    ]
    items = _build_station_capacity_items(rows, [2026, 2027])
    assert [item["label"] for item in items] == ["Станция А", "Станция Б"]
    first = items[0]
    assert first["key"] == station_capacity_row_key(10)
    assert [machine["label"] for machine in first["machines"]] == ["1 Турбина", "2 Турбина"]
    assert first["year_values"][2026] == Decimal("10")
    assert first["rasp_year_values"][2026] == Decimal("8")
    assert first["year_values"][2027] == Decimal("0")
    second = items[1]
    assert second["year_values"][2026] == Decimal("8")
    assert second["year_values"][2027] == Decimal("9")
    inputs = station_capacity_breakdown_to_inputs({"oes-318": {"stations": items}})
    assert inputs["oes-318"]["installed_machine_1"][2026] == Decimal("4")
    assert inputs["oes-318"]["installed_machine_2"][2026] == Decimal("6")
    assert inputs["oes-318"]["available_machine_1"][2026] == Decimal("3")
    assert inputs["oes-318"]["available_machine_2"][2026] == Decimal("5")
    assert "installed_station_10" not in inputs["oes-318"]
    assert "available_station_10" not in inputs["oes-318"]


def test_machine_labels_keep_number_even_if_it_appears_inside_model_name():
    rows = [
        SimpleNamespace(
            station_id=1,
            station_name="Южно-Сахалинская ТЭЦ-1",
            machine_id=10,
            machine_number="6",
            machine_name="LM6000 PF Sprint",
            year=2026,
            p_ust=Decimal("1"),
        ),
        SimpleNamespace(
            station_id=1,
            station_name="Южно-Сахалинская ТЭЦ-1",
            machine_id=11,
            machine_number="1",
            machine_name="ПТ-60-130/13",
            year=2026,
            p_ust=Decimal("1"),
        ),
        SimpleNamespace(
            station_id=1,
            station_name="Южно-Сахалинская ТЭЦ-1",
            machine_id=12,
            machine_number="3",
            machine_name="Т-110/120-130",
            year=2026,
            p_ust=Decimal("1"),
        ),
        SimpleNamespace(
            station_id=1,
            station_name="Южно-Сахалинская ТЭЦ-1",
            machine_id=13,
            machine_number="2",
            machine_name="Т-55/60-130",
            year=2026,
            p_ust=Decimal("1"),
        ),
    ]
    items = _build_station_capacity_items(rows, [2026])
    labels = [machine["label"] for machine in items[0]["machines"]]
    assert labels == [
        "1 ПТ-60-130/13",
        "2 Т-55/60-130",
        "3 Т-110/120-130",
        "6 LM6000 PF Sprint",
    ]


def test_assign_chukotka_stations_to_energy_units_by_name():
    from app.energy_balance.services.power_balance_installed_capacity_services import (
        assign_station_ids_for_shared_res_eu,
    )

    stations = [
        (1, "Анадырская ТЭЦ"),
        (2, "Газомоторная ТЭЦ (г. Анадырь)"),
        (3, "Чаунская ТЭЦ"),
        (4, "Билибинская АЭС"),
        (5, "ПАТЭС Академик Ломоносов"),
        (6, "Новая ТЭС в Чаун-Билибинском энергорайоне"),
    ]
    names = {
        344: "Чаун-Билибинский энергорайон",
        345: "Анадырский энергорайон",
    }
    anadyr = assign_station_ids_for_shared_res_eu(stations, 345, names)
    chaun = assign_station_ids_for_shared_res_eu(stations, 344, names)
    assert anadyr == [1, 2]
    assert chaun == [3, 4, 5, 6]

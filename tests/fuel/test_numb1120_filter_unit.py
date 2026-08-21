# -*- coding: utf-8 -*-
from types import SimpleNamespace

from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
    collect_numb1120_filter_choices,
    displayed_numb1120,
    filter_fuel_param_rows_by_numb1120,
    normalize_numb1120_filter,
)
from app.generation.services.station_services.filters_services import _parse_int_list_filter


def test_parse_int_list_filter_splits_and_dedupes():
    assert _parse_int_list_filter(["12, 34; 56", "34", " 78 "]) == [12, 34, 56, 78]
    assert _parse_int_list_filter([]) == []
    assert _parse_int_list_filter(["abc", ""]) == []


def test_normalize_and_displayed_numb1120():
    assert normalize_numb1120_filter(["10", " 10 ", "20"]) == [10, 20]
    assert normalize_numb1120_filter([]) is None

    eg = SimpleNamespace(id=1, numb=100)
    param = SimpleNamespace(numb1120=200)
    assert displayed_numb1120(eg, param) == 200
    assert displayed_numb1120(eg, SimpleNamespace(numb1120=None)) == 100
    assert displayed_numb1120(eg, None) == 100


def test_filter_rows_keeps_all_years_of_matching_group():
    eg1 = SimpleNamespace(id=1, numb=111)
    eg2 = SimpleNamespace(id=2, numb=222)
    rows = [
        (eg1, SimpleNamespace(numb1120=111, year_number=2024)),
        (eg1, SimpleNamespace(numb1120=111, year_number=2025)),
        (eg2, SimpleNamespace(numb1120=222, year_number=2024)),
    ]
    assert collect_numb1120_filter_choices(rows) == [111, 222]
    filtered = filter_fuel_param_rows_by_numb1120(rows, [111])
    assert [eg.id for eg, _p in filtered] == [1, 1]
    by_param = filter_fuel_param_rows_by_numb1120(
        [(eg2, SimpleNamespace(numb1120=333))],
        [333],
    )
    assert len(by_param) == 1


def test_apply_numb1120_filter_to_eg_param_rows_collects_then_filters():
    from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
        apply_numb1120_filter_to_eg_param_rows,
    )

    eg1 = SimpleNamespace(id=1, numb=111)
    eg2 = SimpleNamespace(id=2, numb=222)
    rows = [
        (eg1, SimpleNamespace(numb1120=111)),
        (eg2, SimpleNamespace(numb1120=222)),
    ]
    filtered, choices = apply_numb1120_filter_to_eg_param_rows(
        rows, {"numb1120_filter": [111]}
    )
    assert choices == [111, 222]
    assert [eg.id for eg, _p in filtered] == [1]

    unfiltered, choices2 = apply_numb1120_filter_to_eg_param_rows(rows, {})
    assert choices2 == [111, 222]
    assert len(unfiltered) == 2


def test_suppress_aggregate_rows_clears_totals():
    from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
        apply_suppress_aggregate_rows_to_hierarchy,
        should_suppress_aggregate_rows_for_filters,
    )

    assert should_suppress_aggregate_rows_for_filters({"numb1120_filter": [111]})
    assert not should_suppress_aggregate_rows_for_filters({})

    hierarchy = [
        {
            "ues_list": [
                {
                    "res_list": [
                        {
                            "res_summary": {"nust": 10},
                            "station_blocks": [
                                {
                                    "group_blocks": [
                                        {
                                            "is_composite_total_row": True,
                                            "use_station_summary": True,
                                        },
                                        {"is_composite_total_row": False},
                                    ]
                                }
                            ],
                            "group_blocks": [],
                        }
                    ]
                }
            ]
        }
    ]
    apply_suppress_aggregate_rows_to_hierarchy(hierarchy)
    res = hierarchy[0]["ues_list"][0]["res_list"][0]
    assert res["hide_res_summary"] is True
    assert res["res_summary"] == {}
    gbs = res["station_blocks"][0]["group_blocks"]
    assert gbs[0]["is_composite_total_row"] is False
    assert gbs[0]["use_station_summary"] is False
    assert len(res["group_blocks"]) == 2

from types import SimpleNamespace

import pytest
from flask import Flask

from app.fuel.services.equipment_groups.equipment_group_flags import (
    MASKED_FLAG_FILTER_VALUE,
    equipment_group_flag_label,
)
from werkzeug.datastructures import MultiDict

from app.fuel.services.stations.stations_equipment_groups_services import (
    _filter_equipment_group_blocks_by_flags,
)
from app.generation.services.station_services.filters_services import (
    extract_filters_from_args,
    extract_filters_from_form,
    has_any_filters,
)


@pytest.mark.parametrize("field,value,expected", [
    ("d", None, "новая"),
    ("d", "", "новая"),
    ("d", 0, "новая"),
    ("d", "0", "новая"),
    ("d", 1, "действующая"),
    ("d", "1", "действующая"),
    ("d", 9, "демонтирована"),
    ("d", "9", "демонтирована"),
    ("r", None, "новая станция"),
    ("r", "", "новая станция"),
    ("r", 0, "новая станция"),
    ("r", "0", "новая станция"),
    ("r", 1, "действующая группа оборудования"),
    ("r", "1", "действующая группа оборудования"),
    ("r", 2, "новая группа оборудования действующей станции"),
    ("r", "2", "новая группа оборудования действующей станции"),
    ("r", 9, "демонтирована"),
    ("r", "9", "демонтирована"),
])
def test_flag_labels(field, value, expected):
    assert equipment_group_flag_label(field, value) == expected


def _block(group_id, d, r, stations=(None,)):
    return {
        "equipment_group": SimpleNamespace(id=group_id, d=d, r=r),
        "station_entries": [
            {
                "station": station,
                "station_rowspan": 2,
                "links": [{"equipment_group_type": None, "machines": [None, None]}],
            }
            for station in stations
        ],
    }


def test_flag_filters_parse_multiple_values_and_keep_blank_selection(monkeypatch):
    monkeypatch.setattr(
        "app.generation.services.station_services.filters_services.get_filter_start_year",
        lambda: 2026,
    )
    monkeypatch.setattr(
        "app.generation.services.station_services.filters_services.get_filter_end_year",
        lambda: 2042,
    )
    args = MultiDict([
        ("equipment_group_d_filter", "0"),
        ("equipment_group_d_filter", "1"),
        ("equipment_group_r_filter", "1, 2"),
        ("equipment_group_r_filter", "invalid"),
    ])
    with Flask(__name__).test_request_context():
        for extract in (extract_filters_from_args, extract_filters_from_form):
            filters = extract(args)
            assert filters["equipment_group_d_filter"] == [0, 1]
            assert filters["equipment_group_r_filter"] == [1, 2]
    assert has_any_filters(MultiDict([("equipment_group_d_filter", "0")]))
    assert has_any_filters(MultiDict([("equipment_group_r_filter", "2")]))


def test_flag_filters_combine_columns_and_keep_all_available_choices():
    blocks = [_block(1, 1, 2), _block(2, 1, 1), _block(3, 0, 2)]
    result, choices = _filter_equipment_group_blocks_by_flags(
        blocks, {"equipment_group_d_filter": [1], "equipment_group_r_filter": [2]}
    )
    assert [block["equipment_group"].id for block in result] == [1]
    assert choices == {
        "d": [(0, "новая"), (1, "действующая")],
        "r": [(1, "действующая группа оборудования"), (2, "новая группа оборудования действующей станции")],
    }
    result, _ = _filter_equipment_group_blocks_by_flags(
        blocks, {"equipment_group_r_filter": [1, 2]}
    )
    assert len(result) == 3


def test_new_station_matches_null_and_zero_but_not_existing():
    blocks = [_block(1, None, None), _block(2, 0, 0), _block(3, 1, 1)]
    result, _ = _filter_equipment_group_blocks_by_flags(
        blocks, {"equipment_group_d_filter": [0], "equipment_group_r_filter": [0]}
    )
    assert [block["equipment_group"].id for block in result] == [1, 2]
    result, _ = _filter_equipment_group_blocks_by_flags(blocks, {})
    assert len(result) == 3


def test_flag_filters_follow_masked_cells_and_recalculate_rowspan(monkeypatch):
    valid = SimpleNamespace(id=10, name="Same region")
    mismatch = SimpleNamespace(id=20, name="Other region")
    monkeypatch.setattr(
        "app.fuel.services.stations.stations_equipment_groups_services."
        "_eg_station_regional_district_consistent",
        lambda station, group: station is valid,
    )
    block = _block(1, 1, 2, (valid, mismatch))
    result, choices = _filter_equipment_group_blocks_by_flags(
        [block], {"equipment_group_r_filter": [MASKED_FLAG_FILTER_VALUE]}
    )
    assert result[0]["station_entries"][0]["station"] is mismatch
    assert len(result[0]["station_entries"]) == 1
    assert result[0]["rowspan"] == 2
    assert choices["r"] == [(MASKED_FLAG_FILTER_VALUE, "–"), (2, "новая группа оборудования действующей станции")]
    assert len(block["station_entries"]) == 2
    new_stations, _ = _filter_equipment_group_blocks_by_flags(
        [block], {"equipment_group_r_filter": [0]}
    )
    assert new_stations == []


def test_demolished_groups_have_named_choices_and_filter_separately():
    blocks = [_block(1, 9, 9), _block(2, 1, 2), _block(3, None, None)]
    result, choices = _filter_equipment_group_blocks_by_flags(
        blocks, {"equipment_group_d_filter": [9], "equipment_group_r_filter": [9]}
    )
    assert [block["equipment_group"].id for block in result] == [1]
    assert (9, "демонтирована") in choices["d"]
    assert (9, "демонтирована") in choices["r"]


def test_flag_filters_keep_unusual_codes_and_selected_values_on_empty_result():
    result, choices = _filter_equipment_group_blocks_by_flags(
        [_block(1, 3, 7)], {"equipment_group_r_filter": [2]}
    )
    assert result == []
    assert choices["d"] == [(3, "3")]
    assert choices["r"] == [(2, "новая группа оборудования действующей станции"), (7, "7")]

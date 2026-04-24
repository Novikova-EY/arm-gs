from types import SimpleNamespace

from app.fuel.services.stations.stations_equipment_groups_services import (
    _merge_adjacent_group_blocks_for_display,
    _merge_adjacent_station_entries_for_display,
)


def _station(station_id, name):
    return SimpleNamespace(id=station_id, name=name)


def _equipment_group(group_id, name):
    return SimpleNamespace(id=group_id, name=name, name_ext=None)


def test_merge_adjacent_station_entries_for_display_uses_station_name():
    blocks = [
        {
            "station_entries": [
                {
                    "station": _station(1, "Архангельская ТЭЦ"),
                    "station_rowspan": 2,
                    "links": [],
                }
            ]
        },
        {
            "station_entries": [
                {
                    "station": _station(99, "Архангельская ТЭЦ"),
                    "station_rowspan": 3,
                    "links": [],
                }
            ]
        },
    ]

    _merge_adjacent_station_entries_for_display(blocks)

    first_entry = blocks[0]["station_entries"][0]
    second_entry = blocks[1]["station_entries"][0]

    assert first_entry["show_merged_station_cells"] is True
    assert first_entry["merged_station_rowspan"] == 5
    assert second_entry["show_merged_station_cells"] is False


def test_merge_adjacent_group_blocks_for_display_uses_group_name():
    blocks = [
        {
            "equipment_group": _equipment_group(1, "Архангельская ТЭЦ (ТЭЦ-130 ата)"),
            "rowspan": 2,
        },
        {
            "equipment_group": _equipment_group(77, "Архангельская ТЭЦ (ТЭЦ-130 ата)"),
            "rowspan": 4,
        },
        {
            "equipment_group": _equipment_group(2, "Вельская ГТ-ТЭЦ"),
            "rowspan": 1,
        },
    ]

    _merge_adjacent_group_blocks_for_display(blocks)

    assert blocks[0]["show_merged_group_cells"] is True
    assert blocks[0]["merged_group_rowspan"] == 6
    assert blocks[1]["show_merged_group_cells"] is False
    assert blocks[2]["show_merged_group_cells"] is True
    assert blocks[2]["merged_group_rowspan"] == 1

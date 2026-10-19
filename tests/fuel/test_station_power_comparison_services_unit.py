from decimal import Decimal
from types import SimpleNamespace

from app.fuel.services.stations.station_power_comparison_services import (
    _add_fuel_totals,
    _collapse_shared_equipment_group,
    _collapse_single_equipment_group,
    _comparison_row_groups,
    _new_totals,
    _paginate_comparison_items,
    _rows_with_numb_subtotals,
    _station_comparison_rows,
    _ved0_parts_check,
)


def test_fuel_power_totals_include_only_positive_ved_rows():
    totals = _new_totals()
    for ved, nust in [
        (1, Decimal("10")),
        (99, Decimal("20")),
        (0, Decimal("100")),
        (None, Decimal("1000")),
        (-1, Decimal("10000")),
    ]:
        _add_fuel_totals(totals, {"ved": ved, "nust": nust})

    assert totals["nust"] == Decimal("30")


def test_global_comparison_rows_stay_grouped_by_numb_for_pagination():
    rows = [
        {"kind": "unclassified", "label": "Без связи"},
        {"kind": "numb", "numb": 10},
        {"kind": "fuel", "numb": 10, "group_id": 1},
        {"kind": "numb", "numb": 11},
        {"kind": "fuel", "numb": 11, "group_id": 2},
    ]

    groups = _comparison_row_groups(rows)

    assert [[row.get("numb") for row in group] for group in groups] == [
        [None, 10, 10], [11, 11]
    ]
    assert groups[0][0]["kind"] == "unclassified"


def test_comparison_pagination_counts_rows_without_splitting_station_blocks():
    items = [
        {"id": index, "rows": [None] * row_count}
        for index, row_count in enumerate((30, 25, 15, 40))
    ]

    current_page, total_pages, page_items = _paginate_comparison_items(items, 2)

    assert (current_page, total_pages) == (2, 2)
    assert [item["id"] for item in page_items] == [2, 3]

    current_page, total_pages, page_items = _paginate_comparison_items(items, 99)
    assert (current_page, total_pages) == (2, 2)
    assert [item["id"] for item in page_items] == [2, 3]

    assert _paginate_comparison_items(items, "bad") == (1, 2, items[:2])


def test_numb_subtotals_sum_both_modules_and_flag_each_mismatch():
    rows = _rows_with_numb_subtotals(
        [
            {"kind": "generation", "numb": 10, "p_ust": Decimal("2"), "p_rasp": Decimal("1")},
            {"kind": "generation", "numb": 10, "p_ust": Decimal("3"), "p_rasp": Decimal("4")},
            {"kind": "generation", "numb": 11, "p_ust": Decimal("5"), "p_rasp": Decimal("6")},
        ],
        [
            {"kind": "fuel", "numb": 10, "ved": 1, "nust": Decimal("5"), "nr": Decimal("5")},
            {"kind": "fuel", "numb": 12, "nust": Decimal("7"), "nr": Decimal("8")},
        ],
        show_p_rasp=True,
    )

    subtotals = {row["numb"]: row for row in rows if row["kind"] == "numb"}

    assert subtotals[10]["p_ust"] == subtotals[10]["nust"] == Decimal("5")
    assert subtotals[10]["p_rasp"] == Decimal("5") == subtotals[10]["nr"]
    assert not subtotals[10]["p_ust_mismatch"]
    assert not subtotals[10]["p_rasp_mismatch"]

    assert subtotals[11]["p_ust"] == Decimal("5")
    assert subtotals[11]["nust"] == Decimal("0")
    assert subtotals[11]["p_ust_mismatch"]
    assert subtotals[11]["p_rasp_mismatch"]

    assert 12 not in subtotals
    assert any(row["kind"] == "fuel" and row["numb"] == 12 for row in rows)


def test_single_fuel_row_without_generation_hides_duplicate_numb_subtotal():
    fuel_row = {
        "kind": "fuel",
        "numb": 66,
        "nust": Decimal("360"),
        "nr": Decimal("0"),
    }

    rows = _rows_with_numb_subtotals([], [fuel_row])

    assert rows == [fuel_row]


def test_single_equipment_group_collapses_units_and_sums_both_modules():
    station = {
        "name": "Станция",
        "station": SimpleNamespace(id=1),
        "generation_rows": [
            {"kind": "generation", "equipment_group_id": 1, "group_name": "Группа 1", "group_type": "ТЭЦ", "numb": 11, "machine_number": str(i), "machine_type": machine_type, "machine_id": i, "p_ust": p_ust, "p_rasp": p_rasp, "is_archived": False, "has_power_row": True}
            for i, machine_type, p_ust, p_rasp in [
                (1, "Р-6-35/5", Decimal("6"), Decimal("2")),
                (2, "Р-12-35/5", Decimal("12"), Decimal("3")),
                (3, "Р-12-35/5", Decimal("12"), Decimal("4")),
            ]
        ],
        "fuel_rows": [
            {"group_id": 1, "numb": 11, "nust": Decimal("27"), "nr": Decimal("6"), "has_param": True, "ved": Decimal("1")}
        ],
    }

    row = _collapse_single_equipment_group(station, show_p_rasp=True)

    assert row["kind"] == "station_group"
    assert row["machine_number"] == "1, 2, 3"
    assert row["machine_type"] == "Р-6-35/5; Р-12-35/5"
    assert row["p_ust"] == Decimal("30")
    assert row["p_rasp"] == Decimal("9")
    assert row["nust"] == Decimal("27")
    assert row["nr"] == Decimal("6")
    assert row["p_ust_mismatch"]
    assert row["p_rasp_mismatch"]
    assert not _collapse_single_equipment_group(station)["p_rasp_mismatch"]


def test_ved_zero_shell_is_excluded_from_totals_but_checked_against_parts():
    rows = _rows_with_numb_subtotals(
        [{"kind": "generation", "numb": 11, "p_ust": Decimal("100"), "p_rasp": Decimal("50")}],
        [
            {"kind": "fuel", "numb": 11, "ved": 1, "nust": Decimal("60"), "nr": Decimal("25")},
            {"kind": "fuel", "numb": 11, "ved": 0, "nust": Decimal("100"), "nr": Decimal("50")},
        ],
        show_p_rasp=True,
    )

    subtotal = next(row for row in rows if row["kind"] == "numb")
    assert subtotal["nust"] == Decimal("60")
    assert subtotal["nr"] == Decimal("25")
    assert subtotal["p_ust_mismatch"]
    assert subtotal["p_rasp_mismatch"]
    assert not any(row.get("ved") == 0 for row in rows if row["kind"] == "fuel")

    visible_rows = _rows_with_numb_subtotals(
        [{"kind": "generation", "numb": 11, "p_ust": Decimal("100"), "p_rasp": Decimal("50")}],
        [
            {"kind": "fuel", "numb": 11, "ved": 1, "nust": Decimal("60"), "nr": Decimal("25")},
            {"kind": "fuel", "numb": 11, "ved": 0, "nust": Decimal("100"), "nr": Decimal("50")},
        ],
        show_p_rasp=True,
        show_ved0=True,
    )
    assert any(row.get("ved") == 0 for row in visible_rows if row["kind"] == "fuel")

    parent = {"nust": Decimal("100"), "nr": Decimal("50")}
    children = [
        {"has_param": True, "ved": 1, "nust": Decimal("60"), "nr": Decimal("25")},
        {"has_param": True, "ved": 2, "nust": Decimal("40"), "nr": Decimal("25")},
    ]
    check = _ved0_parts_check(parent, children, show_p_rasp=True)
    assert check["parts_nust"] == parent["nust"]
    assert check["parts_nr"] == parent["nr"]
    assert not check["nust_mismatch"] and not check["nr_mismatch"]

    children[1]["nust"] = Decimal("39")
    assert _ved0_parts_check(parent, children)["nust_mismatch"]


def test_shared_equipment_group_combines_power_from_multiple_stations():
    station_rows = [
        {
            "name": "Станция 1",
            "station": SimpleNamespace(id=1),
            "generation_rows": [
                {
                    "kind": "generation",
                    "station_id": 1,
                    "equipment_group_id": 7,
                    "group_name": "Общая группа",
                    "group_type": "ТЭЦ",
                    "numb": 17,
                    "machine_number": "1",
                    "machine_type": "Турбина 1",
                    "machine_id": 101,
                    "p_ust": Decimal("10"),
                    "p_rasp": Decimal("8"),
                    "is_archived": False,
                    "has_power_row": True,
                }
            ],
        },
        {
            "name": "Станция 2",
            "station": SimpleNamespace(id=2),
            "generation_rows": [
                {
                    "kind": "generation",
                    "station_id": 2,
                    "equipment_group_id": 7,
                    "group_name": "Общая группа",
                    "group_type": "ТЭЦ",
                    "numb": 17,
                    "machine_number": "2",
                    "machine_type": "Турбина 2",
                    "machine_id": 202,
                    "p_ust": Decimal("20"),
                    "p_rasp": Decimal("15"),
                    "is_archived": False,
                    "has_power_row": True,
                }
            ],
        },
    ]
    fuel_rows = [
        {
            "group_id": 7,
            "numb": 17,
            "nust": Decimal("30"),
            "nr": Decimal("23"),
            "has_param": True,
            "ved": Decimal("1"),
        }
    ]

    row = _collapse_shared_equipment_group(
        7, station_rows, fuel_rows, show_p_rasp=True
    )

    assert row["label"] == "Станция 1 / Станция 2"
    assert row["stations"] == [
        {"id": 1, "name": "Станция 1"},
        {"id": 2, "name": "Станция 2"},
    ]
    assert row["p_ust"] == row["nust"] == Decimal("30")
    assert row["p_rasp"] == row["nr"] == Decimal("23")
    assert not row["p_ust_mismatch"]
    assert not row["p_rasp_mismatch"]
    assert [machine["station_id"] for machine in row["machines"]] == [1, 2]


def test_station_with_multiple_groups_shows_station_then_collapsed_group_rows():
    station = {
        "name": "Станция",
        "station": SimpleNamespace(id=1),
        "totals": {
            "p_ust": Decimal("23"),
            "p_rasp": Decimal("9"),
            "nust": Decimal("23"),
            "nr": Decimal("8"),
        },
        "generation_rows": [
            {
                "kind": "generation",
                "station_id": 1,
                "equipment_group_id": group_id,
                "equipment_group_main": 10,
                "group_name": f"Группа {group_id}",
                "group_type": "ТЭЦ",
                "numb": group_id,
                "machine_number": str(machine_id),
                "machine_sort_key": (machine_id,),
                "machine_type": f"Агрегат {machine_id}",
                "machine_id": machine_id,
                "p_ust": power,
                "p_rasp": power / 2,
                "is_archived": False,
                "has_power_row": True,
            }
            for group_id, machine_id, power in [
                (11, 1, Decimal("6")),
                (11, 2, Decimal("12")),
                (12, 3, Decimal("5")),
            ]
        ],
        "fuel_rows": [
            {"group_id": 11, "group_name": "Группа 11", "numb": 11, "nust": Decimal("18"), "nr": Decimal("9"), "has_param": True, "ved": 1},
            {"group_id": 12, "group_name": "Группа 12", "numb": 12, "nust": Decimal("5"), "nr": Decimal("3"), "has_param": True, "ved": 1},
            {"kind": "fuel", "group_id": 13, "group_name": "Родитель", "numb": 10, "nust": Decimal("23"), "nr": Decimal("12"), "has_param": True, "ved": 0},
        ],
    }

    rows = _station_comparison_rows(station, show_p_rasp=True)

    assert [row["kind"] for row in rows] == [
        "station", "station_group", "station_group"
    ]
    assert not any(row.get("ved") == 0 for row in rows)

    rows_with_ved0 = _station_comparison_rows(
        station, show_p_rasp=True, show_ved0=True
    )
    assert [row["kind"] for row in rows_with_ved0] == [
        "station", "station_group", "station_group", "fuel"
    ]
    assert [row["group_name"] for row in rows_with_ved0[1:3]] == [
        "Группа 11", "Группа 12"
    ]
    assert rows_with_ved0[1]["machine_number"] == "1, 2"
    assert rows_with_ved0[1]["p_ust"] == rows_with_ved0[1]["nust"] == Decimal("18")
    assert rows_with_ved0[2]["machine_number"] == "3"
    assert rows_with_ved0[2]["p_ust"] == rows_with_ved0[2]["nust"] == Decimal("5")
    assert [row["tree_prefix"] for row in rows_with_ved0[1:3]] == ["└", "└"]
    assert rows_with_ved0[-1]["ved"] == 0
    assert rows_with_ved0[-1].get("tree_prefix") is None


def test_several_equipment_groups_are_not_collapsed_together():
    station = {
        "name": "Станция",
        "generation_rows": [
            {"kind": "generation", "equipment_group_id": group_id, "group_name": f"Группа {group_id}", "group_type": "ТЭЦ", "numb": group_id, "machine_number": str(group_id), "machine_type": "Агрегат", "machine_id": group_id, "p_ust": Decimal("10"), "p_rasp": Decimal("5"), "is_archived": False, "has_power_row": True}
            for group_id in (1, 2)
        ],
        "fuel_rows": [],
    }

    assert _collapse_single_equipment_group(station) is None


def test_generation_units_are_grouped_by_equipment_group():
    rows = _rows_with_numb_subtotals(
        [
            {"kind": "generation", "numb": 11, "equipment_group_id": 1, "machine_id": 1, "machine_sort_key": (1,), "p_ust": Decimal("6"), "p_rasp": Decimal("0")},
            {"kind": "generation", "numb": 11, "equipment_group_id": 1, "machine_id": 2, "machine_sort_key": (2,), "p_ust": Decimal("12"), "p_rasp": Decimal("0")},
            {"kind": "generation", "numb": 11, "equipment_group_id": 1, "machine_id": 3, "machine_sort_key": (3,), "p_ust": Decimal("12"), "p_rasp": Decimal("0")},
            {"kind": "generation", "numb": 11, "equipment_group_id": 2, "machine_id": 4, "machine_sort_key": (4,), "p_ust": Decimal("5"), "p_rasp": Decimal("0")},
        ],
        [],
    )

    units = [row for row in rows if row["kind"] == "generation"]
    assert [row["equipment_group_cell_first"] for row in units] == [True, False, False, True]
    assert [row["equipment_group_cell_rowspan"] for row in units if row["equipment_group_cell_first"]] == [3, 1]


def test_rasp_comparison_is_disabled_by_default():
    rows = _rows_with_numb_subtotals(
        [{"kind": "generation", "numb": 10, "p_ust": Decimal("2"), "p_rasp": Decimal("1")}],
        [{"kind": "fuel", "numb": 10, "ved": 1, "nust": Decimal("2"), "nr": Decimal("0")}],
    )

    subtotal = next(row for row in rows if row["kind"] == "numb")
    assert not subtotal["p_ust_mismatch"]
    assert not subtotal["p_rasp_mismatch"]


def test_separate_unlinked_fuel_groups_with_same_numb_are_not_combined():
    rows = _rows_with_numb_subtotals(
        [],
        [
            {"kind": "fuel", "numb": 20, "group_id": 101, "ved": 1, "nust": Decimal("2"), "nr": Decimal("1")},
            {"kind": "fuel", "numb": 20, "group_id": 102, "ved": 1, "nust": Decimal("3"), "nr": Decimal("4")},
        ],
        separate_fuel_groups=True,
    )

    subtotals = [row for row in rows if row["kind"] == "numb"]
    assert len(subtotals) == 2
    assert [row["numb"] for row in subtotals] == [20, 20]
    assert [row["nust"] for row in subtotals] == [Decimal("2"), Decimal("3")]

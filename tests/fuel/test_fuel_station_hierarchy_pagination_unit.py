# -*- coding: utf-8 -*-
"""Unit-тесты soft-пагинации иерархии топлива (не рвать РЭС)."""

from app.fuel.services.equipment_groups.fuel_station_hierarchy_pagination import (
    compute_fuel_eg_effective_total_pages,
    compute_fuel_eg_page_start_index,
    paginate_fuel_eg_station_hierarchy,
    slice_fuel_eg_page_range,
)


def _item(est, ues, res, station, gb_id):
    return {
        "est_id": est,
        "ues_id": ues,
        "res_id": res,
        "station_id": station,
        "station_name": f"st-{station}",
        "group_block": {"id": gb_id},
    }


def test_soft_page_keeps_res_intact_when_limit_hits_mid_res():
    # РЭС-A: 3 группы, РЭС-B: 3 группы. per_page=2 → страница 1 забирает весь A.
    flat = [
        _item(1, 10, 100, 1, "a1"),
        _item(1, 10, 100, 1, "a2"),  # составной ребёнок
        _item(1, 10, 100, 1, "a3"),  # ещё ребёнок / сосед
        _item(1, 10, 200, 2, "b1"),
        _item(1, 10, 200, 2, "b2"),
        _item(1, 10, 200, 2, "b3"),
    ]
    start, end, total_pages, current = slice_fuel_eg_page_range(flat, 2, 1)
    assert current == 1
    assert total_pages == 2
    assert (start, end) == (0, 3)
    page1_ids = [x["group_block"]["id"] for x in flat[start:end]]
    assert page1_ids == ["a1", "a2", "a3"]

    start2, end2, _, current2 = slice_fuel_eg_page_range(flat, 2, 2)
    assert current2 == 2
    assert (start2, end2) == (3, 6)
    page2_ids = [x["group_block"]["id"] for x in flat[start2:end2]]
    assert page2_ids == ["b1", "b2", "b3"]


def test_soft_page_does_not_orphan_composite_parent_before_res_total():
    # Как баг «Новгородская ТЭЦ, всего» без детей при жёстком срезе:
    # per_page=5 на границе РЭС забрал бы только родителя.
    flat = [
        _item(1, 10, 50, 1, f"prev{i}") for i in range(5)
    ] + [
        _item(1, 10, 100, 7, "nov-parent"),
        _item(1, 10, 100, 7, "nov-child1"),
        _item(1, 10, 100, 7, "nov-child2"),
        _item(1, 10, 100, 8, "akron"),
        _item(1, 10, 100, 9, "borovichi"),
    ]
    start1, end1, total_pages, _ = slice_fuel_eg_page_range(flat, 5, 1)
    assert total_pages == 2
    assert (start1, end1) == (0, 5)
    assert [x["group_block"]["id"] for x in flat[start1:end1]] == [
        "prev0",
        "prev1",
        "prev2",
        "prev3",
        "prev4",
    ]

    start2, end2, _, _ = slice_fuel_eg_page_range(flat, 5, 2)
    assert (start2, end2) == (5, 10)
    ids2 = [x["group_block"]["id"] for x in flat[start2:end2]]
    assert ids2 == [
        "nov-parent",
        "nov-child1",
        "nov-child2",
        "akron",
        "borovichi",
    ]


def test_soft_page_extends_through_composite_cluster_inside_res():
    flat = [
        _item(1, 10, 100, 7, "nov-parent"),
        _item(1, 10, 100, 7, "nov-child1"),
        _item(1, 10, 100, 7, "nov-child2"),
        _item(1, 10, 200, 8, "other"),
    ]
    # Жёсткий срез per_page=2: parent+child1 | child2+other.
    start, end, total_pages, _ = slice_fuel_eg_page_range(flat, 2, 1)
    assert total_pages == 2
    assert [x["group_block"]["id"] for x in flat[start:end]] == [
        "nov-parent",
        "nov-child1",
        "nov-child2",
    ]


def test_soft_page_start_index_matches_effective_pages_walk():
    flat = [
        _item(1, 1, 1, 1, i) for i in range(4)
    ] + [
        _item(1, 1, 2, 2, i) for i in range(4, 8)
    ] + [
        _item(1, 1, 3, 3, i) for i in range(8, 10)
    ]
    assert compute_fuel_eg_effective_total_pages(flat, 3) == 3
    assert compute_fuel_eg_page_start_index(flat, 3, 1) == 0
    assert compute_fuel_eg_page_start_index(flat, 3, 2) == 4
    assert compute_fuel_eg_page_start_index(flat, 3, 3) == 8


def test_paginate_does_not_duplicate_same_station_different_clusters(monkeypatch):
    """
    Два station_block с одним station_id/name, но разными cluster_key
    (старый баг Мурманская ТЭЦ / Котельные) не должны дублировать EG.
    """
    from types import SimpleNamespace

    from app.fuel.services.equipment_groups import fuel_station_hierarchy_pagination as mod

    monkeypatch.setattr(mod, "get_current_db_version_id", lambda: None)
    monkeypatch.setattr(mod, "get_standalone_equipment_group_ids", lambda **kwargs: set())

    eg_a = SimpleNamespace(id=1, name="A")
    eg_b = SimpleNamespace(id=2, name="B")
    hierarchy = [
        {
            "est_id": 1,
            "est_name": "EST",
            "ues_list": [
                {
                    "ues_id": 10,
                    "ues_name": "UES",
                    "res_list": [
                        {
                            "res_id": 100,
                            "res_name": "RES",
                            "res_summary": {},
                            "station_blocks": [
                                {
                                    "station_id": 35738,
                                    "station_name": "Мурманская ТЭЦ",
                                    "cluster_key": "composite:16",
                                    "is_virtual": False,
                                    "suppress_station_summary": True,
                                    "group_blocks": [
                                        {
                                            "equipment_group": eg_a,
                                            "rows": [(eg_a, None)],
                                        }
                                    ],
                                },
                                {
                                    "station_id": 35738,
                                    "station_name": "Мурманская ТЭЦ",
                                    "cluster_key": "station:35738",
                                    "is_virtual": False,
                                    "suppress_station_summary": True,
                                    "group_blocks": [
                                        {
                                            "equipment_group": eg_b,
                                            "rows": [(eg_b, None)],
                                        }
                                    ],
                                },
                            ],
                        }
                    ],
                }
            ],
        }
    ]
    paged, total, pages, page = paginate_fuel_eg_station_hierarchy(
        hierarchy, 1, 25, ["gaz"]
    )
    assert page == 1
    assert total == 2
    names = []
    for est in paged:
        for ues in est["ues_list"]:
            for res in ues["res_list"]:
                assert len(res["station_blocks"]) == 2
                for sb in res["station_blocks"]:
                    for gb in sb["group_blocks"]:
                        names.append(gb["equipment_group"].id)
    assert names == [1, 2]
    assert len(names) == len(set(names))

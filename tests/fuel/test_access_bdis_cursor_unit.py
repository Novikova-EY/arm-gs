# -*- coding: utf-8 -*-
from decimal import Decimal
from types import SimpleNamespace

from app.fuel.services.calculation.access_bdis_cursor import (
    AccessBdisCursorState,
    access_dynaset_sort_key,
    fuel_param_access_n1,
    parse_access_numb1,
    sort_access_filter_rows,
    walk_access_bdis_cursor,
)


def test_numb1_keeps_access_fraction():
    assert parse_access_numb1("256.1") == 256.1
    assert parse_access_numb1("256,2") == 256.2
    assert parse_access_numb1(None, 428) == 428.0


def test_dynaset_order_is_numb1_then_year():
    a = access_dynaset_sort_key(numb1="383", year=2024)
    b = access_dynaset_sort_key(numb1="383", year=2026)
    c = access_dynaset_sort_key(numb1="428", year=2024)
    assert a < b < c


def test_cursor_own_base_year_hours_before_cyear():
    rows = sort_access_filter_rows(
        [
            SimpleNamespace(year_number=2024, h=Decimal("337.3"), nust=1200, numb1=428),
            SimpleNamespace(year_number=2026, h=None, nust=1200, numb1=428),
        ],
        n1_of=lambda r: r.numb1,
    )
    cyear = [
        (kind, row, state)
        for kind, row, state in walk_access_bdis_cursor(rows, byear=2024, cyear=2026)
        if kind == "cyear"
    ]
    assert len(cyear) == 1
    assert cyear[0][2].hb == Decimal("337.3")
    assert cyear[0][2].nustb == Decimal("1200")


def test_cursor_reuses_previous_station_hb_when_base_year_not_in_filter():
    """VBA: 2024 с ved=0 не в filter1 — hb остаётся с предыдущей станции."""
    rows = sort_access_filter_rows(
        [
            SimpleNamespace(year_number=2024, h=Decimal("2948.8"), nust=2520, numb1=383),
            SimpleNamespace(year_number=2026, h=None, nust=2520, numb1=383),
            SimpleNamespace(year_number=2026, h=None, nust=1200, numb1=428),
        ],
        n1_of=lambda r: r.numb1,
    )
    cyears = [
        (row.numb1, state.hb, state.nustb)
        for kind, row, state in walk_access_bdis_cursor(rows, byear=2024, cyear=2026)
        if kind == "cyear"
    ]
    assert cyears[0][0] == 383
    assert cyears[0][1] == Decimal("2948.8")
    assert cyears[1][0] == 428
    assert cyears[1][1] == Decimal("2948.8")
    assert cyears[1][2] == Decimal("2520")


def test_empty_h_is_zero_like_access_z():
    rows = [
        SimpleNamespace(year_number=2024, h=None, nust=None, numb1=1),
        SimpleNamespace(year_number=2026, h=None, nust=90, numb1=1),
    ]
    cyear = [
        state
        for kind, _row, state in walk_access_bdis_cursor(rows, byear=2024, cyear=2026)
        if kind == "cyear"
    ][0]
    assert cyear.hb == Decimal("0")
    assert cyear.bnust1 == Decimal("0")


def test_sort_key_uses_ordnumb_not_capacity_n1():
    fp = SimpleNamespace(
        numb1=None,
        numb1120=147,
        equipment_group_id=1,
        equipment_group=SimpleNamespace(n1="1200", ordnumb="428", numb=147),
    )
    groups = {1: fp.equipment_group}
    assert fuel_param_access_n1(fp, groups) == 428.0
    fp.equipment_group.ordnumb = None
    assert fuel_param_access_n1(fp, groups) == 147.0


def test_hb_persists_across_walks_like_vba_dim():
    state = AccessBdisCursorState()
    first = [
        SimpleNamespace(year_number=2024, h=Decimal("2948.8"), nust=2520),
        SimpleNamespace(year_number=2026, h=None, nust=2520),
    ]
    list(walk_access_bdis_cursor(first, byear=2024, cyear=2026, state=state))
    only_cyear = [SimpleNamespace(year_number=2026, h=None, nust=90)]
    cyear = [
        s
        for kind, _row, s in walk_access_bdis_cursor(
            only_cyear, byear=2024, cyear=2026, state=state
        )
        if kind == "cyear"
    ][0]
    assert cyear.hb == Decimal("2948.8")

# -*- coding: utf-8 -*-
from types import SimpleNamespace

from app.fuel.services.calculation.equipment_group_selection import (
    access_ved_filter_year_row_participates,
    dedupe_equipment_group_ids_prefer_version,
    drop_null_groups_shadowed_by_versioned_numb,
    participating_group_ids_for_year,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
    restrict_equipment_group_query_to_current_version,
)


def test_dedupe_prefers_versioned_over_null():
    rows = [
        (1, 10, None),
        (2, 10, 20),
        (3, 11, None),
        (4, 12, 20),
    ]
    assert dedupe_equipment_group_ids_prefer_version(rows, 20) == [2, 3, 4]


def test_dedupe_keeps_null_when_no_versioned():
    rows = [
        (1, 10, None),
        (2, 11, None),
    ]
    assert dedupe_equipment_group_ids_prefer_version(rows, 20) == [1, 2]


def test_dedupe_keeps_rows_without_numb():
    rows = [
        (1, None, 20),
        (2, None, None),
        (3, 5, 20),
        (4, 5, None),
    ]
    assert dedupe_equipment_group_ids_prefer_version(rows, 20) == [1, 2, 3]


def test_drop_null_group_when_versioned_numb_exists():
    """Киришская ГРЭС: 13225 (NULL) не должна подменять 13228 (версия 37)."""
    rows = [
        (13225, 3611, None),
        (99, 4000, None),
        (13228, 3611, 37),
    ]
    out = drop_null_groups_shadowed_by_versioned_numb(rows, {3611})
    assert [(gid, numb, vid) for gid, numb, vid in out] == [
        (99, 4000, None),
        (13228, 3611, 37),
    ]


def test_drop_null_keeps_legacy_when_numb_not_in_version():
    rows = [(13225, 3611, None)]
    assert drop_null_groups_shadowed_by_versioned_numb(rows, set()) == rows
    assert drop_null_groups_shadowed_by_versioned_numb(rows, {9999}) == rows


def test_restrict_version_skip_keeps_explicit_ids_query():
    sentinel = object()
    assert (
        restrict_equipment_group_query_to_current_version(sentinel, 46, skip=True)
        is sentinel
    )


def test_access_ved_filter_year_row_like_access_findfirst():
    """Access filter1 (ved>0) — на строке года, не на группе за оба года."""
    assert access_ved_filter_year_row_participates(SimpleNamespace(ved=2))
    assert access_ved_filter_year_row_participates(SimpleNamespace(ved=1))
    assert not access_ved_filter_year_row_participates(SimpleNamespace(ved=0))
    assert not access_ved_filter_year_row_participates(SimpleNamespace(ved=None))
    assert not access_ved_filter_year_row_participates(None)


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows

    def query(self, *args, **kwargs):
        return _FakeQuery(self._rows)


def test_participating_group_ids_skips_ved_zero_on_calc_year():
    parent = SimpleNamespace(
        equipment_group_id=10, year_number=2026, ved=2, database_version_id=None
    )
    child = SimpleNamespace(
        equipment_group_id=11, year_number=2026, ved=0, database_version_id=None
    )
    session = _FakeSession([parent, child])
    assert participating_group_ids_for_year(
        session, [10, 11], year_number=2026, effective_db_version=None
    ) == [10]

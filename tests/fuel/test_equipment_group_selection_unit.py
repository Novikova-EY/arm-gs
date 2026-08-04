# -*- coding: utf-8 -*-
from app.fuel.services.calculation.equipment_group_selection import (
    dedupe_equipment_group_ids_prefer_version,
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

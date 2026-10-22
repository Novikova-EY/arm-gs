# -*- coding: utf-8 -*-
"""Access Seek: пустое окно этой станции → Bookmark предыдущей, не 2021."""
from types import SimpleNamespace

from app.fuel.services.calculation.specific_consumption_lookup import (
    AccessSeekBookmark,
    access_numb2_key_ge,
    apply_access_seek_bookmark,
    pick_specific_consumption_access_seek,
)


def test_numb2_seek_ge_next_station_is_match():
    """Seek '>=', 671, 0, 2024 находит 672/2021 – NoMatch=False."""
    assert access_numb2_key_ge(672, 0, 2021, seek_numb=671, seek_year=2024) is True
    assert access_numb2_key_ge(671, 0, 2021, seek_numb=671, seek_year=2024) is False
    assert access_numb2_key_ge(670, 0, 2024, seek_numb=671, seek_year=2024) is False


def test_this_station_window_updates_bookmark():
    bm = AccessSeekBookmark()
    own = SimpleNamespace(year_number=2024, y=10)
    assert apply_access_seek_bookmark(own, bm, no_match=False) is own
    assert bm.row is own


def test_empty_window_uses_previous_bookmark():
    prev = SimpleNamespace(year_number=2024, y=343.66, numb1120=670)
    bm = AccessSeekBookmark(row=prev)
    used = apply_access_seek_bookmark(None, bm, no_match=False)
    assert used is prev
    assert bm.row is prev


def test_true_nomatch_skips_and_keeps_bookmark():
    prev = SimpleNamespace(year_number=2024)
    bm = AccessSeekBookmark(row=prev)
    assert apply_access_seek_bookmark(None, bm, no_match=True) is None
    assert bm.row is prev


def test_empty_bookmark_and_not_nomatch_returns_none():
    bm = AccessSeekBookmark()
    assert apply_access_seek_bookmark(None, bm, no_match=False) is None


def test_own_2021_still_outside_window():
    old = SimpleNamespace(year_number=2021, y=429)
    assert pick_specific_consumption_access_seek([old], byear=2024, cyear=2029) is None

# -*- coding: utf-8 -*-
from app.generation.services.station_services.filters_services import (
    _ilike_contains_pattern,
    apply_external_code_sql_filter,
    build_external_code_sql_filter,
)


def test_uuid_filter_empty_is_noop():
    assert build_external_code_sql_filter({}) is None
    assert build_external_code_sql_filter({"external_code_filter": "  "}) is None
    assert apply_external_code_sql_filter("query", {}) == "query"


def test_ilike_contains_escapes_like_wildcards():
    assert _ilike_contains_pattern("872e8d7e-cc4f-5e48-8229-ef2d923f86d1") == (
        "%872e8d7e-cc4f-5e48-8229-ef2d923f86d1%"
    )
    assert _ilike_contains_pattern("a_b%c\\d") == r"%a\_b\%c\\d%"

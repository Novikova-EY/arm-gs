# -*- coding: utf-8 -*-
"""Фильтры витрины итогов топлива."""

from werkzeug.datastructures import MultiDict

from app.fuel.services.totals_summary.fuel_totals_summary_services import (
    parse_aggregation_types,
)


def test_year_query_without_aggregation_defaults_to_ees():
    args = MultiDict([("start_year", "2023"), ("end_year", "2031")])

    assert parse_aggregation_types(args) == ["ees"]


def test_explicit_empty_aggregation_filter_stays_empty():
    args = MultiDict(
        [
            ("start_year", "2023"),
            ("end_year", "2031"),
            ("aggregation_type", ""),
        ]
    )

    assert parse_aggregation_types(args) == []


def test_empty_aggregation_marker_does_not_hide_selected_aggregation():
    args = MultiDict(
        [
            ("aggregation_type", ""),
            ("aggregation_type", "russia"),
        ]
    )

    assert parse_aggregation_types(args) == ["russia"]

"""Парсер «Дата и время, мск» для сводки нагрузок (в т.ч. Excel-варианты)."""

from __future__ import annotations

from zoneinfo import ZoneInfo

import pytest

from app.power_demand.services.demand_parameter_services import (
    _normalize_peak_datetime_text,
    format_peak_datetime,
    parse_peak_datetime,
)

MSK = ZoneInfo("Europe/Moscow")


@pytest.mark.parametrize(
    "raw,expected_norm",
    [
        ('"10.01.23 18-00"', "10.01.2023 18:00"),
        ('"16.12.24 17-00"', "16.12.2024 17:00"),
        ('"26.02.25 19-00"', "26.02.2025 19:00"),
        ("17.12.2016 18:00", "17.12.2016 18:00"),
        ("31.01.2017\n00:00", "31.01.2017 00:00"),
        ("«10.01.23 18-00»", "10.01.2023 18:00"),
        ("10.01.23 18-00", "10.01.2023 18:00"),
        ("2023", "2023"),
    ],
)
def test_normalize_peak_datetime_excel_variants(raw, expected_norm):
    assert _normalize_peak_datetime_text(raw) == expected_norm


@pytest.mark.parametrize(
    "raw,year,month,day,hour,minute",
    [
        ('"10.01.23 18-00"', 2023, 1, 10, 18, 0),
        ('"16.12.24 17-00"', 2024, 12, 16, 17, 0),
        ('"26.02.25 19-00"', 2025, 2, 26, 19, 0),
        ("17.12.2016 18:00", 2016, 12, 17, 18, 0),
        ("24.12.2022 00:00", 2022, 12, 24, 0, 0),
        ("10.01.23 18-00", 2023, 1, 10, 18, 0),
        ("01.01.69 00-00", 1969, 1, 1, 0, 0),  # %y: 69 → 1969
        ("01.01.68 12:30", 2068, 1, 1, 12, 30),
    ],
)
def test_parse_peak_datetime_excel_and_canonical(raw, year, month, day, hour, minute):
    dt = parse_peak_datetime(raw)
    assert dt is not None
    assert dt.tzinfo is not None
    local = dt.astimezone(MSK)
    assert (local.year, local.month, local.day, local.hour, local.minute) == (
        year,
        month,
        day,
        hour,
        minute,
    )


def test_parse_peak_datetime_year_only():
    dt = parse_peak_datetime("2023")
    assert dt is not None
    local = dt.astimezone(MSK)
    assert (local.year, local.month, local.day, local.hour, local.minute) == (
        2023,
        1,
        1,
        0,
        0,
    )


def test_parse_peak_datetime_invalid_returns_none():
    assert parse_peak_datetime("") is None
    assert parse_peak_datetime(None) is None
    assert parse_peak_datetime("not-a-date") is None
    assert parse_peak_datetime("32.13.2023 18:00") is None


def test_format_after_excel_parse_is_canonical():
    dt = parse_peak_datetime('"10.01.23 18-00"')
    assert format_peak_datetime(dt) == "10.01.2023 18:00"

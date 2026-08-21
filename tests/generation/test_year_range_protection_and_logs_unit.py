"""Unit tests for year-range protection when saving machine expected years."""

from app.generation.services.machine_services.machine_services import (
    _should_keep_year_outside_display_range,
)
from app.logs.routes.log_routes import _parse_date_arg
from datetime import date


def test_keep_modernization_year_outside_narrow_display_range():
    assert _should_keep_year_outside_display_range(
        field_name="date_modernization_power_change_expected",
        new_val=None,
        old_val=2025,
        start_year=2026,
        end_year=2031,
        is_new=False,
    )


def test_allow_clear_modernization_when_year_inside_display_range():
    assert not _should_keep_year_outside_display_range(
        field_name="date_modernization_power_change_expected",
        new_val=None,
        old_val=2027,
        start_year=2025,
        end_year=2031,
        is_new=False,
    )


def test_allow_overwrite_when_new_year_provided():
    assert not _should_keep_year_outside_display_range(
        field_name="date_modernization_power_change_expected",
        new_val=2028,
        old_val=2025,
        start_year=2026,
        end_year=2031,
        is_new=False,
    )


def test_do_not_protect_unrelated_fields():
    assert not _should_keep_year_outside_display_range(
        field_name="date_commission_fact",
        new_val=None,
        old_val=2025,
        start_year=2026,
        end_year=2031,
        is_new=False,
    )


def test_parse_date_arg_valid_and_invalid():
    assert _parse_date_arg("2026-03-15") == date(2026, 3, 15)
    assert _parse_date_arg("") is None
    assert _parse_date_arg("15.03.2026") is None
    assert _parse_date_arg("not-a-date") is None

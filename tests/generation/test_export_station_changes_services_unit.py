import pytest


from app.generation.services.station_changes_services.export_station_changes_services import (
    _get_sum_years_and_header,
)


def test_sum_years_excludes_current_year_and_shows_sipr_header_when_current_is_start():
    sum_years, header = _get_sum_years_and_header(2025, 2031, 2025)
    assert sum_years == [2026, 2027, 2028, 2029, 2030, 2031]
    assert header == "2026–2031 гг."


def test_sum_years_excludes_current_year_inside_range_and_marks_header():
    sum_years, header = _get_sum_years_and_header(2025, 2031, 2027)
    assert sum_years == [2025, 2026, 2028, 2029, 2030, 2031]
    assert header == "2025–2031 гг.\n(без 2027 г.)"


def test_sum_years_when_current_year_is_none_sums_all_years():
    sum_years, header = _get_sum_years_and_header(2025, 2031, None)
    assert sum_years == [2025, 2026, 2027, 2028, 2029, 2030, 2031]
    assert header == "2025–2031 гг."



import pytest


from app.generation.services.station_changes_services.export_station_changes_services import (
    STATION_TYPE_ORDER_FOR_TOTALS,
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


def test_export_station_type_order_includes_snee_after_ses():
    assert STATION_TYPE_ORDER_FOR_TOTALS[-1] == "СНЭЭ"
    assert "СЭС" in STATION_TYPE_ORDER_FOR_TOTALS


def test_export_russia_ees_totals_pass_station_type_maps():
    """Регрессия QA C: итоги России/ЕЭС должны получать карту по типам станций."""
    from pathlib import Path

    text = Path(
        "app/generation/services/station_changes_services/export_station_changes_services.py"
    ).read_text(encoding="utf-8")
    assert "aggregate_changes_total_energy_system_types_by_station_types" in text
    assert "total_by_station_map" in text
    assert 'write_combined_totals_block("Итого\\nпо электроэнергетическим системам России", total_events_map, {})' not in text





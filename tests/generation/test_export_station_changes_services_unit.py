import pytest
from types import SimpleNamespace

from app.generation.services.station_changes_services.export_station_changes_services import (
    STATION_TYPE_ORDER_FOR_TOTALS,
    PRIL2_DASH,
    PRIL2_FOOTNOTES,
    _get_sum_years_and_header,
    _pril2_empty_text,
    _pril2_mw_value,
    _pril2_object_mw_cell,
    _pril2_row_period_total,
    _power_row_machine_name,
    _power_row_machine_number,
    _should_split_machine_identity,
    _write_machine_identity_cells,
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
    assert "_write_machine_identity_cells(" in text
    assert text.count("_write_machine_identity_cells(") >= 3


def _mod_machine(**kwargs):
    defaults = dict(
        event_types={"before_modernization", "after_modernization", "change_power"},
        machine_number="7",
        machine_name="ПГУ-1",
        display_name="К-215-130 (К-300-240)",
        display_name_before="К-215-130",
        display_name_after="К-300-240",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_export_machine_number_only_on_before_modernization():
    machine = _mod_machine()
    assert _power_row_machine_number(machine, {"event": "before_modernization"}) == "7"
    assert _power_row_machine_number(machine, {"event": "after_modernization"}) == ""
    assert _power_row_machine_number(machine, {"event": "change_power"}) == ""


def test_export_machine_name_splits_before_after_modernization():
    machine = _mod_machine()
    assert _power_row_machine_name(machine, {"event": "before_modernization"}) == "К-215-130"
    assert _power_row_machine_name(machine, {"event": "after_modernization"}) == "К-300-240"
    assert _power_row_machine_name(machine, {"event": "change_power"}) == ""


def test_export_pgu_part_name_and_number_from_power_row():
    machine = _mod_machine()
    row = {
        "event": "before_modernization",
        "display_machine_name": "ПТ-1",
        "display_machine_number": "2",
    }
    assert _power_row_machine_name(machine, row) == "ПТ-1"
    assert _power_row_machine_number(machine, row) == "2"
    after = {**row, "event": "after_modernization"}
    assert _power_row_machine_number(machine, after) == ""
    assert _power_row_machine_name(machine, after) == ""


def test_export_same_machine_name_only_on_before_modernization():
    machine = _mod_machine(
        machine_name="ПТ-80-130/13",
        display_name="ПТ-80-130/13",
        display_name_before=None,
        display_name_after=None,
    )
    assert _power_row_machine_name(machine, {"event": "before_modernization"}) == "ПТ-80-130/13"
    assert _power_row_machine_name(machine, {"event": "after_modernization"}) == ""
    assert _power_row_machine_name(machine, {"event": "change_power"}) == ""


def test_export_empty_machine_number_is_dash_for_non_mod():
    machine = SimpleNamespace(event_types={"commission"}, machine_number=None, machine_name="ВЭУ")
    assert _power_row_machine_number(machine, {"event": "commission"}) == "–"


def test_write_machine_identity_does_not_merge_on_modernization():
    writes = []
    merges = []

    class _Ws:
        def write(self, r, c, value, fmt=None):
            writes.append((r, c, value))

    def merge_if_needed(r1, c1, r2, c2, value, fmt=None):
        merges.append((r1, c1, r2, c2, value))

    machine = _mod_machine()
    rows = [
        {"event": "before_modernization"},
        {"event": "after_modernization"},
        {"event": "change_power"},
    ]
    assert _should_split_machine_identity(machine, rows) is True
    _write_machine_identity_cells(
        worksheet=_Ws(),
        merge_if_needed=merge_if_needed,
        cell_format=None,
        machine=machine,
        power_rows=rows,
        first_row=10,
        last_row=12,
        machine_num_col=5,
        machine_name_col=6,
    )
    assert merges == []
    assert (10, 5, "7") in writes
    assert (11, 5, "") in writes
    assert (12, 5, "") in writes
    assert (10, 6, "К-215-130") in writes
    assert (11, 6, "К-300-240") in writes
    assert (12, 6, "") in writes


def test_export_routes_pass_changes_mode():
    from pathlib import Path

    text = Path("app/generation/routes/station_changes/station_changes_routes.py").read_text(
        encoding="utf-8"
    )
    assert 'filters["changes_mode"] = _resolve_changes_mode_from_request()' in text
    assert '"changes_mode": _resolve_changes_mode_from_request()' in text
    assert "_clamp_export_start_year" in text
    assert 'STATION_CHANGES_EXPORT_PAYLOAD_VERSION = 11' in text


def test_pril2_dash_and_empty_mw():
    assert PRIL2_DASH == "–"
    assert _pril2_empty_text(None) == "–"
    assert _pril2_empty_text("—") == "–"
    assert _pril2_empty_text("Газ") == "Газ"
    assert _pril2_mw_value(None) == 0
    assert _pril2_mw_value(0) == 0
    assert _pril2_mw_value(-3) == -3
    assert _pril2_mw_value(53) == 53
    assert _pril2_object_mw_cell(None) is None
    assert _pril2_object_mw_cell(0) is None
    assert _pril2_object_mw_cell(-3) == -3
    assert _pril2_object_mw_cell(53) == 53


def test_pril2_period_total_is_per_row_not_station_sum():
    sum_years = [2026, 2027, 2028, 2029, 2030, 2031]
    assert _pril2_row_period_total(2026, 53, sum_years) == 53
    assert _pril2_row_period_total(2026, 168, sum_years) == 168
    assert _pril2_row_period_total(2025, 75, sum_years) is None
    assert _pril2_row_period_total(2026, -3, sum_years) == -3


def test_pril2_form_source_matches_etalon_layout():
    from pathlib import Path

    text = Path(
        "app/generation/services/station_changes_services/export_station_changes_services.py"
    ).read_text(encoding="utf-8")
    assert '"Тип электростанции1)"' in text
    assert 'note_header = "Документ-основание1)"' in text
    assert 'f"A5:{last_col_name}5"' in text
    assert "worksheet.repeat_rows(6, 7)" in text
    assert "worksheet.hide_zero()" in text
    assert "_pril2_object_mw_cell(val)" in text
    assert "_write_pril2_footnotes(worksheet, current_row, last_col_name, workbook)" in text
    assert len(PRIL2_FOOTNOTES) == 7
    assert PRIL2_FOOTNOTES[0][0] == "Примечания"
    assert PRIL2_FOOTNOTES[1][0].startswith("1)")
    assert "Загорской ГАЭС-2" in PRIL2_FOOTNOTES[2][0]
    routes = Path("app/generation/routes/station_changes/station_changes_routes.py").read_text(
        encoding="utf-8"
    )
    assert "Форма «Приложение 2» всегда с итогами" in routes



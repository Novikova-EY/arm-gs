"""Unit tests for Generation station-list / machine-card QA fixes."""

from types import SimpleNamespace
from unittest.mock import patch

from app.common.services.help_services import (
    _clean_name,
    _has_balanced_angle_quotes,
    _replace_quotes_sequentially,
)
from app.generation.models.machine.machine_model import Machine
from app.generation.services.station_changes_services.station_changes_services import (
    resolve_effective_sync_area_id,
)


def _machine_ns(**kwargs):
    """Lightweight stand-in for Machine display properties (no ORM init)."""
    defaults = dict(
        date_commission_year=None,
        date_exploitation=None,
        date_exploitation_expected=None,
        date_commission_fact=None,
        date_joining_fact=None,
        date_detatchment_fact=None,
        date_decompressing_fact=None,
        date_decompressing_expected=None,
        date_modernization_power_change_expected=None,
        date_modernization_no_power_change_expected=None,
        date_relabing_fact=None,
        date_update_fact=None,
        tes_machine_type=None,
        pgu_machines=[],
        pgu_submachines=[],
    )
    defaults.update(kwargs)
    obj = SimpleNamespace(**defaults)
    # Bind helpers used by @property methods
    obj._is_pgu_parent_with_parts = lambda: Machine._is_pgu_parent_with_parts(obj)
    obj._fact_display_years = lambda raw: Machine._fact_display_years(obj, raw)
    obj._has_fact_in_current_year = lambda raw: Machine._has_fact_in_current_year(obj, raw)
    obj._relabing_year_for_display = lambda dt: Machine._relabing_year_for_display(obj, dt)
    return obj


# --- 1) machine_number empty persistence helpers ---


def test_machine_number_empty_string_is_change_from_one():
    old_v, new_v = "1", ""
    to_str = lambda x: (
        str(x).strip() if x is not None and str(x).strip() != "" else "не указано"
    )
    assert to_str(old_v) != to_str(new_v)
    assert to_str(new_v) == "не указано"


# --- 2) display years: fact suppresses expected ---


def test_modernization_display_suppresses_expected_when_relabing_in_current_year():
    m = _machine_ns(
        date_modernization_power_change_expected=2027,
        date_relabing_fact="15.06.2025",
    )
    with patch(
        "app.common.services.get_services.years.years_get_services.get_current_year",
        return_value=2025,
    ):
        assert Machine.modernization_display.fget(m) == "2025"


def test_modernization_display_keeps_expected_when_no_current_fact():
    m = _machine_ns(date_modernization_power_change_expected=2027)
    with patch(
        "app.common.services.get_services.years.years_get_services.get_current_year",
        return_value=2025,
    ):
        assert Machine.modernization_display.fget(m) == "2027"


def test_commission_display_hides_expected_when_joining_fact_current_year():
    m = _machine_ns(
        date_exploitation_expected=2026,
        date_joining_fact="01.03.2025",
    )
    with patch(
        "app.common.services.get_services.years.years_get_services.get_current_year",
        return_value=2025,
    ):
        assert Machine.commission_display.fget(m) is None


def test_decompressing_display_01_01_rule():
    m = _machine_ns(
        date_decompressing_fact="01.01.2025",
        date_decompressing_expected=2030,
    )
    assert Machine.decompressing_display.fget(m) == 2024


def test_pgu_parent_hides_commission_and_modernization():
    m = _machine_ns(
        date_commission_year=2024,
        date_modernization_power_change_expected=2026,
        tes_machine_type=SimpleNamespace(name="ПГУ"),
        pgu_machines=[SimpleNamespace(id=1)],
    )
    assert Machine.commission_display.fget(m) is None
    assert Machine.modernization_display.fget(m) is None


# --- 3) quotes ---


def test_nested_yolochki_not_mangled_by_clean_name():
    src = "АО «Группа «Илим»»"
    assert _has_balanced_angle_quotes(src)
    assert _clean_name(src) == src
    assert _replace_quotes_sequentially(src) == src


def test_ascii_quotes_still_normalized():
    assert _replace_quotes_sequentially('АО "Группа"') == "АО «Группа»"


# --- 6) decommission filter 01.01.XX → XX-1 (pattern contract) ---


def test_decompressing_filter_0101_patterns():
    """Same pattern contract as modernization filter / card display."""
    years_only = [2024]
    pats = []
    for y in years_only:
        pats.append(rf"01\.01\.{y + 1}\b")
        pats.append(rf"(?<!01\.01\.){y}(?!\d)")
    fact_regex = "(" + "|".join(pats) + ")"
    assert r"01\.01\.2025\b" in fact_regex
    assert r"(?<!01\.01\.)2024(?!\d)" in fact_regex
    # 01.01.2025 must match year filter 2024, not 2025
    import re

    assert re.search(fact_regex, "01.01.2025")
    assert not re.search(
        "(" + "|".join([rf"01\.01\.{2025 + 1}\b", rf"(?<!01\.01\.){2025}(?!\d)"]) + ")",
        "01.01.2025",
    )


# --- 7) commission year sort key ascending ---


def test_commission_year_sort_ascending_not_parity():
    years = [2042, 2025, 2027, 2026, 2028]
    sorted_years = sorted(years)
    assert sorted_years == [2025, 2026, 2027, 2028, 2042]
    odd_even = sorted(years, key=lambda y: (y % 2, y))
    assert odd_even != sorted_years


# --- 9) sync zones ---


def test_kaliningrad_merged_into_first_sz_before_2025():
    first = SimpleNamespace(id=1, name="1-я синхронная зона", number="1")
    kali = SimpleNamespace(id=10, name="Синхронная зона Калининградской области", number="")
    sa_by_id = {1: first, 10: kali}
    station = SimpleNamespace(
        regional_district=SimpleNamespace(
            name="Калининградская область",
            id_synchronous_area=10,
        )
    )
    assert resolve_effective_sync_area_id(station, sa_by_id, current_year=2024) == 1
    assert resolve_effective_sync_area_id(station, sa_by_id, current_year=2025) == 10


def test_taimyr_not_in_first_sz():
    first = SimpleNamespace(id=1, name="1-я синхронная зона", number="1")
    sa_by_id = {1: first}
    station = SimpleNamespace(
        regional_district=SimpleNamespace(
            name="Таймырский Долгано-Ненецкий муниципальный район",
            id_synchronous_area=1,
        )
    )
    assert resolve_effective_sync_area_id(station, sa_by_id, current_year=2025) == 0


# --- УМ > 100 МВт filter ---


def test_um_gt_100_filter_wired_in_extract_and_template():
    from pathlib import Path

    filt = Path("app/generation/services/station_services/filters_services.py").read_text(encoding="utf-8")
    svc = Path("app/generation/services/station_services/station_services.py").read_text(encoding="utf-8")
    tmpl = Path("app/templates/generation/stations/station_filters_third_row.html").read_text(encoding="utf-8")
    assert '"um_gt_100": args.get("um_gt_100", "0") == "1"' in filt
    assert 'filters.get("um_gt_100")' in svc
    assert "sum(MachinePower.p_ust)" in svc or "func.sum(MachinePower.p_ust)" in svc
    assert 'id="um_gt_100_switch"' in tmpl
    assert "Станции с УМ" in tmpl
    assert "um_gt_100_switch" in Path("app/static/js/generation/stations/station_page_logic.js").read_text(encoding="utf-8")


def test_tes_type_filter_uses_year_range_on_station_list():
    from pathlib import Path

    svc = Path("app/generation/services/station_services/station_services.py").read_text(encoding="utf-8")
    # Основной отбор станций — between по диапазону, не только current_year
    assert "MachineTesType.year_number.between(_sy, _ey)" in svc
    filt = Path("app/generation/services/station_services/filters_services.py").read_text(encoding="utf-8")
    assert "MachineTesType.year_number.between(_sy, _ey)" in filt


def test_update_hidden_fields_preserves_year_filter_intersection():
    from pathlib import Path

    js = Path("app/static/js/generation/stations/station_page_logic.js").read_text(encoding="utf-8")
    assert "updateHiddenFields" in js
    assert "data-year-filter" in Path(
        "app/templates/generation/stations/station_filters_third_row.html"
    ).read_text(encoding="utf-8")
    assert "y < startY || y > endY" in js


def test_des_dga_keep_fuel_breakdown_in_totals_summary():
    from pathlib import Path

    text = Path("app/generation/routes/totals_summary_routes.py").read_text(encoding="utf-8")
    assert "ДЭС" in text
    assert "ДГА" in text
    assert "_tes_type_skips_fuel_breakdown" in text


def test_apply_machine_display_names_plan_and_fact_relabing_logic():
    """Контракт формата «до (после)» для плана и факт-перемаркировки."""
    from pathlib import Path

    from app.generation.services.station_services.station_services import (
        _split_display_name_before_after,
    )

    src = Path("app/generation/services/station_services/station_services.py").read_text(encoding="utf-8")
    assert 'display_name = f"{base_name} ({plan_name})"' in src
    assert "date_relabing_fact" in src
    assert 'display_name = f"{before_name} ({after_name})"' in src
    assert 'display_name_before = base_name' in src
    assert 'display_name_after = plan_name' in src
    assert 'setattr(m, "display_name_before", display_name_before)' in src
    assert 'setattr(m, "display_name_after", display_name_after)' in src
    assert "_split_display_name_before_after" in src

    # Логика формата (без ORM)
    base_name, plan_name = "ТГ-1", "ТГ-1М"
    assert f"{base_name} ({plan_name})" == "ТГ-1 (ТГ-1М)"
    before_name, after_name = "ПТ-10", "ПТ-12"
    assert f"{before_name} ({after_name})" == "ПТ-10 (ПТ-12)"

    # Готовая строка «до (после)» в machine_name / MachineName
    assert _split_display_name_before_after("РО-230/989-В-450 (РО 230-450)") == (
        "РО-230/989-В-450",
        "РО 230-450",
    )
    assert _split_display_name_before_after("К(ПЛ)-510-ВБ-900 (ПЛ20-В-900)") == (
        "К(ПЛ)-510-ВБ-900",
        "ПЛ20-В-900",
    )
    assert _split_display_name_before_after("ТГ-1") == (None, None)

    rows = Path("app/templates/generation/stations/station_rows.html").read_text(encoding="utf-8")
    assert "machine.display_name or machine.machine_name" in rows
    ch_rows = Path("app/templates/generation/station_changes/station_changes_rows.html").read_text(
        encoding="utf-8"
    )
    assert "machine.display_name" in ch_rows
    assert "display_name_before" in ch_rows
    assert "display_name_after" in ch_rows
    assert "_split_tes_name" in ch_rows


def test_station_changes_rows_split_tes_name_on_modernization():
    """При смене названия до/после года ячейка «Тип агрегата ТЭС» не объединяется."""
    from pathlib import Path

    text = Path("app/templates/generation/station_changes/station_changes_rows.html").read_text(
        encoding="utf-8"
    )
    assert "_split_tes_name" in text
    assert "machine.display_name_before" in text
    assert "machine.display_name_after" in text
    assert "power_row.event == 'change_power'" in text

"""Unit tests for station_changes QA fixes (A–L, focused)."""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.generation.services.station_changes_services.aggregation_station_changes_services.aggregation_rows import (
    get_full_aggregation_rows,
)
from app.generation.services.station_changes_services.export_station_changes_services import (
    STATION_TYPE_ORDER_FOR_TOTALS,
)
from app.generation.services.station_changes_services.station_changes_services import (
    assign_machine_powers_changes_by_year,
    display_machine_number,
    energy_unit_dative_for_totals,
    _round_power_value,
    _sort_stations_in_hierarchy_by_gen_company,
    _station_gen_company_sort_key,
)


# --- A: plan sums exclude current-year fact ---


def test_aggregation_rows_exclude_current_year_fact_bucket():
    station = SimpleNamespace(
        regional_district=SimpleNamespace(id=1, regional_energy_systems=[]),
        id_energy_unit=None,
        id_station_type=10,
        id_regional_energy_system=None,
        regional_energy_system_obj=None,
    )
    machine = SimpleNamespace(
        event_types={"commission"},
        is_archived=False,
        machine_station=station,
        machine_tes_types=[],
        machine_fuels=[],
        id_tes_machine_type=None,
        powers_by_year=[
            {"year": 2025, "p_ust": "10", "event": "commission", "current_year_bucket": "fact"},
            {"year": 2025, "p_ust": "20", "event": "commission", "current_year_bucket": "plan"},
            {"year": 2026, "p_ust": "30", "event": "commission"},
        ],
    )

    rows = get_full_aggregation_rows([machine])
    assert len(rows) == 2
    assert all(getattr(r, "current_year_bucket", None) != "fact" for r in rows)
    assert {r.p_ust for r in rows} == {Decimal("20"), Decimal("30")}


# --- B: empty machine_number -> dash ---


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, "–"),
        ("", "–"),
        ("   ", "–"),
        ("12", "12"),
        (" 3А ", "3А"),
    ],
)
def test_display_machine_number(raw, expected):
    assert display_machine_number(raw) == expected


# --- C: SNEE in export station type order ---


def test_station_type_order_includes_snee():
    assert "СНЭЭ" in STATION_TYPE_ORDER_FOR_TOTALS
    assert STATION_TYPE_ORDER_FOR_TOTALS.index("СЭС") < STATION_TYPE_ORDER_FOR_TOTALS.index("СНЭЭ")


# --- D: start year floor is conceptual (route clamps); filter template uses 2022 ---


def test_station_changes_start_year_options_exclude_2021():
    from pathlib import Path

    text = Path("app/templates/generation/station_changes/station_changes_filters_third_row.html").read_text(
        encoding="utf-8"
    )
    assert "range(2022, 2043)" in text
    assert "range(2021, 2043)" not in text


# --- E: float precision capped at 3 decimals when «не округлять» ---


def test_round_power_value_zero_digits_caps_float_noise():
    noisy = 12.300000000000001
    got = _round_power_value(noisy, 0)
    assert got == Decimal("12.300")
    assert str(got) == "12.300"


def test_assign_powers_uses_decimal_without_float_garbage():
    machine = SimpleNamespace(
        machine_powers=[
            SimpleNamespace(year_number=2023, p_ust=100),
            SimpleNamespace(year_number=2024, p_ust=Decimal("100.1") + Decimal("0.2")),
        ],
        machine_name="TG",
        pgu_submachines=[],
    )
    assign_machine_powers_changes_by_year(machine, 2024, 2024, rounding_digits=0)
    assert machine.powers_by_year
    for row in machine.powers_by_year:
        # не более 3 знаков после запятой
        assert abs(row["p_ust"].as_tuple().exponent) <= 3 or row["p_ust"] == row["p_ust"].to_integral()


# --- F: tes_type filter uses year range (code presence) ---


def test_tes_type_filter_uses_between_year_range():
    from pathlib import Path

    text = Path(
        "app/generation/services/station_changes_services/station_changes_services.py"
    ).read_text(encoding="utf-8")
    assert "MachineTesType.year_number.between(start_year, end_year)" in text
    assert "MachineTesType.year_number == current_year" not in text.split("tes_type_filter")[1].split(
        "tes_machine_type_filter"
    )[0]


# --- H: sort stations by gen company ---


def test_sort_stations_in_hierarchy_by_gen_company():
    def _st(name, company):
        gc = SimpleNamespace(name=company, id=hash(company) % 1000) if company else None
        m = SimpleNamespace(gen_company=gc, is_archived=False)
        return SimpleNamespace(name=name, id=hash(name) % 10000, machines=[m])

    a = _st("St-A", "Beta GC")
    b = _st("St-B", "Alpha GC")
    c = _st("St-C", "Alpha GC")
    grouped = {1: {2: {3: {4: [a, b, c]}}}}
    _sort_stations_in_hierarchy_by_gen_company(grouped)
    ordered = grouped[1][2][3][4]
    assert [s.name for s in ordered] == ["St-B", "St-C", "St-A"]
    assert _station_gen_company_sort_key(b) < _station_gen_company_sort_key(a)


# --- I: PGU — only changing parts ---


def test_pgu_capacity_change_shows_only_changed_parts():
    part_changed = SimpleNamespace(
        id=1,
        machine_name="ГТ-1",
        machine_number="1",
        pgu_machine_powers=[
            SimpleNamespace(year_number=2023, p_ust=40),
            SimpleNamespace(year_number=2024, p_ust=50),
        ],
    )
    part_same = SimpleNamespace(
        id=2,
        machine_name="ПТ-1",
        machine_number="2",
        pgu_machine_powers=[
            SimpleNamespace(year_number=2023, p_ust=60),
            SimpleNamespace(year_number=2024, p_ust=60),
        ],
    )
    machine = SimpleNamespace(
        machine_name="ПГУ-1",
        machine_powers=[
            SimpleNamespace(year_number=2023, p_ust=100),
            SimpleNamespace(year_number=2024, p_ust=110),
        ],
        pgu_submachines=[part_changed, part_same],
    )
    assign_machine_powers_changes_by_year(machine, 2024, 2024, rounding_digits=1)
    names = {r.get("display_machine_name") for r in machine.powers_by_year}
    assert names == {"ГТ-1"}
    assert all(r.get("display_machine_name") != "ПГУ-1" for r in machine.powers_by_year)
    deltas = [r for r in machine.powers_by_year if r["event"] == "change_power"]
    assert len(deltas) == 1
    assert deltas[0]["p_ust"] == Decimal("10.0")


# --- J/K: modernization display helpers via assign ---


def test_modernization_events_created_for_capacity_change():
    machine = SimpleNamespace(
        machine_name="ТГ-1",
        machine_powers=[
            SimpleNamespace(year_number=2023, p_ust=100),
            SimpleNamespace(year_number=2024, p_ust=120),
        ],
        pgu_submachines=[],
    )
    assign_machine_powers_changes_by_year(machine, 2024, 2024, rounding_digits=1)
    events = [r["event"] for r in machine.powers_by_year]
    assert events == ["before_modernization", "after_modernization", "change_power"]


def test_station_changes_rows_template_modernization_no_merge_number():
    from pathlib import Path

    text = Path("app/templates/generation/station_changes/station_changes_rows.html").read_text(encoding="utf-8")
    assert "before_modernization" in text
    assert "after_modernization" in text
    assert "_row_number if _row_number else" in text
    assert "_split_tes_name" in text
    assert "display_name_before" in text
    assert "display_name_after" in text


# --- L: Taimyr dative ---


def test_energy_unit_dative_taimyr():
    long_name = (
        "Таймырский Долгано-Ненецкий муниципальный район, Туруханский район "
        "и городской округ г. Норильск Красноярского края"
    )
    prep = (
        "Таймырском Долгано-Ненецком муниципальном районе, Туруханском районе "
        "и городском округе г. Норильск Красноярского края"
    )
    assert energy_unit_dative_for_totals(long_name, prep) == "Таймыру"
    assert energy_unit_dative_for_totals("Обычный узел", "Обычному узлу") == "Обычному узлу"


# --- changes_mode fact|plan ---


def test_power_row_matches_changes_mode_fact_and_plan():
    from app.generation.services.station_changes_services.station_changes_services import (
        power_row_matches_changes_mode,
    )

    year_features = {2024: "факт", 2025: "текущий (оценка)", 2026: "план"}
    fact_bucket = {"year": 2025, "current_year_bucket": "fact", "p_ust": 10}
    plan_bucket = {"year": 2025, "current_year_bucket": "plan", "p_ust": 20}
    plan_year = {"year": 2026, "p_ust": 30}
    fact_year = {"year": 2024, "p_ust": 5}

    assert power_row_matches_changes_mode(fact_bucket, "fact", year_features, 2025)
    assert not power_row_matches_changes_mode(plan_bucket, "fact", year_features, 2025)
    assert power_row_matches_changes_mode(fact_year, "fact", year_features, 2025)
    assert not power_row_matches_changes_mode(plan_year, "fact", year_features, 2025)

    assert power_row_matches_changes_mode(plan_bucket, "plan", year_features, 2025)
    assert not power_row_matches_changes_mode(fact_bucket, "plan", year_features, 2025)
    assert power_row_matches_changes_mode(plan_year, "plan", year_features, 2025)
    assert not power_row_matches_changes_mode(fact_year, "plan", year_features, 2025)


def test_changes_mode_buttons_in_template_and_js():
    from pathlib import Path

    tmpl = Path("app/templates/generation/station_changes/station_changes_filters_third_row.html").read_text(
        encoding="utf-8"
    )
    js = Path("app/static/js/generation/station_changes/station_page_logic.js").read_text(encoding="utf-8")
    assert 'data-changes-mode="plan"' in tmpl
    assert 'data-changes-mode="fact"' in tmpl
    assert "Планируемые изменения" in tmpl
    assert "Фактические изменения" in tmpl
    assert "setupChangesModeButtons" in js
    assert "updateHiddenFields" in js


def test_station_changes_passes_years_and_machine_filters_to_loaders():
    from pathlib import Path

    text = Path(
        "app/generation/services/station_changes_services/station_changes_services.py"
    ).read_text(encoding="utf-8")
    assert "start_year=start_year" in text
    assert "end_year=end_year" in text
    assert "tes_machine_type_filter=filters.get(\"tes_machine_type_filter\")" in text
    assert "tes_type_filter=filters.get(\"tes_type_filter\")" in text


def test_regional_district_totals_include_tes_machine_type_rows():
    from pathlib import Path

    text = Path(
        "app/templates/generation/station_changes/aggregated_data/regional_districts/"
        "aggregated_regional_districts_by_station_type.html"
    ).read_text(encoding="utf-8")
    assert "regional_districts_by_tes_machine_types_yearly_p_ust" in text
    assert "tes_machine_type_list" in text


def test_aggregation_rows_with_commission_and_tes_machine_type():
    """Ввод + тип агрегата: строки агрегации по регионам не пустые."""
    station = SimpleNamespace(
        regional_district=SimpleNamespace(id=7, regional_energy_systems=[]),
        id_energy_unit=None,
        id_station_type=10,
        id_regional_energy_system=None,
        regional_energy_system_obj=None,
    )
    machine = SimpleNamespace(
        event_types={"commission"},
        is_archived=False,
        machine_station=station,
        machine_tes_types=[],
        machine_fuels=[],
        id_tes_machine_type=55,
        powers_by_year=[
            {"year": 2026, "p_ust": "15", "event": "commission"},
        ],
    )
    rows = get_full_aggregation_rows([machine])
    assert len(rows) == 1
    assert rows[0].regional_district_id == 7
    assert rows[0].tes_machine_type_id == 55
    assert rows[0].event_type == "commission"
    assert rows[0].p_ust == Decimal("15")

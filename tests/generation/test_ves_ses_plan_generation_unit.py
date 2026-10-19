# -*- coding: utf-8 -*-
"""Расчёт плановой выработки ВЭС/СЭС: 7-летний минимум и сравнение с собственником."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.generation.services.station_services import (
    ves_ses_plan_generation_services as plan_services,
)
from app.generation.services.station_services.ves_ses_plan_generation_services import (
    PLAN_RULE_CAPACITY_SES,
    PLAN_RULE_CAPACITY_SES_PARTIAL,
    PLAN_RULE_CAPACITY_VES,
    PLAN_RULE_MIN_OWNER_SAMPLE_OWNER,
    PLAN_RULE_MIN_OWNER_SAMPLE_SAMPLE,
    PLAN_RULE_OWNER_IN_PLAN,
    PLAN_RULE_SEVEN_YEAR_MIN,
    classify_ves_ses_generation_years,
    compute_ves_ses_plan_generation,
    filter_commission_ramp_sample,
    min_generation_over_sample,
    plan_calc_after_owner_edit,
    plan_generation_explained,
    plan_generation_for_year,
    sample_generation_pairs,
    seven_year_sample_window,
    year_operation_fraction,
)


def test_seven_year_window_is_seven_fact_years_without_current():
    assert seven_year_sample_window(2025) == (2018, 2024)


def test_classify_current_and_plan_years():
    current, plan = classify_ves_ses_generation_years(
        {
            2023: "факт",
            2024: "факт",
            2025: "текущий (оценка)",
            2026: "план",
            2027: "План",
        }
    )
    assert current == 2025
    assert plan == [2026, 2027]


def test_min_sample_uses_only_positive_values():
    energy = {2018: 15, 2019: 0, 2020: 10, 2021: None, 2022: 8, 2023: 12, 2024: 9, 2025: 1}
    assert min_generation_over_sample(
        energy, current_year=2025, commission_year=2010
    ) == Decimal("8")


def test_min_sample_does_not_use_current_year_even_if_smallest():
    energy = {
        2018: 10,
        2019: 9,
        2020: 8,
        2021: 11,
        2022: 12,
        2023: 13,
        2024: 14,
        2025: 1,
    }
    assert min_generation_over_sample(
        energy, current_year=2025, commission_year=2010
    ) == Decimal("8")


def test_new_station_excludes_first_nonzero_year():
    energy = {
        2018: 30,
        2019: 0,
        2021: 5,
        2022: 20,
        2023: 22,
        2024: 21,
        2025: 19,
    }
    pairs = sample_generation_pairs(energy, 2018, 2024)
    filtered = filter_commission_ramp_sample(
        pairs, commission_year=2021, window_start=2018, window_end=2024
    )
    years = [year for year, _value in filtered]
    assert 2021 not in years
    assert min_generation_over_sample(
        energy, current_year=2025, commission_year=2021
    ) == Decimal("20")


def test_second_year_excluded_when_below_half_of_third():
    energy = {
        2022: 10,
        2023: 8,
        2024: 20,
        2025: 18,
    }
    filtered = filter_commission_ramp_sample(
        sample_generation_pairs(energy, 2019, 2025),
        commission_year=2022,
        window_start=2019,
        window_end=2025,
    )
    years = [year for year, _value in filtered]
    assert years == [2024, 2025]
    assert min_generation_over_sample(
        energy, current_year=2025, commission_year=2022
    ) == Decimal("20")


def test_second_year_kept_when_at_least_half_of_third():
    energy = {2022: 4, 2023: 12, 2024: 20, 2025: 19}
    filtered = filter_commission_ramp_sample(
        sample_generation_pairs(energy, 2019, 2025),
        commission_year=2022,
        window_start=2019,
        window_end=2025,
    )
    years = [year for year, _value in filtered]
    assert years == [2023, 2024, 2025]


def test_plan_year_is_min_of_owner_and_sample():
    value = plan_generation_for_year(
        2026,
        owner_by_year={2026: Decimal("15")},
        min_sample=Decimal("8.7"),
        commission_year=2010,
        plan_years=[2026, 2027],
    )
    assert value == Decimal("8.7")


def test_plan_year_uses_owner_when_owner_is_smaller():
    value = plan_generation_for_year(
        2026,
        owner_by_year={2026: Decimal("5")},
        min_sample=Decimal("8.7"),
        commission_year=2010,
        plan_years=[2026],
    )
    assert value == Decimal("5")


def test_zero_owner_does_not_participate():
    value = plan_generation_for_year(
        2026,
        owner_by_year={2026: Decimal("0")},
        min_sample=Decimal("8.7"),
        commission_year=2010,
        plan_years=[2026],
    )
    assert value == Decimal("8.7")


def test_commission_in_plan_without_owner_uses_ses_capacity_factor():
    value = plan_generation_for_year(
        2028,
        owner_by_year={},
        min_sample=Decimal("8.7"),
        commission_year=2028,
        plan_years=[2026, 2027, 2028],
        capacity_by_year={2028: Decimal("10")},
        type_key="ses",
    )
    assert value == Decimal("15")


def test_commission_in_plan_without_owner_uses_ves_capacity_factor():
    value = plan_generation_for_year(
        2027,
        owner_by_year={2027: Decimal("0")},
        min_sample=None,
        commission_year=2027,
        plan_years=[2026, 2027],
        capacity_by_year={2027: Decimal("10")},
        type_key="ves",
    )
    assert value == Decimal("25")


def test_commission_in_plan_with_owner_keeps_owner_over_capacity():
    value = plan_generation_for_year(
        2028,
        owner_by_year={2028: Decimal("112.74")},
        min_sample=Decimal("8.7"),
        commission_year=2028,
        plan_years=[2026, 2027, 2028],
        capacity_by_year={2028: Decimal("10")},
        type_key="ses",
    )
    assert value == Decimal("112.74")


def test_plan_capacity_fallback_when_first_capacity_is_in_plan():
    value = plan_generation_for_year(
        2026,
        owner_by_year={},
        min_sample=None,
        commission_year=None,
        plan_years=[2026, 2027],
        capacity_by_year={2024: None, 2025: Decimal("0"), 2026: Decimal("72"), 2027: Decimal("72")},
        type_key="ses",
    )
    assert value == Decimal("108")


def test_year_operation_fraction_december_start_non_leap():
    assert year_operation_fraction(date(2025, 12, 1), 2025) == Decimal(31) / Decimal(365)
    assert year_operation_fraction(date(2025, 12, 1), 2026) == Decimal(1)
    assert year_operation_fraction(date(2025, 12, 1), 2024) == Decimal(0)


def test_year_operation_fraction_leap_year():
    assert year_operation_fraction(date(2024, 12, 1), 2024) == Decimal(31) / Decimal(366)


def test_capacity_fallback_prorates_by_exploitation_date():
    # 1.5 * 72 * 31/365
    value, rule = plan_generation_explained(
        2025,
        owner_by_year={},
        min_sample=None,
        commission_year=2025,
        plan_years=[2025, 2026],
        capacity_by_year={2025: Decimal("72"), 2026: Decimal("72")},
        type_key="ses",
        exploitation_date_expected="01.12.2025",
    )
    assert value == Decimal("72") * Decimal("1.5") * Decimal(31) / Decimal(365)
    assert rule == PLAN_RULE_CAPACITY_SES_PARTIAL

    full_year = plan_generation_for_year(
        2026,
        owner_by_year={},
        min_sample=None,
        commission_year=2025,
        plan_years=[2025, 2026],
        capacity_by_year={2025: Decimal("72"), 2026: Decimal("72")},
        type_key="ses",
        exploitation_date_expected="01.12.2025",
    )
    assert full_year == Decimal("108")


def test_capacity_fallback_when_commission_is_current_year():
    """Новая станция: ввод в текущем году → план с 2026 считается от Руст."""
    min_sample, calculated, rules = compute_ves_ses_plan_generation(
        {},
        {},
        current_year=2025,
        plan_years=[2026, 2027],
        commission_year=2025,
        capacity_by_year={
            2025: Decimal("72"),
            2026: Decimal("72"),
            2027: Decimal("72"),
        },
        type_key="ses",
        exploitation_date_expected="01.12.2025",
    )
    assert min_sample is None
    assert calculated[2025] == Decimal("72") * Decimal("1.5") * Decimal(31) / Decimal(365)
    assert calculated[2026] == Decimal("108")
    assert calculated[2027] == Decimal("108")
    assert rules[2025] == PLAN_RULE_CAPACITY_SES_PARTIAL
    assert rules[2026] == PLAN_RULE_CAPACITY_SES


def test_compute_fills_each_plan_year():
    energy = {2018: 11.0, 2019: 10.8, 2020: 9.7, 2021: 10.4, 2022: 9.8, 2023: 9.9, 2024: 8.72, 2025: 1.0}
    owner = {2026: 20, 2027: 7}
    min_sample, calculated, rules = compute_ves_ses_plan_generation(
        energy,
        owner,
        current_year=2025,
        plan_years=[2026, 2027],
        commission_year=2010,
    )
    assert min_sample == Decimal("8.72")
    assert calculated[2026] == Decimal("8.72")
    assert calculated[2027] == Decimal("7")
    assert rules[2026] == PLAN_RULE_MIN_OWNER_SAMPLE_SAMPLE
    assert rules[2027] == PLAN_RULE_MIN_OWNER_SAMPLE_OWNER


def test_plan_rule_capacity_ses():
    value, rule = plan_generation_explained(
        2026,
        owner_by_year={},
        min_sample=None,
        commission_year=None,
        plan_years=[2026, 2027],
        capacity_by_year={2026: Decimal("72")},
        type_key="ses",
    )
    assert value == Decimal("108")
    assert rule == PLAN_RULE_CAPACITY_SES


def test_plan_rule_capacity_ves():
    value, rule = plan_generation_explained(
        2027,
        owner_by_year={},
        min_sample=None,
        commission_year=2027,
        plan_years=[2026, 2027],
        capacity_by_year={2027: Decimal("10")},
        type_key="ves",
    )
    assert value == Decimal("25")
    assert rule == PLAN_RULE_CAPACITY_VES


def test_plan_rule_owner_in_plan_period():
    value, rule = plan_generation_explained(
        2028,
        owner_by_year={2028: Decimal("112.74")},
        min_sample=Decimal("8.7"),
        commission_year=2028,
        plan_years=[2026, 2027, 2028],
        capacity_by_year={2028: Decimal("10")},
        type_key="ses",
    )
    assert value == Decimal("112.74")
    assert rule == PLAN_RULE_OWNER_IN_PLAN


def test_plan_rule_seven_year_min_without_owner():
    value, rule = plan_generation_explained(
        2026,
        owner_by_year={},
        min_sample=Decimal("8.7"),
        commission_year=2010,
        plan_years=[2026],
    )
    assert value == Decimal("8.7")
    assert rule == PLAN_RULE_SEVEN_YEAR_MIN


def test_ramp_empties_sample_uses_ves_capacity_factor():
    min_sample, calculated, rules = compute_ves_ses_plan_generation(
        {2024: Decimal("2.86967")},
        {},
        current_year=2025,
        plan_years=[2026, 2027],
        commission_year=2023,
        capacity_by_year={
            2023: Decimal("2.425"),
            2024: Decimal("2.425"),
            2026: Decimal("2.425"),
            2027: Decimal("2.425"),
        },
        type_key="ves",
    )
    expected = Decimal("2.425") * Decimal("2.5")
    assert min_sample is None
    assert calculated == {2026: expected, 2027: expected}
    assert rules[2026] == PLAN_RULE_CAPACITY_VES
    assert 2025 not in calculated


def test_old_station_empty_sample_does_not_use_capacity_factor():
    value = plan_generation_for_year(
        2026,
        owner_by_year={},
        min_sample=None,
        commission_year=2010,
        plan_years=[2026],
        capacity_by_year={2010: Decimal("10"), 2026: Decimal("10")},
        type_key="ves",
        current_year=2025,
    )
    assert value is None


def test_decommissioned_year_skips_min_sample_when_capacity_zero():
    value, rule = plan_generation_explained(
        2026,
        owner_by_year={},
        min_sample=Decimal("0.2"),
        commission_year=2010,
        plan_years=[2026, 2027],
        capacity_by_year={2022: Decimal("0.5"), 2023: Decimal("0"), 2026: Decimal("0")},
        type_key="ves",
    )
    assert value is None
    assert rule is None


def test_min_sample_kept_when_capacity_positive():
    value = plan_generation_for_year(
        2026,
        owner_by_year={},
        min_sample=Decimal("0.2"),
        commission_year=2010,
        plan_years=[2026],
        capacity_by_year={2020: Decimal("0.5"), 2026: Decimal("0.5")},
        type_key="ves",
    )
    assert value == Decimal("0.2")


def test_station_type_key_ses_ves():
    from app.energy_balance.services.ee_balance_ves_ses_page_services import _station_type_key

    assert _station_type_key("СЭС") == "ses"
    assert _station_type_key("ВЭС (Р)") == "ves"
    assert _station_type_key("ТЭС") == "other"


def test_ves_ses_rows_empty_without_types(monkeypatch):
    from app.energy_balance.services.ee_balance_ves_ses_page_services import (
        build_ves_ses_page_rows,
    )

    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_ves_ses_page_services.ves_ses_station_type_ids",
        lambda: [],
    )
    assert build_ves_ses_page_rows([2024, 2025], digits=1, year_features={})[0] == []


def _plan_after_owner_edit(calculated, rules, **overrides):
    """План-расчёт в том виде, в каком его отдаёт station_plan_generation."""
    plan = {
        "current_year": 2025,
        "plan_years": [2026, 2027, 2028],
        "energy_by_year": {},
        "owner_by_year": {},
        "commission_year": 2028,
        "capacity_by_year": {2028: Decimal("10")},
        "type_key": "ses",
        "exploitation_date_expected": "",
        "min_sample": None,
        "calculated": calculated,
        "rules": rules,
    }
    plan.update(overrides)
    return plan


def _patch_plan(monkeypatch, plan):
    monkeypatch.setattr(
        plan_services, "station_plan_generation", lambda *_args, **_kwargs: plan
    )


def test_owner_edit_fills_empty_plan_cell_for_station_commissioned_in_plan(monkeypatch):
    """Ввод в плановом периоде: пустая ячейка выработки получает выработку собственника."""
    plan = _plan_after_owner_edit(
        {2028: Decimal("112.74")},
        {2028: PLAN_RULE_OWNER_IN_PLAN},
        owner_by_year={2028: Decimal("112.74")},
    )
    _patch_plan(monkeypatch, plan)

    value, rule = plan_services.plan_calc_after_owner_edit(
        SimpleNamespace(),
        year=2028,
        start_year=2024,
        end_year=2031,
        previous_owner_value="",
        station_version_id=4,
    )

    assert value == Decimal("112.74")
    assert rule == PLAN_RULE_OWNER_IN_PLAN


def test_owner_edit_skips_plan_cell_with_manual_value(monkeypatch):
    """Значение, введённое прямо в таблице выработки, правкой собственника не трогаем."""
    plan = _plan_after_owner_edit(
        {2028: Decimal("112.74")},
        {2028: PLAN_RULE_OWNER_IN_PLAN},
        owner_by_year={2028: Decimal("112.74")},
        energy_by_year={2028: Decimal("90")},
    )
    _patch_plan(monkeypatch, plan)

    value, rule = plan_services.plan_calc_after_owner_edit(
        SimpleNamespace(),
        year=2028,
        start_year=2024,
        end_year=2031,
        previous_owner_value="10",
        station_version_id=4,
    )

    assert (value, rule) == (None, None)


def test_owner_edit_keeps_sync_when_stored_value_is_rounded_calc(monkeypatch):
    """В БД расчёт лежит с точностью Numeric(25, 16): хвост дроби не мешает синхронизации."""
    # Расчёт до правки: 1,5 × 72 × 31/366 (ввод 01.12.2028) = 9,147540983606557377...
    calc_before = Decimal(72) * Decimal("1.5") * Decimal(31) / Decimal(366)
    stored = Decimal("9.1475409836065574")
    plan = _plan_after_owner_edit(
        {2028: Decimal("50")},
        {2028: PLAN_RULE_OWNER_IN_PLAN},
        owner_by_year={2028: Decimal("50")},
        energy_by_year={2028: stored},
        capacity_by_year={2028: Decimal("72")},
        exploitation_date_expected="01.12.2028",
    )
    _patch_plan(monkeypatch, plan)

    value, rule = plan_services.plan_calc_after_owner_edit(
        SimpleNamespace(),
        year=2028,
        start_year=2024,
        end_year=2031,
        previous_owner_value="",
        station_version_id=4,
    )

    assert calc_before != stored
    assert value == Decimal("50")
    assert rule == PLAN_RULE_OWNER_IN_PLAN


def test_owner_edit_syncs_plan_cell_of_long_operating_station(monkeypatch):
    """Ячейка показывала минимум из собственника и выборки: остаётся расчётной."""
    plan = _plan_after_owner_edit(
        {2027: Decimal("7")},
        {2027: PLAN_RULE_MIN_OWNER_SAMPLE_OWNER},
        owner_by_year={2027: Decimal("7")},
        energy_by_year={2024: Decimal("8.72"), 2027: Decimal("8.72")},
        commission_year=2010,
        capacity_by_year={2010: Decimal("10"), 2027: Decimal("10")},
        min_sample=Decimal("8.72"),
    )
    _patch_plan(monkeypatch, plan)

    value, rule = plan_services.plan_calc_after_owner_edit(
        SimpleNamespace(),
        year=2027,
        start_year=2024,
        end_year=2031,
        previous_owner_value="20",
        station_version_id=4,
    )

    assert value == Decimal("7")
    assert rule == PLAN_RULE_MIN_OWNER_SAMPLE_OWNER


def test_owner_edit_without_plan_calc_gives_nothing_to_sync(monkeypatch):
    plan = _plan_after_owner_edit({}, {}, owner_by_year={2025: Decimal("5")})
    _patch_plan(monkeypatch, plan)

    value, rule = plan_services.plan_calc_after_owner_edit(
        SimpleNamespace(),
        year=2025,
        start_year=2024,
        end_year=2031,
        previous_owner_value="",
        station_version_id=4,
    )

    assert (value, rule) == (None, None)


def test_owner_edit_without_plan_for_station(monkeypatch):
    monkeypatch.setattr(
        plan_services, "station_plan_generation", lambda *_args, **_kwargs: None
    )

    value, rule = plan_services.plan_calc_after_owner_edit(
        SimpleNamespace(),
        year=2025,
        start_year=2024,
        end_year=2031,
        previous_owner_value="",
        station_version_id=4,
    )

    assert (value, rule) == (None, None)

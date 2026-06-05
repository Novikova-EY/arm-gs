# -*- coding: utf-8 -*-
"""GET-параметры страницы потребления по ВЭД (годы, фильтры)."""

from __future__ import annotations

from flask import request

from app.common.services.get_services.years.years_get_services import (
    get_filter_end_year,
    get_filter_start_year,
    get_ges_tep_current_price_year_number,
    get_year_numbers_sorted_for_current_db_version,
)


def filter_year_list_for_page() -> list[int]:
    nums = get_year_numbers_sorted_for_current_db_version()
    if nums:
        return nums
    return list(range(get_filter_start_year(), get_filter_end_year() + 1))


def summary_period_base_year_n() -> int:
    n = get_ges_tep_current_price_year_number()
    if n is not None:
        return int(n)
    return int(get_filter_end_year())


SUMMARY_MEDIUM_YEARS_AFTER_N = 6
SUMMARY_LONG_TERM_YEARS_AFTER_N = 17


def parse_include_medium_years() -> bool:
    return str(request.args.get("pd_medium") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def parse_include_long_years() -> bool:
    return str(request.args.get("pd_long") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def expand_years_for_period_segments(
    sy: int,
    ey: int,
    n: int,
    *,
    include_medium_years: bool,
    include_long_years: bool = False,
) -> tuple[int, int]:
    bounds = filter_year_list_for_page()
    if not bounds:
        lo, hi = sy, ey
    else:
        lo, hi = bounds[0], bounds[-1]
    eff_sy = max(lo, min(sy, n - 9))
    cap_ey = n
    if include_medium_years:
        cap_ey = max(cap_ey, n + SUMMARY_MEDIUM_YEARS_AFTER_N)
    if include_long_years:
        cap_ey = max(cap_ey, n + SUMMARY_LONG_TERM_YEARS_AFTER_N)
    eff_ey = min(hi, max(ey, cap_ey))
    if eff_sy > eff_ey:
        eff_sy, eff_ey = eff_ey, eff_sy
    return eff_sy, eff_ey


def parse_summary_year_range() -> tuple[int, int]:
    bounds = filter_year_list_for_page()
    n = summary_period_base_year_n()
    default_sy = n - 9
    default_ey = n
    if bounds:
        lo, hi = bounds[0], bounds[-1]
        default_sy = max(lo, min(default_sy, hi))
        default_ey = max(lo, min(default_ey, hi))
        if default_sy > default_ey:
            default_sy, default_ey = default_ey, default_sy
    sy_raw = request.args.get("start_year")
    ey_raw = request.args.get("end_year")
    try:
        sy = int(sy_raw) if sy_raw not in (None, "") else default_sy
    except (TypeError, ValueError):
        sy = default_sy
    try:
        ey = int(ey_raw) if ey_raw not in (None, "") else default_ey
    except (TypeError, ValueError):
        ey = default_ey
    if sy > ey:
        sy, ey = ey, sy
    if bounds:
        lo, hi = bounds[0], bounds[-1]
        sy = max(lo, min(sy, hi))
        ey = max(lo, min(ey, hi))
    return sy, ey


def parse_federal_district_filter_ids() -> frozenset[int]:
    ids: set[int] = set()
    for raw in request.args.getlist("ds_fd"):
        try:
            ids.add(int(raw))
        except (TypeError, ValueError):
            continue
    return frozenset(ids)


def parse_ved_filter_ids() -> frozenset[int]:
    ids: set[int] = set()
    for raw in request.args.getlist("ds_ved"):
        try:
            ids.add(int(raw))
        except (TypeError, ValueError):
            continue
    return frozenset(ids)


def has_active_ved_filters(
    fd_ids: frozenset[int], ved_ids: frozenset[int]
) -> bool:
    return bool(fd_ids or ved_ids)


def _max_year_segment_presets(n: int) -> tuple[dict[str, bool | int], ...]:
    return (
        {
            "reporting": True,
            "medium": False,
            "long": False,
            "lo": n - 9,
            "hi": n,
            "pd_medium": False,
            "pd_long": False,
        },
        {
            "reporting": False,
            "medium": True,
            "long": False,
            "lo": n + 1,
            "hi": n + SUMMARY_MEDIUM_YEARS_AFTER_N,
            "pd_medium": True,
            "pd_long": False,
        },
        {
            "reporting": False,
            "medium": False,
            "long": True,
            "lo": n + 1,
            "hi": n + SUMMARY_LONG_TERM_YEARS_AFTER_N,
            "pd_medium": False,
            "pd_long": True,
        },
        {
            "reporting": True,
            "medium": True,
            "long": False,
            "lo": n - 9,
            "hi": n + SUMMARY_MEDIUM_YEARS_AFTER_N,
            "pd_medium": True,
            "pd_long": False,
        },
        {
            "reporting": True,
            "medium": False,
            "long": True,
            "lo": n - 9,
            "hi": n + SUMMARY_LONG_TERM_YEARS_AFTER_N,
            "pd_medium": False,
            "pd_long": True,
        },
        {
            "reporting": False,
            "medium": True,
            "long": True,
            "lo": n + 1,
            "hi": n + SUMMARY_LONG_TERM_YEARS_AFTER_N,
            "pd_medium": True,
            "pd_long": True,
        },
        {
            "reporting": True,
            "medium": True,
            "long": True,
            "lo": n - 9,
            "hi": n + SUMMARY_LONG_TERM_YEARS_AFTER_N,
            "pd_medium": True,
            "pd_long": True,
        },
    )


def infer_max_year_segment_state(
    start_year: int,
    end_year: int,
    n: int,
    include_medium: bool,
    include_long: bool = False,
) -> dict[str, bool | str]:
    """Состояние кнопок периодов по URL (как inferStateFromUrlForm в demand_summary_year_period_mode.js)."""
    for c in _max_year_segment_presets(n):
        if (
            start_year == c["lo"]
            and end_year == c["hi"]
            and include_medium == c["pd_medium"]
            and include_long == c["pd_long"]
        ):
            return {
                "mode": "segments",
                "reporting": c["reporting"],
                "medium": c["medium"],
                "long": c["long"],
            }
    return {"mode": "manual", "reporting": False, "medium": False, "long": False}


def build_visible_years_for_max_year_segment_state(
    state: dict[str, bool | str],
    n: int,
    *,
    start_year: int,
    end_year: int,
) -> set[int]:
    """Годы, видимые в таблице (как buildVisibleYears в demand_summary_year_period_mode.js)."""
    visible: set[int] = set()
    if state.get("mode") == "manual":
        lo = min(start_year, end_year)
        hi = max(start_year, end_year)
        visible.update(range(lo, hi + 1))
        return visible
    reporting = state.get("reporting") is True
    medium = state.get("medium") is True
    long = state.get("long") is True
    if reporting:
        visible.update(range(n - 9, n + 1))
    if medium:
        visible.update(range(n + 1, n + SUMMARY_MEDIUM_YEARS_AFTER_N + 1))
    if long:
        visible.update(range(n + 1, n + SUMMARY_LONG_TERM_YEARS_AFTER_N + 1))
    return visible


def compute_initial_visible_years_for_max_year_table(
    *,
    display_years: list[int],
    start_year: int,
    end_year: int,
    coeff_base_year: int,
    summary_include_medium_years: bool,
    summary_include_long_years: bool = False,
) -> frozenset[int]:
    """Начальная видимость колонок годов без sessionStorage (первая отрисовка страницы)."""
    state = infer_max_year_segment_state(
        start_year,
        end_year,
        coeff_base_year,
        summary_include_medium_years,
        summary_include_long_years,
    )
    visible = build_visible_years_for_max_year_segment_state(
        state,
        coeff_base_year,
        start_year=start_year,
        end_year=end_year,
    )
    return frozenset(y for y in display_years if y in visible)


def parse_ved_consumption_page_kwargs(*, rounding_digits: int) -> dict:
    sy, ey = parse_summary_year_range()
    n = summary_period_base_year_n()
    include_medium = parse_include_medium_years()
    eff_sy, eff_ey = expand_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
    )
    year_list = filter_year_list_for_page()
    display_years = [y for y in year_list if eff_sy <= y <= eff_ey]
    if not display_years and year_list:
        display_years = [y for y in year_list if sy <= y <= ey] or year_list
    fd_ids = parse_federal_district_filter_ids()
    ved_ids = parse_ved_filter_ids()
    return {
        "rounding_digits": rounding_digits,
        "start_year": sy,
        "end_year": ey,
        "data_start_year": eff_sy,
        "data_end_year": eff_ey,
        "display_years": display_years,
        "filter_year_list": year_list,
        "coeff_base_year": n,
        "summary_include_medium_years": include_medium,
        "fd_filter_ids": fd_ids,
        "ved_filter_ids": ved_ids,
        "has_active_filters": has_active_ved_filters(fd_ids, ved_ids),
    }

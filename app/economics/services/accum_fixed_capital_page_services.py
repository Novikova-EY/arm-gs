# -*- coding: utf-8 -*-
"""GET-параметры страницы накопленных инвестиций в основной капитал (годы, фильтры)."""

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


def parse_include_medium_years() -> bool:
    return str(request.args.get("pd_medium") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def expand_years_for_period_segments(
    sy: int, ey: int, n: int, *, include_medium_years: bool
) -> tuple[int, int]:
    bounds = filter_year_list_for_page()
    if not bounds:
        lo, hi = sy, ey
    else:
        lo, hi = bounds[0], bounds[-1]
    eff_sy = max(lo, min(sy, n - 9))
    cap_ey = n + 6 if include_medium_years else n
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


def parse_accum_fixed_capital_page_kwargs(*, rounding_digits: int) -> dict:
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

# -*- coding: utf-8 -*-
"""GET-параметры страницы численности населения (годы, фильтры)."""

from __future__ import annotations

from flask import request

from app.economics.services.ved_consumption_page_services import (
    expand_years_for_period_segments,
    filter_year_list_for_page,
    infer_max_year_segment_state,
    parse_include_long_years,
    parse_include_medium_years,
    parse_summary_year_range,
    summary_period_base_year_n,
)


def parse_federal_district_filter_ids() -> frozenset[int]:
    ids: set[int] = set()
    for raw in request.args.getlist("ds_fd"):
        try:
            ids.add(int(raw))
        except (TypeError, ValueError):
            continue
    return frozenset(ids)


def parse_population_page_kwargs(*, rounding_digits: int) -> dict:
    sy, ey = parse_summary_year_range()
    n = summary_period_base_year_n()
    include_medium = parse_include_medium_years()
    include_long = parse_include_long_years()
    eff_sy, eff_ey = expand_years_for_period_segments(
        sy,
        ey,
        n,
        include_medium_years=include_medium,
        include_long_years=include_long,
    )
    year_list = filter_year_list_for_page()
    display_years = [y for y in year_list if eff_sy <= y <= eff_ey]
    if not display_years and year_list:
        display_years = [y for y in year_list if sy <= y <= ey] or year_list
    fd_ids = parse_federal_district_filter_ids()
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
        "summary_include_long_years": include_long,
        "lt_ved_year_seg_state": infer_max_year_segment_state(
            sy, ey, n, include_medium, include_long
        ),
        "fd_filter_ids": fd_ids,
        "has_active_filters": bool(fd_ids),
    }

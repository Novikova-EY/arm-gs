# -*- coding: utf-8 -*-

"""GET-параметры страницы электроёмкости."""



from __future__ import annotations



from flask import request



from app.economics.services.ved_consumption_page_services import (

    SUMMARY_LONG_TERM_YEARS_AFTER_N,

    compute_initial_visible_years_for_max_year_table,

    expand_years_for_period_segments,

    filter_year_list_for_page,

    has_active_ved_filters,

    infer_max_year_segment_state,

    parse_federal_district_filter_ids,

    summary_period_base_year_n,

)

from app.electrical_intensity.services.electrical_intensity_constants import (
    EI_COEFFICIENT_X_AVG_START_YEAR,
    POPULATION_SECTION_MARKER,
)





def _parse_period_flag_default_true(param: str) -> bool:

    """Флаг периода на электроёмкости: включён, если параметр отсутствует или равен 1."""

    raw = request.args.get(param)

    if raw is None or str(raw).strip() == "":

        return True

    return str(raw).strip().lower() in ("1", "true", "yes", "on")





def parse_electrical_intensity_include_medium_years() -> bool:

    return _parse_period_flag_default_true("pd_medium")





def parse_electrical_intensity_include_long_years() -> bool:

    return _parse_period_flag_default_true("pd_long")





def parse_electrical_intensity_summary_year_range() -> tuple[int, int]:

    """По умолчанию — полный диапазон отчётного + среднесрочного + долгосрочного периода."""

    bounds = filter_year_list_for_page()

    n = summary_period_base_year_n()

    default_sy = EI_COEFFICIENT_X_AVG_START_YEAR

    default_ey = n + SUMMARY_LONG_TERM_YEARS_AFTER_N

    if bounds:

        lo, hi = bounds[0], bounds[-1]

        default_sy = max(lo, min(default_sy, hi))

        default_ey = max(lo, min(default_ey, hi))

        if default_sy > default_ey:

            default_sy, default_ey = default_ey, default_sy

    sy_raw = request.args.get("start_year") or request.form.get("start_year")

    ey_raw = request.args.get("end_year") or request.form.get("end_year")

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





def parse_electrical_intensity_ved_filters() -> tuple[frozenset[int], bool]:
    """Парсинг ds_ved: целочисленные id ВЭД и маркер блока «Население» (population)."""

    ids: set[int] = set()
    include_population = False
    for raw in request.args.getlist("ds_ved"):
        s = str(raw).strip()
        if s == POPULATION_SECTION_MARKER:
            include_population = True
            continue
        try:
            ids.add(int(s))
        except (TypeError, ValueError):
            continue
    return frozenset(ids), include_population


def parse_electrical_intensity_page_kwargs(*, rounding_digits: int) -> dict:

    sy, ey = parse_electrical_intensity_summary_year_range()

    n = summary_period_base_year_n()

    include_medium = parse_electrical_intensity_include_medium_years()

    include_long = parse_electrical_intensity_include_long_years()

    eff_sy, eff_ey = expand_years_for_period_segments(

        sy, ey, n, include_medium_years=include_medium, include_long_years=include_long

    )

    year_list = filter_year_list_for_page()

    display_years = [y for y in year_list if eff_sy <= y <= eff_ey]

    if not display_years and year_list:

        display_years = [y for y in year_list if sy <= y <= ey] or year_list

    fd_ids = parse_federal_district_filter_ids()

    ved_ids, population_filter_selected = parse_electrical_intensity_ved_filters()

    seg_state = infer_max_year_segment_state(

        sy, ey, n, include_medium, include_long

    )

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

        "lt_ei_year_seg_state": seg_state,

        "lt_ei_initial_visible_years": compute_initial_visible_years_for_max_year_table(

            display_years=display_years,

            start_year=sy,

            end_year=ey,

            coeff_base_year=n,

            summary_include_medium_years=include_medium,

            summary_include_long_years=include_long,

        ),

        "fd_filter_ids": fd_ids,

        "ved_filter_ids": ved_ids,

        "population_filter_selected": population_filter_selected,

        "has_active_filters": has_active_ved_filters(fd_ids, ved_ids)
        or population_filter_selected,

    }


# -*- coding: utf-8 -*-
"""Годы фильтров страниц энергобаланса: отчётное окно N−9…N (текущий год)."""

from __future__ import annotations

from urllib.parse import urlencode

from flask import redirect, request

from app.common.services.get_services.years.years_get_services import (
    get_filter_end_year,
    get_filter_start_year,
    get_ges_tep_current_price_year_number,
    get_year_list_full,
)
from app.generation.services.station_services.generation_year_filter_services import (
    sync_generation_years_session_on_version_change,
)


def _normalize_start_end_years(start_year: int, end_year: int) -> tuple[int, int]:
    if start_year > end_year:
        return end_year, start_year
    return start_year, end_year


def get_ee_period_base_year() -> int:
    """Текущий год N для отчётного окна N−9…N (как на сводке потребления)."""
    n = get_ges_tep_current_price_year_number()
    if n is not None:
        return int(n)
    return int(get_filter_end_year())


def get_ee_default_start_year() -> int:
    return get_ee_period_base_year() - 9


def get_ee_default_end_year() -> int:
    return get_ee_period_base_year()


def get_ee_filter_year_list() -> list[int]:
    """Годы для выпадающих списков на страницах энергобаланса (отчётное окно N−9…N)."""
    start = get_ee_default_start_year()
    end = get_ee_default_end_year()
    years = sorted(
        {
            int(year.number)
            for year in get_year_list_full()
            if year.number is not None and start <= int(year.number) <= end
        }
    )
    if years:
        return years
    return list(range(start, end + 1))


def _is_generation_planning_year_range(start_year: int, end_year: int) -> bool:
    return start_year == get_filter_start_year() and end_year == get_filter_end_year()


def resolve_ee_year_filters_for_request():
    """
    Возвращает (start_year, end_year, redirect_response).

    По умолчанию — отчётное окно N−9…N (текущий год), а не период планирования СиПР.
    """
    default_start = get_ee_default_start_year()
    default_end = get_ee_default_end_year()
    version_changed = sync_generation_years_session_on_version_change()

    if version_changed:
        url_start = request.args.get("start_year", type=int)
        url_end = request.args.get("end_year", type=int)
        if request.method == "GET" and (url_start is not None or url_end is not None):
            if url_start != default_start or url_end != default_end:
                q = request.args.to_dict(flat=True)
                q["start_year"] = default_start
                q["end_year"] = default_end
                return default_start, default_end, redirect(f"{request.path}?{urlencode(q)}")
        return default_start, default_end, None

    start_year = request.args.get("start_year", default_start, type=int)
    end_year = request.args.get("end_year", default_end, type=int)
    start_year, end_year = _normalize_start_end_years(start_year, end_year)
    return start_year, end_year, None


def resolve_ee_transfers_year_filters_for_request():
    """
    Годы для страницы «Перетоки ЭЭ».

    Не подхватывает из URL период планирования СиПР (2024–2031 и т.п.) —
    для отчётных данных используется окно N−9…N.
    """
    start_year, end_year, redirect_response = resolve_ee_year_filters_for_request()
    if redirect_response is not None:
        return start_year, end_year, redirect_response

    start_year, end_year = resolve_ee_transfers_year_range()
    url_start = request.args.get("start_year", type=int)
    url_end = request.args.get("end_year", type=int)
    default_start = get_ee_default_start_year()
    default_end = get_ee_default_end_year()
    if (
        request.method == "GET"
        and url_start is not None
        and url_end is not None
        and _is_generation_planning_year_range(url_start, url_end)
        and (url_start != default_start or url_end != default_end)
    ):
        query = request.args.to_dict(flat=True)
        query["start_year"] = default_start
        query["end_year"] = default_end
        return default_start, default_end, redirect(f"{request.path}?{urlencode(query)}")

    return start_year, end_year, None


def resolve_ee_transfers_year_range() -> tuple[int, int]:
    """Диапазон лет перетоков без HTTP-редиректа (экспорт и пр.)."""
    default_start = get_ee_default_start_year()
    default_end = get_ee_default_end_year()
    url_start = request.args.get("start_year", type=int)
    url_end = request.args.get("end_year", type=int)
    if url_start is None and url_end is None:
        return default_start, default_end
    start_year = url_start if url_start is not None else default_start
    end_year = url_end if url_end is not None else default_end
    if _is_generation_planning_year_range(start_year, end_year):
        return default_start, default_end
    return _normalize_start_end_years(start_year, end_year)

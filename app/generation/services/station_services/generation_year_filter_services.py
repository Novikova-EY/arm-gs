# -*- coding: utf-8 -*-
"""Годы фильтров страниц генерации: период планирования и смена версии БД."""

from __future__ import annotations

from urllib.parse import urlencode

from flask import redirect, request, session

from app.common.services.database_version_filter import get_current_db_version_id
from app.common.services.get_services.years.years_get_services import (
    get_filter_end_year,
    get_filter_start_year,
)

GENERATION_YEARS_VERSION_SESSION_KEY = "generation_years_version_id"
STATION_LIST_FILTERS_SESSION_KEY = "station_list_last_query_args"


def _normalize_start_end_years(start_year: int, end_year: int) -> tuple[int, int]:
    if start_year > end_year:
        return end_year, start_year
    return start_year, end_year


def _strip_years_from_station_list_session() -> None:
    saved = session.get(STATION_LIST_FILTERS_SESSION_KEY)
    if not isinstance(saved, dict):
        return
    changed = False
    for key in ("start_year", "end_year"):
        if key in saved:
            saved.pop(key, None)
            changed = True
    if changed:
        session[STATION_LIST_FILTERS_SESSION_KEY] = saved
        session.modified = True


def sync_generation_years_session_on_version_change() -> bool:
    """
    Фиксирует смену версии БД в сессии и сбрасывает сохранённые годы station_list.
    Возвращает True, если версия изменилась с прошлего запроса.
    """
    version_id = get_current_db_version_id()
    prev_version_id = session.get(GENERATION_YEARS_VERSION_SESSION_KEY)
    if prev_version_id == version_id:
        return False

    session[GENERATION_YEARS_VERSION_SESSION_KEY] = version_id
    session.modified = True
    _strip_years_from_station_list_session()
    return True


def resolve_generation_year_filters_for_request():
    """
    Возвращает (start_year, end_year, redirect_response).

    При смене версии БД подставляет период планирования с /refdata/ и при необходимости
    делает redirect с обновлёнными start_year/end_year в query string.
    """
    default_start = get_filter_start_year()
    default_end = get_filter_end_year()
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

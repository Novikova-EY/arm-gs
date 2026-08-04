# -*- coding: utf-8 -*-
"""Общие хелперы страницы «Расчёт» (параметры распределения / этапы Коэфф–Распред–Топливо)."""
from urllib.parse import urlencode, urlparse

from flask import redirect, request, url_for

# После успешного POST этапа «Распред» — сырой JSON-сериализуемый словарь для таблицы на GET /fuel/calculation.
FUEL_DISTRIBUTION_LAST_RUN_SESSION_KEY = "fuel_distribution_last_run"
# После успешного POST этапа «Топливо» — сводка для таблицы на GET /fuel/calculation.
FUEL_STAGE_LAST_RUN_SESSION_KEY = "fuel_stage_last_run"
# После успешного POST этапа «Коэфф» — метаданные запуска (таблицы Коэфф — из сводки БД).
FUEL_COEFF_LAST_RUN_SESSION_KEY = "fuel_coeff_last_run"

# Query-параметры формы /fuel/calculation (без диагностик edit_data вроде equipment_group_ids).
FUEL_CALCULATION_FORM_QUERY_KEYS = (
    "start_year",
    "base_year",
    "union_energy_system_filter",
    "tes_type_filter",
    "apply_restrictions",
    "distribution_parameter_id",
)


def fuel_calculation_form_query_string(args=None) -> str:
    """
    Query string только с фильтрами страницы «Расчёт».

    Не тащит equipment_group_ids / show_empty_rows / per_page со страниц edit_data
    (ссылка «Без удельника»), иначе «Назад к расчёту» и кнопка «ТЭП» снова открывают
    ту же узкую выборку.
    """
    src = args if args is not None else request.args
    pairs = []
    for key in FUEL_CALCULATION_FORM_QUERY_KEYS:
        getlist = getattr(src, "getlist", None)
        values = getlist(key) if callable(getlist) else [src.get(key)]
        for v in values:
            if v is None:
                continue
            pairs.append((key, v))
    return urlencode(pairs)


def fuel_calculation_tep_edit_query_string(
    *,
    base_year: int | None,
    calc_year: int | None,
    args=None,
) -> str:
    """
    Query для кнопки «ТЭП… (редактирование)» с формы расчёта.

    На странице ТЭП: Год начала = базовый, Год конца = расчётный.
    base_year сохраняется в query для «Назад к расчёту».
    «Пустые строки» по умолчанию включены (кнопка нажата; show_empty_rows не обязателен).
    """
    src = args if args is not None else request.args
    pairs: list[tuple[str, str]] = []
    for key in FUEL_CALCULATION_FORM_QUERY_KEYS:
        if key in ("start_year", "base_year", "end_year"):
            continue
        getlist = getattr(src, "getlist", None)
        values = getlist(key) if callable(getlist) else [src.get(key)]
        for v in values:
            if v is None or v == "":
                continue
            pairs.append((key, str(v)))

    interval_start = base_year if base_year is not None else calc_year
    interval_end = calc_year if calc_year is not None else base_year
    if interval_start is not None:
        pairs.append(("start_year", str(interval_start)))
    if interval_end is not None:
        pairs.append(("end_year", str(interval_end)))
    if base_year is not None:
        pairs.append(("base_year", str(base_year)))
    return urlencode(pairs)


def fuel_calculation_form_url_from_tep_edit_args(args=None) -> str:
    """
    «Назад к расчёту» со страницы ТЭП edit_data.

    Расчётный год (start_year на форме расчёта) = end_year интервала ТЭП,
    базовый = base_year (или start_year интервала, если base_year нет).
    """
    src = args if args is not None else request.args
    pairs: list[tuple[str, str]] = []
    for key in FUEL_CALCULATION_FORM_QUERY_KEYS:
        if key in ("start_year", "base_year", "end_year"):
            continue
        getlist = getattr(src, "getlist", None)
        values = getlist(key) if callable(getlist) else [src.get(key)]
        for v in values:
            if v is None or v == "":
                continue
            pairs.append((key, str(v)))

    get = getattr(src, "get", None)
    ey = get("end_year") if callable(get) else None
    sy = get("start_year") if callable(get) else None
    by = get("base_year") if callable(get) else None
    if by in (None, ""):
        by = None
    if ey in (None, ""):
        ey = None
    if sy in (None, ""):
        sy = None

    calc_year = ey or sy
    base_year = by
    if base_year is None and sy is not None and ey is not None and str(sy) != str(ey):
        base_year = sy

    if calc_year is not None:
        pairs.append(("start_year", str(calc_year)))
    if base_year is not None:
        pairs.append(("base_year", str(base_year)))

    base = url_for("fuel_bp.fuel_calculation_form")
    qs = urlencode(pairs)
    return f"{base}?{qs}" if qs else base


def fuel_calculation_form_url(args=None) -> str:
    """URL /fuel/calculation с whitelist-фильтрами формы."""
    base = url_for("fuel_bp.fuel_calculation_form")
    qs = fuel_calculation_form_query_string(args)
    return f"{base}?{qs}" if qs else base


def redirect_back_after_post():
    """После POST сохраняем query string страницы расчёта (фильтры), если referrer локальный."""
    ref = (request.referrer or "").strip()
    if ref:
        try:
            path = urlparse(ref).path.rstrip("/")
            if path.endswith("/fuel/calculation"):
                return redirect(ref)
        except Exception:
            pass
    return redirect(url_for("fuel_bp.fuel_calculation_form"))

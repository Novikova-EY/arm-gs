from __future__ import annotations

from typing import Any

from flask import jsonify, render_template, request, send_file
from flask_login import current_user, login_required

from app.common.services.get_services.years.years_get_services import (
    get_filter_end_year,
    get_filter_start_year,
    get_ges_tep_current_price_year_number,
    get_year_list_full,
)
from app.power_demand.routes.power_demand_bp import power_demand_bp
from app.power_demand.services.access_services import can_edit_power_demand
from app.power_demand.services.demand_summary_export_services import (
    build_demand_summary_excel_stream,
)
from app.common.services.database_version_services import get_current_version
from app.logs.services.log_display_utils import format_logs_for_display
from app.power_demand.services import demand_parameter_services as dps
from app.power_demand.services.demand_summary_logging import (
    PD_SUMMARY_LOGS_INITIAL_LIMIT,
    PD_SUMMARY_LOGS_LOAD_MORE_LIMIT,
    count_pd_summary_logs,
    load_formatted_pd_summary_logs,
    load_pd_summary_logs_raw,
)
from app.power_demand.services.pd_summary_formula_template_vars import (
    inject_pd_formula_template_variables,
)
from app.power_demand.services.formula_text.power_demand_summary_formula_text_services import (
    apply_row_formula_text_overrides,
    build_pd_formula_texts_map,
)
from app.power_demand.services.demand_summary_client_render_services import (
    build_client_render_config,
    build_summary_data_json_response,
)
from app.power_demand.services.pd_summary_data_segments import (
    PD_SUMMARY_SEGMENT_CORE,
    filter_summary_rows_for_data_segments,
    needs_full_summary_build,
    parse_pd_data_segments,
)
from app.power_demand.services.pd_summary_entity_pagination import (
    parse_pd_entity_pagination,
)
from app.power_demand.services.pd_summary_page_cache import (
    cached_load_pd_summary_data,
    clear_pd_summary_page_cache,
)
from app.power_demand.services.demand_summary_services import (
    EZ_EXPORT_PARAMETER_KEYS,
    FO_COEFF_EXPORT_PARAMETER_KEYS,
    FO_EXPORT_PARAMETER_KEYS,
    OES_EXPORT_PARAMETER_KEYS,
    apply_power_demand_oes_summary_nt_export_ui,
    apply_power_demand_summary_export_entity_label_overrides,
    apply_power_demand_summary_screen_entity_labels,
    apply_power_demand_summary_territory_compact_export_ui,
    build_energy_zones_summary_context,
    build_energy_zones_summary_context_coeff,
    build_federal_district_summary_context,
    build_federal_district_summary_context_coeff,
    build_oes_summary_context,
    build_oes_summary_context_coeff,
    enrich_summary_rows_coeff_k_columns,
    filter_summary_rows_for_parameter_keys,
    filter_summary_rows_hide_empty_entity_blocks,
    get_demand_summary_filter_refdata,
    get_power_demand_ez_filter_cascade_data,
    get_power_demand_fo_filter_cascade_data,
    get_power_demand_oes_filter_cascade_data,
    parse_power_demand_export_hide_empty,
    parse_power_demand_export_hist,
    parse_power_demand_export_nt_detail,
    parse_power_demand_export_territory_compact,
    slice_coeff_summary_for_lazy_long_segment,
    slice_power_demand_summary_context_for_export_years,
)


DEFAULT_SUMMARY_COEFF_K_ROUNDING_DIGITS = 3


def _attach_pd_summary_logs(context: dict) -> None:
    scope = context.get("active_summary")
    if scope not in ("oes", "fo", "ez"):
        return
    vid = get_current_version()
    context["pd_summary_logs_formatted"] = load_formatted_pd_summary_logs(
        str(scope), vid, limit=PD_SUMMARY_LOGS_INITIAL_LIMIT
    )
    context["pd_summary_logs_initial_limit"] = PD_SUMMARY_LOGS_INITIAL_LIMIT
    context["pd_summary_logs_load_more_limit"] = PD_SUMMARY_LOGS_LOAD_MORE_LIMIT


def _attach_pd_summary_formula_texts(context: dict) -> None:
    formula_texts = build_pd_formula_texts_map()
    context["pd_formula_texts"] = formula_texts
    inject_pd_formula_template_variables(context, formula_texts)
    apply_row_formula_text_overrides(context.get("summary_rows"))


def _attach_pd_summary_client_render(context: dict, *, scope: str, data_path: str) -> None:
    context["pd_summary_client_render"] = True
    context["pd_summary_client_render_config"] = build_client_render_config(
        scope=scope,
        data_path=data_path,
    )


def _build_summary_data_json_response(
    *, scope: str, context_builder, cache_scope: str | None = None
) -> Any:
    data_segments = parse_pd_data_segments(scope)
    entity_pagination = parse_pd_entity_pagination(scope)

    def loader() -> dict:
        context = context_builder(for_shell=False, data_segments=data_segments)
        boundary_rows = None
        if (
            entity_pagination is not None
            and entity_pagination[1] > 0
            and not needs_full_summary_build(data_segments)
            # core пагинируется целиком (prefix + секции + суффикс ТИТЭС);
            # boundary нужен только для ленивых сегментов (chi, ee, nt_extra, …).
            and data_segments != frozenset({PD_SUMMARY_SEGMENT_CORE})
        ):
            core_context = context_builder(
                for_shell=False,
                data_segments=frozenset({PD_SUMMARY_SEGMENT_CORE}),
            )
            boundary_rows = core_context.get("summary_rows")
        payload = build_summary_data_json_response(
            context,
            entity_pagination=entity_pagination,
            pagination_boundary_rows=boundary_rows,
        ).get_json()
        payload["loaded_segments"] = sorted(data_segments)
        return payload

    return jsonify(cached_load_pd_summary_data(cache_scope or scope, loader))


def _parse_oes_max_summary_args() -> dict:
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
    )
    oes_ordered = _parse_oes_territory_ordered()
    ues_l, res_l, rd_l, eu_l = oes_ordered
    return {
        "sy": sy,
        "ey": ey,
        "include_medium": include_medium,
        "eff_sy": eff_sy,
        "eff_ey": eff_ey,
        "oes_ordered": oes_ordered,
        "ues_l": ues_l,
        "res_l": res_l,
        "rd_l": rd_l,
        "eu_l": eu_l,
    }


def _build_oes_max_summary_context(*, for_shell: bool, data_segments=None) -> dict:
    args = _parse_oes_max_summary_args()
    context = build_oes_summary_context(
        _parse_rounding_digits(),
        start_year=args["sy"],
        end_year=args["ey"],
        data_start_year=args["eff_sy"],
        data_end_year=args["eff_ey"],
        filter_year_list=_filter_year_list_for_summary(),
        oes_territory_ordered=args["oes_ordered"],
        for_client_render_shell=for_shell,
        data_segments=data_segments,
    )
    if for_shell:
        context.update(get_demand_summary_filter_refdata())
        context["pd_oes_filters_cascade"] = get_power_demand_oes_filter_cascade_data()
    context["can_edit_summary_cells"] = can_edit_power_demand(current_user)
    context["has_active_summary_filters"] = bool(
        args["ues_l"] or args["res_l"] or args["rd_l"] or args["eu_l"]
    )
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = _summary_period_base_year_n()
    context["summary_include_medium_years"] = args["include_medium"]
    _attach_pd_summary_formula_texts(context)
    if for_shell:
        context["pd_summary_logs_lazy"] = True
        context["pd_summary_logs_initial_limit"] = PD_SUMMARY_LOGS_INITIAL_LIMIT
        context["pd_summary_logs_load_more_limit"] = PD_SUMMARY_LOGS_LOAD_MORE_LIMIT
    return context


def _parse_fo_max_summary_args() -> dict:
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
    )
    fo_sets = _parse_fo_filter_sets()
    f_fd, f_res = fo_sets
    return {
        "sy": sy,
        "ey": ey,
        "include_medium": include_medium,
        "eff_sy": eff_sy,
        "eff_ey": eff_ey,
        "fo_sets": fo_sets,
        "f_fd": f_fd,
        "f_res": f_res,
    }


def _build_fo_max_summary_context(*, for_shell: bool, data_segments=None) -> dict:
    args = _parse_fo_max_summary_args()
    context = build_federal_district_summary_context(
        _parse_rounding_digits(),
        start_year=args["sy"],
        end_year=args["ey"],
        data_start_year=args["eff_sy"],
        data_end_year=args["eff_ey"],
        filter_year_list=_filter_year_list_for_summary(),
        fo_filter_sets=args["fo_sets"],
        fo_aggregate_by_res=True,
        fo_max_extended_parameters=True,
        for_client_render_shell=for_shell,
        data_segments=data_segments,
    )
    if for_shell:
        context.update(get_demand_summary_filter_refdata())
        context["pd_fo_filters_cascade"] = get_power_demand_fo_filter_cascade_data()
    context["can_edit_summary_cells"] = can_edit_power_demand(current_user)
    context["has_active_summary_filters"] = bool(args["f_fd"] or args["f_res"])
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = _summary_period_base_year_n()
    context["summary_include_medium_years"] = args["include_medium"]
    _attach_pd_summary_formula_texts(context)
    if for_shell:
        context["pd_summary_logs_lazy"] = True
        context["pd_summary_logs_initial_limit"] = PD_SUMMARY_LOGS_INITIAL_LIMIT
        context["pd_summary_logs_load_more_limit"] = PD_SUMMARY_LOGS_LOAD_MORE_LIMIT
    return context


def _parse_ez_max_summary_args() -> dict:
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
    )
    ez_ordered = _parse_ez_territory_ordered()
    ez_l, res_l = ez_ordered
    return {
        "sy": sy,
        "ey": ey,
        "include_medium": include_medium,
        "eff_sy": eff_sy,
        "eff_ey": eff_ey,
        "ez_ordered": ez_ordered,
        "ez_l": ez_l,
        "res_l": res_l,
    }


def _build_ez_max_summary_context(*, for_shell: bool, data_segments=None) -> dict:
    args = _parse_ez_max_summary_args()
    context = build_energy_zones_summary_context(
        _parse_rounding_digits(),
        start_year=args["sy"],
        end_year=args["ey"],
        data_start_year=args["eff_sy"],
        data_end_year=args["eff_ey"],
        filter_year_list=_filter_year_list_for_summary(),
        ez_territory_ordered=args["ez_ordered"],
        ez_max_extended_parameters=True,
        for_client_render_shell=for_shell,
        data_segments=data_segments,
    )
    if for_shell:
        context.update(get_demand_summary_filter_refdata())
        context["pd_ez_filters_cascade"] = get_power_demand_ez_filter_cascade_data()
    context["can_edit_summary_cells"] = can_edit_power_demand(current_user)
    context["has_active_summary_filters"] = bool(args["ez_l"] or args["res_l"])
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = _summary_period_base_year_n()
    context["summary_include_medium_years"] = args["include_medium"]
    _attach_pd_summary_formula_texts(context)
    if for_shell:
        context["pd_summary_logs_lazy"] = True
        context["pd_summary_logs_initial_limit"] = PD_SUMMARY_LOGS_INITIAL_LIMIT
        context["pd_summary_logs_load_more_limit"] = PD_SUMMARY_LOGS_LOAD_MORE_LIMIT
    return context


def _coeff_build_segments_for_k_enrichment(
    data_segments: frozenset[str] | None,
) -> frozenset[str] | None:
    """Для k нужен max_power в блоке: при ленивых сегментах временно включаем core."""
    if data_segments is None or needs_full_summary_build(data_segments):
        return data_segments
    if PD_SUMMARY_SEGMENT_CORE in data_segments:
        return data_segments
    return frozenset(data_segments | {PD_SUMMARY_SEGMENT_CORE})


def _finalize_coeff_summary_context(
    context: dict,
    *,
    scope: str,
    for_shell: bool,
    data_segments: frozenset[str] | None,
    coeff_n: int,
    coeff_include_long: bool,
) -> dict:
    context["rounding_digits_k"] = _parse_rounding_digits_k(
        fallback=DEFAULT_SUMMARY_COEFF_K_ROUNDING_DIGITS
    )
    context["can_edit_summary_cells"] = can_edit_power_demand(current_user)
    context["summary_route_variant"] = "coeff"
    context["coeff_base_year"] = coeff_n
    context["coeff_period_header_groups"] = _coeff_period_header_groups_html(
        include_long=coeff_include_long
    )
    if not for_shell:
        _apply_coeff_year_k_columns(context)
        build_segs = _coeff_build_segments_for_k_enrichment(data_segments)
        if (
            data_segments is not None
            and build_segs is not None
            and data_segments != build_segs
        ):
            context["summary_rows"] = filter_summary_rows_for_data_segments(
                context.get("summary_rows"),
                data_segments,
                scope=scope,
            )
        slice_coeff_summary_for_lazy_long_segment(
            context, coeff_n, include_long=coeff_include_long
        )
    else:
        # Shell: только метаданные/годы (без строк); срез долгосрочных колонок для thead.
        slice_coeff_summary_for_lazy_long_segment(
            context, coeff_n, include_long=coeff_include_long
        )
        context["summary_rows"] = []
    _apply_coeff_ui_year_form_context(context, coeff_n)
    _attach_pd_summary_formula_texts(context)
    if for_shell:
        context["pd_summary_logs_lazy"] = True
        context["pd_summary_logs_initial_limit"] = PD_SUMMARY_LOGS_INITIAL_LIMIT
        context["pd_summary_logs_load_more_limit"] = PD_SUMMARY_LOGS_LOAD_MORE_LIMIT
    return context


def _build_oes_coeff_summary_context(*, for_shell: bool, data_segments=None) -> dict:
    coeff_n, start_year, end_year = _parse_coeff_summary_year_range()
    coeff_include_long = _parse_coeff_include_long()
    oes_ordered = _parse_oes_territory_ordered()
    ues_l, res_l, rd_l, eu_l = oes_ordered
    build_segs = (
        None
        if for_shell
        else _coeff_build_segments_for_k_enrichment(data_segments)
    )
    context = build_oes_summary_context_coeff(
        _parse_rounding_digits(),
        start_year=start_year,
        end_year=end_year,
        filter_year_list=_filter_year_list_for_summary(),
        oes_territory_ordered=oes_ordered,
        for_client_render_shell=for_shell,
        data_segments=build_segs,
    )
    if for_shell:
        context.update(get_demand_summary_filter_refdata())
        context["pd_oes_filters_cascade"] = get_power_demand_oes_filter_cascade_data()
    context["has_active_summary_filters"] = bool(ues_l or res_l or rd_l or eu_l)
    return _finalize_coeff_summary_context(
        context,
        scope="oes",
        for_shell=for_shell,
        data_segments=data_segments,
        coeff_n=coeff_n,
        coeff_include_long=coeff_include_long,
    )


def _build_fo_coeff_summary_context(*, for_shell: bool, data_segments=None) -> dict:
    coeff_n, start_year, end_year = _parse_coeff_summary_year_range()
    coeff_include_long = _parse_coeff_include_long()
    fo_sets = _parse_fo_filter_sets()
    f_fd, f_res = fo_sets
    build_segs = (
        None
        if for_shell
        else _coeff_build_segments_for_k_enrichment(data_segments)
    )
    context = build_federal_district_summary_context_coeff(
        _parse_rounding_digits(),
        start_year=start_year,
        end_year=end_year,
        filter_year_list=_filter_year_list_for_summary(),
        fo_filter_sets=fo_sets,
        for_client_render_shell=for_shell,
        data_segments=build_segs,
    )
    if for_shell:
        context.update(get_demand_summary_filter_refdata())
        context["pd_fo_filters_cascade"] = get_power_demand_fo_filter_cascade_data()
    context["has_active_summary_filters"] = bool(f_fd or f_res)
    return _finalize_coeff_summary_context(
        context,
        scope="fo",
        for_shell=for_shell,
        data_segments=data_segments,
        coeff_n=coeff_n,
        coeff_include_long=coeff_include_long,
    )


def _build_ez_coeff_summary_context(*, for_shell: bool, data_segments=None) -> dict:
    coeff_n, start_year, end_year = _parse_coeff_summary_year_range()
    coeff_include_long = _parse_coeff_include_long()
    ez_ordered = _parse_ez_territory_ordered()
    ez_l, res_l = ez_ordered
    build_segs = (
        None
        if for_shell
        else _coeff_build_segments_for_k_enrichment(data_segments)
    )
    context = build_energy_zones_summary_context_coeff(
        _parse_rounding_digits(),
        start_year=start_year,
        end_year=end_year,
        filter_year_list=_filter_year_list_for_summary(),
        ez_territory_ordered=ez_ordered,
        for_client_render_shell=for_shell,
        data_segments=build_segs,
    )
    if for_shell:
        context.update(get_demand_summary_filter_refdata())
        context["pd_ez_filters_cascade"] = get_power_demand_ez_filter_cascade_data()
    context["has_active_summary_filters"] = bool(ez_l or res_l)
    return _finalize_coeff_summary_context(
        context,
        scope="ez",
        for_shell=for_shell,
        data_segments=data_segments,
        coeff_n=coeff_n,
        coeff_include_long=coeff_include_long,
    )


def _parse_rounding_digits() -> int:
    raw = request.args.get("rounding_digits")
    if raw is None or str(raw).strip() == "":
        return 1
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 1
    if value == -1:
        return -1
    if value in (0, 1, 2, 3):
        return value
    return 1


def _parse_rounding_digits_k(*, fallback: int | None = None) -> int:
    """Округление строк k на сводках «Коэффициенты…»; без параметра — fallback (на coeff-страницах 3 знака)."""
    raw = request.args.get("rounding_digits_k")
    if raw is None or str(raw).strip() == "":
        return _parse_rounding_digits() if fallback is None else fallback
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return _parse_rounding_digits() if fallback is None else fallback
    if value == -1:
        return -1
    if value in (0, 1, 2, 3):
        return value
    return _parse_rounding_digits() if fallback is None else fallback


def _filter_year_list_for_summary() -> list[int]:
    nums = sorted({y.number for y in get_year_list_full()})
    if nums:
        return nums
    return list(range(get_filter_start_year(), get_filter_end_year() + 1))


def _coeff_base_year_n() -> int:
    """
    N — календарный год с признаком «текущий», иначе «текущий (оценка)»,
    иначе конец стандартного диапазона (как get_ges_tep_current_price_year_number + fallback).
    """
    n = get_ges_tep_current_price_year_number()
    if n is not None:
        return int(n)
    return int(get_filter_end_year())


def _summary_period_base_year_n() -> int:
    """N для колонок «отчётный N−9…N», «среднесрочный N+1…N+6» (как на сводке потребления и коэффициентах)."""
    return _coeff_base_year_n()


def _parse_summary_include_medium_years() -> bool:
    """GET pd_medium=1 — подгрузить столбцы N+1…N+6 (кнопка «Среднесрочный период» на сводке «максимумы»)."""
    return str(request.args.get("pd_medium") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _expand_summary_years_for_period_segments(
    sy: int, ey: int, n: int, *, include_medium_years: bool
) -> tuple[int, int]:
    """Объединить выбранный диапазон с отчётным окном N−9…N; при include_medium_years — ещё с N+1…N+6."""
    bounds = _filter_year_list_for_summary()
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


def _parse_summary_year_range() -> tuple[int, int]:
    """По умолчанию — отчётное окно N−9…N (как кнопка «Отчётный период»), в границах справочника Year."""
    bounds = _filter_year_list_for_summary()
    n = _summary_period_base_year_n()
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
    if sy > ey:
        sy, ey = ey, sy
    return sy, ey


def _parse_coeff_summary_year_range() -> tuple[int, int, int]:
    """(N, start_year, end_year) для «Коэффициенты…»: N−9…N+18 (28 лет)."""
    n = _coeff_base_year_n()
    return n, n - 9, n + 18


def _parse_coeff_ui_year_form_range(coeff_n: int) -> tuple[int, int, bool]:
    """
    Диапазон для формы «Год начала/конца» на страницах «Коэффициенты…».

    Данные таблицы по-прежнему N−9…N+18 (со срезом долгосрочного сегмента).
    Если в URL есть start_year/end_year — считаем диапазон применённым (ручной режим отображения).
    Без параметров в URL — по умолчанию отчётное окно N−9…N (как на «Максимумы…»).
    """
    bounds = _filter_year_list_for_summary()
    default_sy = int(coeff_n) - 9
    default_ey = int(coeff_n)
    if bounds:
        lo, hi = bounds[0], bounds[-1]
        default_sy = max(lo, min(default_sy, hi))
        default_ey = max(lo, min(default_ey, hi))
        if default_sy > default_ey:
            default_sy, default_ey = default_ey, default_sy
    sy_raw = request.args.get("start_year")
    ey_raw = request.args.get("end_year")
    applied = sy_raw not in (None, "") and ey_raw not in (None, "")
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
    if sy > ey:
        sy, ey = ey, sy
    return sy, ey, applied


def _apply_coeff_ui_year_form_context(context: dict, coeff_n: int) -> None:
    """Подставить годы формы и флаг ручного выбора на страницах coeff."""
    ui_sy, ui_ey, applied = _parse_coeff_ui_year_form_range(coeff_n)
    context["start_year"] = ui_sy
    context["end_year"] = ui_ey
    context["pd_coeff_years_applied"] = applied


def _coeff_period_header_groups(n: int) -> list[dict[str, str | int]]:
    """По два столбца (k, МВт) на каждый год периода."""
    return [
        {"label": "Отчетный период", "colspan": 20, "key": "reporting"},
        {"label": "Среднесрочный период", "colspan": 12, "key": "medium"},
        {"label": "Долгосрочный период", "colspan": 24, "key": "long"},
    ]


def _coeff_period_header_groups_html(*, include_long: bool) -> list[dict[str, str | int]]:
    """Шапка «Коэффициенты…»: без догрузки долгосрочного сегмента третья группа не выводится."""
    groups: list[dict[str, str | int]] = [
        {"label": "Отчетный период", "colspan": 20, "key": "reporting"},
        {"label": "Среднесрочный период", "colspan": 12, "key": "medium"},
    ]
    if include_long:
        groups.append({"label": "Долгосрочный период", "colspan": 24, "key": "long"})
    return groups


def _parse_coeff_include_long() -> bool:
    return str(request.args.get("coeff_include_long") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _parse_ordered_unique_int_ids(arg_name: str) -> list[int]:
    """Порядок значений в URL сохраняется (для объединения фильтров по раундам)."""
    seen: set[int] = set()
    out: list[int] = []
    for raw in request.args.getlist(arg_name):
        try:
            v = int(raw)
        except (TypeError, ValueError):
            continue
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _parse_oes_territory_ordered() -> tuple[list[int], list[int], list[int], list[int]]:
    return (
        _parse_ordered_unique_int_ids("ds_ues"),
        _parse_ordered_unique_int_ids("ds_res"),
        _parse_ordered_unique_int_ids("ds_rd"),
        _parse_ordered_unique_int_ids("ds_eu"),
    )


def _parse_fo_filter_sets() -> tuple[frozenset[int], frozenset[int]]:
    return (
        frozenset(_parse_ordered_unique_int_ids("ds_fd")),
        frozenset(_parse_ordered_unique_int_ids("ds_res")),
    )


def _parse_ez_territory_ordered() -> tuple[list[int], list[int]]:
    return (
        _parse_ordered_unique_int_ids("ds_ez"),
        _parse_ordered_unique_int_ids("ds_res"),
    )


def _parse_summary_export_visible_keys(allowed: frozenset[str]) -> frozenset[str] | None:
    """GET visible_rows=a,b,c — только ключи из whitelist; None = все строки."""
    raw = request.args.get("visible_rows")
    if raw is None or str(raw).strip() == "":
        return None
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    keys = [p for p in parts if p in allowed]
    if not keys:
        return None
    return frozenset(keys)


def _parse_export_entity_label_overrides() -> dict[str, str]:
    """Подписи энергосистем с экрана: JSON-тело POST или GET export_entity_labels."""
    raw = None
    if request.method == "POST":
        payload = request.get_json(silent=True)
        if isinstance(payload, dict):
            raw = payload.get("export_entity_labels")
    if raw is None:
        raw = request.args.get("export_entity_labels")
    if raw is None:
        return {}
    if isinstance(raw, str):
        raw_s = raw.strip()
        if not raw_s:
            return {}
        try:
            import json

            raw = json.loads(raw_s)
        except (TypeError, ValueError):
            return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key, label in raw.items():
        ks = str(key or "").strip()
        ls = str(label or "").strip()
        if ks and ls:
            out[ks] = ls
    return out


def _apply_summary_export_view_filters(
    context: dict,
    allowed_keys: frozenset[str],
) -> dict:
    """Применить к context те же ограничения строк, что на экране (кнопки / пикер / пустые)."""
    sub_years = _parse_export_years_list(list(context.get("years") or []))
    if sub_years is not None:
        context = slice_power_demand_summary_context_for_export_years(context, sub_years)
    visible = _parse_summary_export_visible_keys(allowed_keys)
    if visible is not None:
        context["summary_rows"] = filter_summary_rows_for_parameter_keys(
            context["summary_rows"], visible
        )
    nt_detail_on = parse_power_demand_export_nt_detail()
    territory_compact_on = parse_power_demand_export_territory_compact()
    context["summary_rows"] = apply_power_demand_oes_summary_nt_export_ui(
        context["summary_rows"],
        nt_detail_on=nt_detail_on,
    )
    context["summary_rows"] = apply_power_demand_summary_territory_compact_export_ui(
        context["summary_rows"],
        territory_compact_on=territory_compact_on,
    )
    context["summary_rows"] = apply_power_demand_summary_screen_entity_labels(
        context["summary_rows"],
        nt_detail_on=nt_detail_on,
        territory_compact_on=territory_compact_on,
    )
    context["summary_rows"] = apply_power_demand_summary_export_entity_label_overrides(
        context["summary_rows"],
        _parse_export_entity_label_overrides(),
    )
    context["summary_rows"] = filter_summary_rows_hide_empty_entity_blocks(
        context["summary_rows"],
        hide_empty=parse_power_demand_export_hide_empty(),
    )
    return context


def _parse_export_years_list(full_years: list[int]) -> list[int] | None:
    """GET export_years=2015,2016,... — подмножество full_years, порядок как в запросе."""
    raw = request.args.get("export_years")
    if raw is None or str(raw).strip() == "":
        return None
    allowed = set(full_years)
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    if not parts:
        return None
    out: list[int] = []
    for p in parts:
        try:
            y = int(p)
        except (TypeError, ValueError):
            return None
        if y not in allowed:
            return None
        if y not in out:
            out.append(y)
    return out


def _apply_coeff_year_k_columns(context: dict) -> None:
    """Для «Коэффициенты…»: k = значение / макс. мощность года (блок строк)."""
    coeff_n = context.get("coeff_base_year")
    if coeff_n is None:
        coeff_n = _coeff_base_year_n()
    rd_k = context.get("rounding_digits_k")
    if rd_k is None:
        rd_k = DEFAULT_SUMMARY_COEFF_K_ROUNDING_DIGITS
    enrich_summary_rows_coeff_k_columns(
        context["summary_rows"],
        context["years"],
        context["rounding_digits"],
        context.get("year_is_plan") or {},
        rounding_digits_k=rd_k,
        coeff_base_year=int(coeff_n),
    )


def _demand_summary_excel_response(
    context: dict, filename_prefix: str, *, export_coeff_k_columns: bool = False
):
    coeff_excel = None
    if export_coeff_k_columns:
        coeff_excel = context.get("coeff_base_year")
        if coeff_excel is None:
            coeff_excel = _coeff_base_year_n()
    show_hist = (not export_coeff_k_columns) and parse_power_demand_export_hist()
    stream = build_demand_summary_excel_stream(
        summary_rows=context["summary_rows"],
        years=context["years"],
        sheet_title=context["page_title"],
        year_features=context.get("year_features"),
        year_is_plan=context.get("year_is_plan"),
        export_coeff_k_columns=export_coeff_k_columns,
        coeff_base_year=int(coeff_excel) if coeff_excel is not None else None,
        rounding_digits=int(context.get("rounding_digits") or 1),
        rounding_digits_k=context.get("rounding_digits_k"),
        show_hist_col=show_hist,
        coeff_include_long=bool(context.get("coeff_include_long")),
    )
    fn = f"{filename_prefix}_{context['start_year']}_{context['end_year']}.xlsx"
    return send_file(
        stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=fn,
    )


@power_demand_bp.route("/summary/oes/export.xlsx", methods=["GET", "POST"])
@login_required
def demand_summary_oes_export():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=True
    )
    oes_ordered = _parse_oes_territory_ordered()
    context = build_oes_summary_context(
        _parse_rounding_digits(),
        start_year=sy,
        end_year=ey,
        data_start_year=eff_sy,
        data_end_year=eff_ey,
        filter_year_list=_filter_year_list_for_summary(),
        oes_territory_ordered=oes_ordered,
    )
    context = _apply_summary_export_view_filters(context, OES_EXPORT_PARAMETER_KEYS)
    return _demand_summary_excel_response(context, "power_demand_svodka_oes")


@power_demand_bp.route("/summary/federal_districts/export.xlsx", methods=["GET", "POST"])
@login_required
def demand_summary_federal_districts_export():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=True
    )
    fo_sets = _parse_fo_filter_sets()
    context = build_federal_district_summary_context(
        _parse_rounding_digits(),
        start_year=sy,
        end_year=ey,
        data_start_year=eff_sy,
        data_end_year=eff_ey,
        filter_year_list=_filter_year_list_for_summary(),
        fo_filter_sets=fo_sets,
        fo_aggregate_by_res=True,
        fo_max_extended_parameters=True,
    )
    context = _apply_summary_export_view_filters(context, FO_EXPORT_PARAMETER_KEYS)
    return _demand_summary_excel_response(context, "power_demand_svodka_fo")


@power_demand_bp.route("/summary/energy_zones/export.xlsx", methods=["GET", "POST"])
@login_required
def demand_summary_energy_zones_export():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=True
    )
    ez_ordered = _parse_ez_territory_ordered()
    context = build_energy_zones_summary_context(
        _parse_rounding_digits(),
        start_year=sy,
        end_year=ey,
        data_start_year=eff_sy,
        data_end_year=eff_ey,
        filter_year_list=_filter_year_list_for_summary(),
        ez_territory_ordered=ez_ordered,
        ez_max_extended_parameters=True,
    )
    context = _apply_summary_export_view_filters(context, EZ_EXPORT_PARAMETER_KEYS)
    return _demand_summary_excel_response(context, "power_demand_svodka_ez")


# --- «Коэффициенты и совмещенные максимумы» (независимые URL и выгрузки, те же данные) ---


@power_demand_bp.route("/summary/coeff/oes/export.xlsx", methods=["GET", "POST"])
@login_required
def demand_summary_oes_export_coeff():
    _n, start_year, end_year = _parse_coeff_summary_year_range()
    oes_ordered = _parse_oes_territory_ordered()
    rd = _parse_rounding_digits()
    context = build_oes_summary_context_coeff(
        rd,
        start_year=start_year,
        end_year=end_year,
        filter_year_list=_filter_year_list_for_summary(),
        oes_territory_ordered=oes_ordered,
    )
    context["rounding_digits_k"] = _parse_rounding_digits_k(
        fallback=DEFAULT_SUMMARY_COEFF_K_ROUNDING_DIGITS
    )
    context = _apply_summary_export_view_filters(context, OES_EXPORT_PARAMETER_KEYS)
    _apply_coeff_year_k_columns(context)
    return _demand_summary_excel_response(
        context, "power_demand_svodka_oes_coeff", export_coeff_k_columns=True
    )


@power_demand_bp.route("/summary/coeff/federal_districts/export.xlsx", methods=["GET", "POST"])
@login_required
def demand_summary_federal_districts_export_coeff():
    _n, start_year, end_year = _parse_coeff_summary_year_range()
    fo_sets = _parse_fo_filter_sets()
    rd = _parse_rounding_digits()
    context = build_federal_district_summary_context_coeff(
        rd,
        start_year=start_year,
        end_year=end_year,
        filter_year_list=_filter_year_list_for_summary(),
        fo_filter_sets=fo_sets,
    )
    context["rounding_digits_k"] = _parse_rounding_digits_k(
        fallback=DEFAULT_SUMMARY_COEFF_K_ROUNDING_DIGITS
    )
    context = _apply_summary_export_view_filters(
        context, FO_COEFF_EXPORT_PARAMETER_KEYS
    )
    _apply_coeff_year_k_columns(context)
    return _demand_summary_excel_response(
        context, "power_demand_svodka_fo_coeff", export_coeff_k_columns=True
    )


@power_demand_bp.route("/summary/coeff/energy_zones/export.xlsx", methods=["GET", "POST"])
@login_required
def demand_summary_energy_zones_export_coeff():
    _n, start_year, end_year = _parse_coeff_summary_year_range()
    ez_ordered = _parse_ez_territory_ordered()
    rd = _parse_rounding_digits()
    context = build_energy_zones_summary_context_coeff(
        rd,
        start_year=start_year,
        end_year=end_year,
        filter_year_list=_filter_year_list_for_summary(),
        ez_territory_ordered=ez_ordered,
    )
    context["rounding_digits_k"] = _parse_rounding_digits_k(
        fallback=DEFAULT_SUMMARY_COEFF_K_ROUNDING_DIGITS
    )
    context = _apply_summary_export_view_filters(context, EZ_EXPORT_PARAMETER_KEYS)
    _apply_coeff_year_k_columns(context)
    return _demand_summary_excel_response(
        context, "power_demand_svodka_ez_coeff", export_coeff_k_columns=True
    )


@power_demand_bp.route("/summary/cell", methods=["POST"])
@login_required
def demand_summary_save_cell():
    if not can_edit_power_demand(current_user):
        return jsonify(ok=False, error="Недостаточно прав"), 403
    data = request.get_json(silent=True) or {}
    try:
        demand_model_name = str(data.get("demand_model_name") or "").strip()
        parameter_key = str(data.get("parameter_key") or "").strip()
        raw_value = data.get("value")
        rd = data.get("rounding_digits", 1)
        rounding_digits = int(rd) if rd is not None and str(rd).strip() != "" else 1
        rd_k_raw = data.get("rounding_digits_k")
        rounding_digits_k = (
            int(rd_k_raw)
            if rd_k_raw is not None and str(rd_k_raw).strip() != ""
            else DEFAULT_SUMMARY_COEFF_K_ROUNDING_DIGITS
        )
    except (TypeError, ValueError):
        return jsonify(ok=False, error="Неверный запрос"), 400
    if rounding_digits not in (-1, 0, 1, 2, 3):
        rounding_digits = 1
    if rounding_digits_k not in (-1, 0, 1, 2, 3):
        rounding_digits_k = DEFAULT_SUMMARY_COEFF_K_ROUNDING_DIGITS

    rid_raw = data.get("row_id")
    row_id = None
    if rid_raw not in (None, "", 0, "0"):
        try:
            row_id = int(rid_raw)
        except (TypeError, ValueError):
            return jsonify(ok=False, error="Неверный идентификатор строки"), 400

    slice_key = data.get("slice_key")
    pfk_raw = data.get("parent_fk_column")
    parent_fk_column = (
        str(pfk_raw).strip() if pfk_raw not in (None, "") else None
    )
    pid_raw = data.get("parent_id")
    if pid_raw in (None, ""):
        parent_id = None
    else:
        try:
            parent_id = int(pid_raw)
        except (TypeError, ValueError):
            return jsonify(ok=False, error="Неверный parent_id"), 400

    if row_id is None and (slice_key is None or str(slice_key).strip() == ""):
        return jsonify(ok=False, error="Укажите срез (год или исторический максимум)."), 400

    rd_save = (
        rounding_digits_k
        if str(parameter_key or "").startswith("coeff_k_")
        else rounding_digits
    )
    pvc_raw = data.get("perimeter_variant_code") or data.get("south_perimeter_variant")
    perimeter_variant_code = (
        str(pvc_raw).strip() if pvc_raw not in (None, "") else None
    )

    summary_log_scope: str | None = None
    sls_raw = data.get("summary_log_scope")
    if sls_raw not in (None, ""):
        s = str(sls_raw).strip().lower()
        if s in ("oes", "fo", "ez"):
            summary_log_scope = s

    try:
        display = dps.save_demand_summary_cell(
            demand_model_name,
            parameter_key,
            raw_value,
            rounding_digits=rd_save,
            row_id=row_id,
            slice_key=slice_key,
            parent_fk_column=parent_fk_column,
            parent_id=parent_id,
            perimeter_variant_code=perimeter_variant_code,
            summary_log_scope=summary_log_scope,
        )
    except ValueError as e:
        return jsonify(ok=False, error=str(e)), 400
    clear_pd_summary_page_cache()
    return jsonify(ok=True, display_value=display)


@power_demand_bp.route("/summary/perimeter_variant", methods=["POST"])
@login_required
def demand_summary_save_perimeter_variant():
    if not can_edit_power_demand(current_user):
        return jsonify(ok=False, error="Недостаточно прав"), 403
    data = request.get_json(silent=True) or {}
    demand_model_name = str(data.get("demand_model_name") or "").strip()
    if not demand_model_name:
        return jsonify(ok=False, error="Не указана модель параметров."), 400

    pfk_raw = data.get("parent_fk_column")
    parent_fk_column = str(pfk_raw).strip() if pfk_raw not in (None, "") else None
    pid_raw = data.get("parent_id")
    parent_id = None
    if pid_raw not in (None, ""):
        try:
            parent_id = int(pid_raw)
        except (TypeError, ValueError):
            return jsonify(ok=False, error="Неверный идентификатор объекта."), 400

    from_variant = dps._UNSET
    to_variant = dps._UNSET
    if "from_variant_code" in data:
        from_variant = dps._parse_reassign_variant_code_payload(
            data.get("from_variant_code")
        )
    if "to_variant_code" in data:
        to_variant = dps._parse_reassign_variant_code_payload(data.get("to_variant_code"))
    elif "to_variant_code" not in data and "perimeter_variant_code" in data:
        to_variant = dps._parse_reassign_variant_code_payload(
            data.get("perimeter_variant_code")
        )

    summary_log_scope: str | None = None
    sls_raw = data.get("summary_log_scope")
    if sls_raw not in (None, ""):
        s = str(sls_raw).strip().lower()
        if s in ("oes", "fo", "ez"):
            summary_log_scope = s

    try:
        updated = dps.reassign_summary_entity_perimeter_variant(
            demand_model_name,
            parent_fk_column=parent_fk_column,
            parent_id=parent_id,
            from_variant_code=from_variant,
            to_variant_code=to_variant,
            summary_log_scope=summary_log_scope,
        )
    except ValueError as e:
        return jsonify(ok=False, error=str(e)), 400
    clear_pd_summary_page_cache()
    return jsonify(ok=True, updated=updated)


@power_demand_bp.route("/summary/block_variant", methods=["POST"])
@login_required
def demand_summary_save_block_variant():
    """Назначает вариант периметра блоку строк сводки нагрузок."""
    if not can_edit_power_demand(current_user):
        return jsonify(ok=False, error="Недостаточно прав"), 403
    data = request.get_json(silent=True) or {}
    demand_model_name = str(data.get("demand_model_name") or "").strip()
    if not demand_model_name:
        return jsonify(ok=False, error="Не указана модель параметров."), 400

    block_kind = str(data.get("block_kind") or "").strip()
    if not block_kind:
        return jsonify(ok=False, error="Не указан тип блока сводки."), 400

    pfk_raw = data.get("parent_fk_column")
    parent_fk_column = str(pfk_raw).strip() if pfk_raw not in (None, "") else None
    pid_raw = data.get("parent_id")
    parent_id = None
    if pid_raw not in (None, ""):
        try:
            parent_id = int(pid_raw)
        except (TypeError, ValueError):
            return jsonify(ok=False, error="Неверный идентификатор объекта."), 400

    block_scope_raw = data.get("block_scope")
    block_scope = (
        str(block_scope_raw).strip() if block_scope_raw not in (None, "") else None
    )

    summary_log_scope: str | None = None
    sls_raw = data.get("summary_log_scope")
    if sls_raw not in (None, ""):
        s = str(sls_raw).strip().lower()
        if s in ("oes", "fo", "ez"):
            summary_log_scope = s

    try:
        dps.set_summary_block_variant_code(
            demand_model_name,
            parent_fk_column=parent_fk_column,
            parent_id=parent_id,
            block_kind=block_kind,
            perimeter_variant_code=data.get("perimeter_variant_code", dps._UNSET),
            block_scope=block_scope,
            from_variant_code=data.get("from_variant_code", dps._UNSET),
            summary_log_scope=summary_log_scope,
        )
    except ValueError as e:
        return jsonify(ok=False, error=str(e)), 400
    clear_pd_summary_page_cache()
    return jsonify(ok=True)


@power_demand_bp.route("/summary/logs/<scope>", methods=["GET"])
@login_required
def demand_summary_scope_logs(scope: str):
    """AJAX: журнал изменений сводки нагрузок (ОЭС / ФО / энергозоны) для текущей версии БД."""
    if scope not in ("oes", "fo", "ez"):
        return jsonify(ok=False, error="Неверная область журнала."), 400
    offset = request.args.get("offset", 0, type=int) or 0
    limit = request.args.get("limit", PD_SUMMARY_LOGS_INITIAL_LIMIT, type=int)
    vid = get_current_version()
    if limit == 0:
        total = count_pd_summary_logs(scope, vid)
        return jsonify(
            ok=True,
            logs=[],
            offset=0,
            limit=0,
            count=0,
            total=total,
            has_more=False,
        )
    if limit is None:
        limit = PD_SUMMARY_LOGS_INITIAL_LIMIT
    limit = max(1, min(int(limit), 500))
    rows = load_pd_summary_logs_raw(scope, vid, limit=limit, offset=offset)
    formatted = format_logs_for_display(rows)
    total = count_pd_summary_logs(scope, vid)
    n = len(formatted)
    return jsonify(
        ok=True,
        logs=formatted,
        offset=offset,
        limit=limit,
        count=n,
        total=total,
        has_more=(offset + n) < total,
    )


@power_demand_bp.route("/summary/oes/")
@login_required
def demand_summary_oes():
    context = _build_oes_max_summary_context(for_shell=True)
    _attach_pd_summary_client_render(
        context,
        scope="oes",
        data_path="/power_demand/summary/oes/data.json",
    )
    return render_template("power_demand/power_demand_summary.html", **context)


@power_demand_bp.route("/summary/oes/data.json")
@login_required
def demand_summary_oes_data():
    return _build_summary_data_json_response(
        scope="oes",
        context_builder=_build_oes_max_summary_context,
    )


@power_demand_bp.route("/summary/energy_zones/")
@login_required
def demand_summary_energy_zones():
    context = _build_ez_max_summary_context(for_shell=True)
    _attach_pd_summary_client_render(
        context,
        scope="ez",
        data_path="/power_demand/summary/energy_zones/data.json",
    )
    return render_template("power_demand/power_demand_summary.html", **context)


@power_demand_bp.route("/summary/energy_zones/data.json")
@login_required
def demand_summary_energy_zones_data():
    return _build_summary_data_json_response(
        scope="ez",
        context_builder=_build_ez_max_summary_context,
    )


@power_demand_bp.route("/summary/federal_districts/")
@login_required
def demand_summary_federal_districts():
    context = _build_fo_max_summary_context(for_shell=True)
    _attach_pd_summary_client_render(
        context,
        scope="fo",
        data_path="/power_demand/summary/federal_districts/data.json",
    )
    return render_template("power_demand/power_demand_summary.html", **context)


@power_demand_bp.route("/summary/federal_districts/data.json")
@login_required
def demand_summary_federal_districts_data():
    return _build_summary_data_json_response(
        scope="fo",
        context_builder=_build_fo_max_summary_context,
    )


@power_demand_bp.route("/summary/coeff/oes/")
@login_required
def demand_summary_oes_coeff():
    context = _build_oes_coeff_summary_context(for_shell=True)
    _attach_pd_summary_client_render(
        context,
        scope="oes",
        data_path="/power_demand/summary/coeff/oes/data.json",
    )
    return render_template("power_demand/power_demand_summary.html", **context)


@power_demand_bp.route("/summary/coeff/oes/data.json")
@login_required
def demand_summary_oes_coeff_data():
    return _build_summary_data_json_response(
        scope="oes",
        context_builder=_build_oes_coeff_summary_context,
        cache_scope="coeff_oes",
    )


@power_demand_bp.route("/summary/coeff/federal_districts/")
@login_required
def demand_summary_federal_districts_coeff():
    context = _build_fo_coeff_summary_context(for_shell=True)
    _attach_pd_summary_client_render(
        context,
        scope="fo",
        data_path="/power_demand/summary/coeff/federal_districts/data.json",
    )
    return render_template("power_demand/power_demand_summary.html", **context)


@power_demand_bp.route("/summary/coeff/federal_districts/data.json")
@login_required
def demand_summary_federal_districts_coeff_data():
    return _build_summary_data_json_response(
        scope="fo",
        context_builder=_build_fo_coeff_summary_context,
        cache_scope="coeff_fo",
    )


@power_demand_bp.route("/summary/coeff/energy_zones/")
@login_required
def demand_summary_energy_zones_coeff():
    context = _build_ez_coeff_summary_context(for_shell=True)
    _attach_pd_summary_client_render(
        context,
        scope="ez",
        data_path="/power_demand/summary/coeff/energy_zones/data.json",
    )
    return render_template("power_demand/power_demand_summary.html", **context)


@power_demand_bp.route("/summary/coeff/energy_zones/data.json")
@login_required
def demand_summary_energy_zones_coeff_data():
    return _build_summary_data_json_response(
        scope="ez",
        context_builder=_build_ez_coeff_summary_context,
        cache_scope="coeff_ez",
    )

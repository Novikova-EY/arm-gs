from __future__ import annotations

from flask import current_app, jsonify, render_template, request, send_file
from flask_login import current_user, login_required
from app.common.services.get_services.years.years_get_services import (
    get_filter_end_year,
    get_filter_start_year,
    get_ges_tep_current_price_year_number,
    get_year_numbers_sorted_for_current_db_version,
)
from app.common.services.database_version_services import get_current_version
from app.energy_consumption.routes.energy_consumption_bp import energy_consumption_bp
from app.energy_consumption.services.energy_consumption_summary_export_services import (
    build_demand_summary_excel_stream,
)
from app.energy_consumption.services.energy_consumption_summary_import_services import (
    import_energy_consumption_summary_from_xlsx_bytes,
)
from app.energy_consumption.services import energy_consumption_parameter_services as dps
from app.energy_consumption.services.energy_consumption_summary_logging import (
    count_ec_summary_logs,
    load_ec_summary_logs_raw,
    load_formatted_ec_summary_logs,
)
from app.logs.services.log_display_utils import format_logs_for_display
from app.energy_consumption.services.energy_consumption_gaes_charge_summary_services import (
    build_energy_consumption_gaes_charge_only_context,
    remove_oes_and_subject_rows_from_gaes_charge_context,
)
from app.energy_consumption.services.energy_consumption_summary_services import (
    EZ_EXPORT_PARAMETER_KEYS,
    FO_EXPORT_PARAMETER_KEYS,
    GAES_CHARGE_PARAMETER_KEY,
    OES_EXPORT_PARAMETER_KEYS,
    build_energy_zones_summary_context,
    build_federal_district_summary_context,
    build_oes_summary_context,
    finalize_summary_rows_for_excel_export,
    filter_summary_rows_for_summary_table_page,
    filter_oes_summary_hidden_tites_union_energy_system_rows,
    filter_summary_table_gaes_charge_aggregate_rows,
    keep_centralized_zone_rows_in_territory_compact,
    get_demand_summary_filter_refdata,
    get_energy_consumption_ez_filter_cascade_data,
    get_energy_consumption_fo_filter_cascade_data,
    get_energy_consumption_oes_filter_cascade_data,
    parse_energy_consumption_export_ui_options,
    apply_energy_consumption_summary_table_variant_toggle_rows,
    apply_federal_district_formula_to_summary_rows,
    apply_gaes_without_charge_formula_to_summary_rows,
    inject_federal_district_without_gaes_summary_rows,
    inject_fo_summary_verification_rows,
    inject_union_energy_system_without_gaes_summary_rows,
    inject_oes_territory_detail_without_gaes_summary_rows,
    apply_fo_rd_gaes_territory_entity_labels,
    apply_union_energy_system_gaes_entity_labels,
    apply_oes_territory_detail_gaes_entity_labels,
    apply_summary_table_formula_calculations,
    apply_oes_tites_root_formula_to_summary_rows,
    apply_summary_table_russia_federation_row_rules,
    inject_first_sa_without_nt_with_gaes_with_kaliningrad_ues_verification_after_ees_russia_rows,
    inject_oes_summary_verification_rows,
    inject_oes_tites_aggregate_verification_row,
    inject_south_ues_new_territories_summary_rows,
    inject_south_fd_new_territories_summary_rows,
    slice_energy_consumption_summary_context_for_export_years,
    tag_energy_consumption_summary_rows_for_territory_compact,
    tag_energy_consumption_summary_rows_perimeter_variant_labels,
    mask_summary_rows_perimeter_variant_year_display,
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


def _filter_year_list_for_summary() -> list[int]:
    nums = get_year_numbers_sorted_for_current_db_version()
    if nums:
        return nums
    return list(range(get_filter_start_year(), get_filter_end_year() + 1))


def _summary_period_base_year_n() -> int:
    """N для колонок «отчётный N−9…N», «среднесрочный N+1…N+6» (как на странице коэффициентов спроса)."""
    n = get_ges_tep_current_price_year_number()
    if n is not None:
        return int(n)
    return int(get_filter_end_year())


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


def _parse_oes_export_visible_keys() -> frozenset[str] | None:
    return _parse_summary_export_visible_keys(OES_EXPORT_PARAMETER_KEYS)


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


def _demand_summary_excel_response(context: dict, filename_prefix: str):
    stream = build_demand_summary_excel_stream(
        summary_rows=context["summary_rows"],
        years=context["years"],
        sheet_title=context["page_title"],
        year_features=context.get("year_features") or {},
    )
    fn = f"{filename_prefix}_{context['start_year']}_{context['end_year']}.xlsx"
    return send_file(
        stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=fn,
    )


def _apply_ec_summary_export_filters(
    context: dict,
    allowed_parameter_keys: frozenset[str],
    *,
    summary_table_page: bool = False,
) -> dict:
    """Усечение лет, видимых параметров и строк по кнопкам UI (как на экране)."""
    sub_years = _parse_export_years_list(list(context.get("years") or []))
    if sub_years is not None:
        context = slice_energy_consumption_summary_context_for_export_years(context, sub_years)
    visible = _parse_summary_export_visible_keys(allowed_parameter_keys)
    ui_opts = parse_energy_consumption_export_ui_options(
        summary_table_page=summary_table_page
    )
    context = dict(context)
    context["summary_rows"] = finalize_summary_rows_for_excel_export(
        list(context.get("summary_rows") or []),
        visible_parameter_keys=visible,
        ui_opts=ui_opts,
    )
    return context


def _attach_ec_summary_logs(context: dict) -> None:
    scope = context.get("active_summary")
    if scope not in ("oes", "fo", "ez"):
        return
    vid = get_current_version()
    context["ec_summary_logs_formatted"] = load_formatted_ec_summary_logs(
        str(scope), vid, limit=50
    )


def _convert_context_to_summary_table_page(
    context: dict,
    *,
    keep_gaes_charge_territory_rows: bool = False,
    hide_gaes_charge_aggregate_rows: bool = True,
) -> dict:
    summary_rows = list(context.get("summary_rows") or [])
    source_summary_rows = list(summary_rows)
    tag_energy_consumption_summary_rows_for_territory_compact(summary_rows)
    context["summary_rows"] = filter_summary_rows_for_summary_table_page(
        summary_rows,
        keep_gaes_charge_territory_rows=keep_gaes_charge_territory_rows,
    )
    apply_energy_consumption_summary_table_variant_toggle_rows(context["summary_rows"])
    if context.get("active_summary") == "fo":
        apply_federal_district_formula_to_summary_rows(
            context["summary_rows"],
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_south_fd_new_territories_summary_rows(
            context["summary_rows"],
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_federal_district_without_gaes_summary_rows(
            context["summary_rows"],
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        apply_gaes_without_charge_formula_to_summary_rows(
            context["summary_rows"],
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        fo_res_sum_source_rows = list(source_summary_rows)
        inject_fo_summary_verification_rows(
            context["summary_rows"],
            source_rows=list(context["summary_rows"]),
            fo_res_sum_source_rows=fo_res_sum_source_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
    if context.get("active_summary") == "oes":
        apply_summary_table_russia_federation_row_rules(context["summary_rows"])
        apply_summary_table_formula_calculations(
            context["summary_rows"],
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        apply_oes_tites_root_formula_to_summary_rows(
            context["summary_rows"],
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
            eu_source_rows=source_summary_rows,
        )
        inject_first_sa_without_nt_with_gaes_with_kaliningrad_ues_verification_after_ees_russia_rows(
            context["summary_rows"],
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_south_ues_new_territories_summary_rows(
            context["summary_rows"],
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        # РЭС скрыты compact-фильтром, но нужны для суммы в «Проверка для …».
        ues_res_sum_source_rows = list(source_summary_rows)
        inject_union_energy_system_without_gaes_summary_rows(
            context["summary_rows"],
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_oes_territory_detail_without_gaes_summary_rows(
            context["summary_rows"],
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        verification_source_rows = list(context["summary_rows"])
        inject_oes_summary_verification_rows(
            context["summary_rows"],
            source_rows=verification_source_rows,
            ues_res_sum_source_rows=ues_res_sum_source_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        context["summary_rows"] = filter_oes_summary_hidden_tites_union_energy_system_rows(
            context["summary_rows"]
        )
        inject_oes_tites_aggregate_verification_row(
            context["summary_rows"],
            source_rows=source_summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
    tag_energy_consumption_summary_rows_perimeter_variant_labels(context["summary_rows"])
    mask_summary_rows_perimeter_variant_year_display(
        context["summary_rows"],
        list(context.get("years") or []),
    )
    if context.get("active_summary") == "fo":
        apply_fo_rd_gaes_territory_entity_labels(context["summary_rows"])
        apply_oes_territory_detail_gaes_entity_labels(context["summary_rows"])
    if context.get("active_summary") == "oes":
        apply_union_energy_system_gaes_entity_labels(context["summary_rows"])
        apply_oes_territory_detail_gaes_entity_labels(context["summary_rows"])
    if hide_gaes_charge_aggregate_rows and context.get("active_summary") == "oes":
        context["summary_rows"] = filter_summary_table_gaes_charge_aggregate_rows(
            context["summary_rows"]
        )
    context["summary_table_standalone"] = True
    context["summary_variant_toggle_default_off"] = False
    context["summary_table_hide_toggle"] = True
    context["summary_table_force_compact_mode"] = True
    context["summary_hub_endpoint"] = "energy_consumption_bp.summary_table_start"
    context["summary_oes_endpoint"] = "energy_consumption_bp.demand_summary_oes"
    context["summary_fo_endpoint"] = "energy_consumption_bp.demand_summary_federal_districts"
    context["summary_ez_endpoint"] = "energy_consumption_bp.demand_summary_energy_zones"
    if context.get("active_summary") == "oes":
        context["page_title"] = "Сводная информация по потреблению электрической энергии"
    return context


def _apply_summary_table_variant_behaviour_to_summary_page(context: dict) -> dict:
    """Варианты периметра и переключатели НТ/ГАЭС на обычных страницах сводки."""
    summary_rows = list(context.get("summary_rows") or [])
    apply_energy_consumption_summary_table_variant_toggle_rows(summary_rows)
    if context.get("active_summary") == "oes":
        apply_summary_table_russia_federation_row_rules(summary_rows)
    if context.get("active_summary") == "fo":
        apply_federal_district_formula_to_summary_rows(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_south_fd_new_territories_summary_rows(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_federal_district_without_gaes_summary_rows(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_oes_territory_detail_without_gaes_summary_rows(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        apply_gaes_without_charge_formula_to_summary_rows(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_fo_summary_verification_rows(
            summary_rows,
            source_rows=list(summary_rows),
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
    if context.get("active_summary") == "oes":
        apply_summary_table_formula_calculations(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        apply_oes_tites_root_formula_to_summary_rows(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_first_sa_without_nt_with_gaes_with_kaliningrad_ues_verification_after_ees_russia_rows(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_south_ues_new_territories_summary_rows(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        ues_res_sum_source_rows = list(summary_rows)
        inject_union_energy_system_without_gaes_summary_rows(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_oes_territory_detail_without_gaes_summary_rows(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        source_summary_rows = list(summary_rows)
        inject_oes_summary_verification_rows(
            summary_rows,
            source_rows=source_summary_rows,
            ues_res_sum_source_rows=ues_res_sum_source_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        summary_rows = filter_oes_summary_hidden_tites_union_energy_system_rows(
            summary_rows
        )
        inject_oes_tites_aggregate_verification_row(
            summary_rows,
            source_rows=ues_res_sum_source_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
    tag_energy_consumption_summary_rows_perimeter_variant_labels(summary_rows)
    mask_summary_rows_perimeter_variant_year_display(
        summary_rows,
        list(context.get("years") or []),
    )
    if context.get("active_summary") == "fo":
        apply_fo_rd_gaes_territory_entity_labels(summary_rows)
        apply_oes_territory_detail_gaes_entity_labels(summary_rows)
    if context.get("active_summary") == "oes":
        apply_union_energy_system_gaes_entity_labels(summary_rows)
        apply_oes_territory_detail_gaes_entity_labels(summary_rows)
    tag_energy_consumption_summary_rows_for_territory_compact(summary_rows)
    if context.get("active_summary") in ("oes", "fo"):
        keep_centralized_zone_rows_in_territory_compact(summary_rows)
    context = dict(context)
    context["summary_rows"] = summary_rows
    context["summary_variant_toggle_default_off"] = True
    return context


@energy_consumption_bp.route("/summary-table/start/")
@login_required
def summary_table_start():
    """Выбор разреза (ОЭС / ФО / ЭЗ) для сводной таблицы без строк РЭС и субъектов."""
    return render_template("energy_consumption/energy_consumption_summary_start.html")


@energy_consumption_bp.route("/summary-table/")
@login_required
def summary_table_hub():
    """Корень сводной таблицы: ОЭС без строк РЭС/субъектов; синхронные зоны — как на /summary-table/oes/."""
    return demand_summary_table_oes()


@energy_consumption_bp.route("/summary/oes/export.xlsx")
@login_required
def demand_summary_oes_export():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
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
        ees_top_from_db=True,
        russia_country_summary_ec_divisor=1,
        include_ees_russia_rows=False,
        include_synchronous_area_rows=False,
        include_oes_summary_table_sync_sa_ees_verification=False,
        expand_south_ues_perimeter_variants=True,
        summary_table_top_order=True,
    )
    context = _apply_summary_table_variant_behaviour_to_summary_page(context)
    context = _apply_ec_summary_export_filters(context, OES_EXPORT_PARAMETER_KEYS)
    return _demand_summary_excel_response(context, "energy_consumption_svodka_oes")


@energy_consumption_bp.route("/summary/federal-districts/export.xlsx")
@login_required
def demand_summary_federal_districts_export():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
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
        expand_entity_perimeter_variants=True,
    )
    context = _apply_summary_table_variant_behaviour_to_summary_page(context)
    context = _apply_ec_summary_export_filters(context, FO_EXPORT_PARAMETER_KEYS)
    return _demand_summary_excel_response(context, "energy_consumption_svodka_fo")


@energy_consumption_bp.route("/summary/energy-zones/export.xlsx")
@login_required
def demand_summary_energy_zones_export():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
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
        expand_entity_perimeter_variants=True,
    )
    context = _apply_summary_table_variant_behaviour_to_summary_page(context)
    context = _apply_ec_summary_export_filters(context, EZ_EXPORT_PARAMETER_KEYS)
    return _demand_summary_excel_response(context, "energy_consumption_svodka_ez")


@energy_consumption_bp.route("/summary-table/oes/export.xlsx")
@login_required
def demand_summary_table_oes_export():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
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
        ees_top_from_db=True,
        russia_country_summary_ec_divisor=1,
        include_oes_summary_table_sync_sa_ees_verification=True,
        expand_south_ues_perimeter_variants=True,
        summary_table_top_order=True,
    )
    context = _convert_context_to_summary_table_page(context)
    context = _apply_ec_summary_export_filters(
        context, OES_EXPORT_PARAMETER_KEYS, summary_table_page=True
    )
    return _demand_summary_excel_response(context, "energy_consumption_svodka_table_oes")


@energy_consumption_bp.route("/summary-table/federal-districts/export.xlsx")
@login_required
def demand_summary_table_federal_districts_export():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
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
        expand_entity_perimeter_variants=True,
    )
    context = _convert_context_to_summary_table_page(context)
    context = _apply_ec_summary_export_filters(
        context, FO_EXPORT_PARAMETER_KEYS, summary_table_page=True
    )
    return _demand_summary_excel_response(context, "energy_consumption_svodka_table_fo")


@energy_consumption_bp.route("/summary-table/energy-zones/export.xlsx")
@login_required
def demand_summary_table_energy_zones_export():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
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
        expand_entity_perimeter_variants=True,
    )
    context = _convert_context_to_summary_table_page(context)
    context = _apply_ec_summary_export_filters(
        context, EZ_EXPORT_PARAMETER_KEYS, summary_table_page=True
    )
    return _demand_summary_excel_response(context, "energy_consumption_svodka_table_ez")


@energy_consumption_bp.route("/summary/oes/gaes-charge/export.xlsx")
@login_required
def demand_summary_oes_gaes_charge_export():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
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
        include_synchronous_area_rows=False,
        include_russia_top_row=False,
    )
    context = build_energy_consumption_gaes_charge_only_context(context)
    context = _apply_ec_summary_export_filters(
        context,
        frozenset({GAES_CHARGE_PARAMETER_KEY}),
        summary_table_page=False,
    )
    return _demand_summary_excel_response(
        context, "energy_consumption_svodka_oes_gaes_charge"
    )


@energy_consumption_bp.route("/summary/fo-ez/import.xlsx", methods=["POST"])
@login_required
def demand_summary_fo_ez_import_xlsx():
    """Импорт показателей потребления по ОЭС/РЭС/субъект РФ/ФО — для страниц сводки по ОЭС, ФО и энергозонам.

    По умолчанию данные записываются только в текущую выбранную версию БД; запись во все версии —
    переменная окружения EC_SUMMARY_IMPORT_ALL_DB_VERSIONS (см. модуль импорта сводки).
    """
    if not getattr(current_user, "has_admin", False):
        return jsonify(ok=False, error="Недостаточно прав"), 403
    upload = request.files.get("file")
    if upload is None or upload.filename is None or str(upload.filename).strip() == "":
        return jsonify(ok=False, error="Файл не выбран."), 400
    raw_name = str(upload.filename).strip().lower()
    if not (raw_name.endswith(".xlsx") or raw_name.endswith(".xlsm")):
        return jsonify(ok=False, error="Ожидается файл в формате .xlsx или .xlsm."), 400
    raw = upload.read()
    if not raw:
        return jsonify(ok=False, error="Пустой файл."), 400
    try:
        stats = import_energy_consumption_summary_from_xlsx_bytes(raw)
    except ValueError as e:
        return jsonify(ok=False, error=str(e)), 400
    except Exception:
        current_app.logger.exception("Импорт сводки потребления из Excel (не ValueError)")
        return (
            jsonify(
                ok=False,
                error=(
                    "Не удалось выполнить импорт (ошибка при обработке файла или записи в БД). "
                    "Подробности — в журнале сервера приложения."
                ),
            ),
            400,
        )
    msg = (
        "Импорт выполнен по версиям БД: "
        f"{stats['database_versions_processed']}. Лист «млн. кВт.ч»: записано ячеек — "
        f"{stats['cells_written_mln_kvt_ch']}; лист «СиПР»: записано ячеек — "
        f"{stats['cells_written_sipr']}."
    )
    if stats.get("mln_sheet_absent"):
        msg += " Лист «млн. кВт.ч» в файле отсутствует — данные для него не импортировались."
    if stats.get("sipr_sheet_absent"):
        msg += " Лист «СиПР» в файле отсутствует — данные для него не импортировались."
    if stats.get("mln_sheet_skipped_no_data_grid"):
        msg += (
            " Лист «млн. кВт.ч» без таблицы (заглушка) — поля «млн. кВт·ч» из этого листа не обновлялись."
        )
    extras = []
    um = stats.get("unmatched_labels_mln") or []
    us = stats.get("unmatched_labels_sipr") or []
    if um:
        extras.append(
            "Не сопоставлены строки (лист «млн. кВт.ч», первые наименования): "
            + "; ".join(um[:12])
            + (" …" if len(um) > 12 else "")
        )
    if us:
        extras.append(
            "Не сопоставлены строки (лист «СиПР», первые наименования): "
            + "; ".join(us[:12])
            + (" …" if len(us) > 12 else "")
        )
    return jsonify(ok=True, message=msg, hints=extras, **stats)


@energy_consumption_bp.route("/summary/cell", methods=["POST"])
@login_required
def demand_summary_save_cell():
    if not getattr(current_user, "has_admin", False):
        return jsonify(ok=False, error="Недостаточно прав"), 403
    data = request.get_json(silent=True) or {}
    try:
        demand_model_name = str(data.get("demand_model_name") or "").strip()
        parameter_key = str(data.get("parameter_key") or "").strip()
        raw_value = data.get("value")
        rd = data.get("rounding_digits", 1)
        rounding_digits = int(rd) if rd is not None and str(rd).strip() != "" else 1
    except (TypeError, ValueError):
        return jsonify(ok=False, error="Неверный запрос"), 400
    if rounding_digits not in (-1, 0, 1, 2, 3):
        rounding_digits = 1

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

    gaes_station_id: int | None = None
    gs_raw = data.get("gaes_station_id")
    if gs_raw not in (None, "", 0, "0"):
        try:
            gaes_station_id = int(gs_raw)
        except (TypeError, ValueError):
            return jsonify(ok=False, error="Неверный идентификатор станции ГАЭС."), 400

    if row_id is None and (slice_key is None or str(slice_key).strip() == ""):
        return jsonify(ok=False, error="Укажите год среза или существующую строку (row_id)."), 400

    summary_log_scope: str | None = None
    sls_raw = data.get("summary_log_scope")
    if sls_raw not in (None, ""):
        s = str(sls_raw).strip().lower()
        if s in ("oes", "fo", "ez"):
            summary_log_scope = s

    if "perimeter_variant_code" not in data:
        pvc = dps._UNSET
    else:
        pvc = dps._resolve_perimeter_variant_for_save(data.get("perimeter_variant_code"))

    try:
        sipr_summary_mode = bool(data.get("sipr_summary_mode"))
        display = dps.save_demand_summary_cell(
            demand_model_name,
            parameter_key,
            raw_value,
            rounding_digits=rounding_digits,
            sipr_summary_mode=sipr_summary_mode,
            row_id=row_id,
            slice_key=slice_key,
            parent_fk_column=parent_fk_column,
            parent_id=parent_id,
            summary_log_scope=summary_log_scope,
            gaes_station_id=gaes_station_id,
            perimeter_variant_code=pvc,
        )
    except ValueError as e:
        return jsonify(ok=False, error=str(e)), 400
    return jsonify(ok=True, display_value=display)


@energy_consumption_bp.route("/summary/perimeter-variant", methods=["POST"])
@login_required
def demand_summary_save_perimeter_variant():
    if not getattr(current_user, "has_admin", False):
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

    from_variant = data.get("from_variant_code", dps._UNSET)
    to_variant = data.get("to_variant_code", dps._UNSET)
    if "from_variant_code" in data:
        from_variant = dps._resolve_perimeter_variant_for_save(data.get("from_variant_code"))
    if "to_variant_code" in data:
        to_variant = dps._resolve_perimeter_variant_for_save(data.get("to_variant_code"))

    try:
        updated = dps.reassign_summary_entity_perimeter_variant(
            demand_model_name,
            parent_fk_column=parent_fk_column,
            parent_id=parent_id,
            from_variant_code=from_variant,
            to_variant_code=to_variant,
        )
    except ValueError as e:
        return jsonify(ok=False, error=str(e)), 400
    return jsonify(ok=True, updated=updated)


@energy_consumption_bp.route("/summary/block-variant", methods=["POST"])
@login_required
def demand_summary_save_block_variant():
    """Назначает вариант периметра блоку строк сводки (без переноса данных между вариантами)."""
    if not getattr(current_user, "has_admin", False):
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

    try:
        dps.set_summary_block_variant_code(
            demand_model_name,
            parent_fk_column=parent_fk_column,
            parent_id=parent_id,
            block_kind=block_kind,
            perimeter_variant_code=data.get("perimeter_variant_code", dps._UNSET),
            block_scope=block_scope,
        )
    except ValueError as e:
        return jsonify(ok=False, error=str(e)), 400
    return jsonify(ok=True)


@energy_consumption_bp.route("/summary/persist-formula-block", methods=["POST"])
@login_required
def demand_summary_persist_formula_block():
    if not getattr(current_user, "has_admin", False):
        return jsonify(ok=False, error="Недостаточно прав"), 403
    data = request.get_json(silent=True) or {}
    demand_model_name = str(data.get("demand_model_name") or "").strip()
    if not demand_model_name:
        return jsonify(ok=False, error="Не указана модель параметров."), 400
    formula_kind = str(data.get("formula_kind") or "").strip()
    if formula_kind != "without_gaes_charge":
        return jsonify(ok=False, error="Неподдерживаемый тип расчётной строки."), 400

    pfk_raw = data.get("parent_fk_column")
    parent_fk_column = str(pfk_raw).strip() if pfk_raw not in (None, "") else None
    pid_raw = data.get("parent_id")
    parent_id = None
    if pid_raw not in (None, ""):
        try:
            parent_id = int(pid_raw)
        except (TypeError, ValueError):
            return jsonify(ok=False, error="Неверный идентификатор объекта."), 400

    formula_context = data.get("formula_context")
    if not isinstance(formula_context, dict):
        return jsonify(ok=False, error="Не передан контекст расчётной строки."), 400

    sy = data.get("start_year")
    ey = data.get("end_year")
    try:
        sy_i = int(sy)
        ey_i = int(ey)
    except (TypeError, ValueError):
        return jsonify(ok=False, error="Не указан диапазон годов."), 400
    if sy_i > ey_i:
        sy_i, ey_i = ey_i, sy_i
    years = list(range(sy_i, ey_i + 1))

    rounding_digits = data.get("rounding_digits", 3)
    try:
        rounding_digits = int(rounding_digits)
    except (TypeError, ValueError):
        rounding_digits = 3

    try:
        updated = dps.persist_gaes_without_charge_formula_block(
            demand_model_name=demand_model_name,
            parent_fk_column=parent_fk_column,
            parent_id=parent_id,
            source_perimeter_variant_code=data.get("source_perimeter_variant_code", dps._UNSET),
            target_perimeter_variant_code=data.get("target_perimeter_variant_code", dps._UNSET),
            formula_context=formula_context,
            years=years,
            rounding_digits=rounding_digits,
            summary_log_scope=data.get("summary_log_scope"),
        )
    except ValueError as e:
        return jsonify(ok=False, error=str(e)), 400
    return jsonify(ok=True, updated=updated)


@energy_consumption_bp.route("/summary/logs/<scope>", methods=["GET"])
@login_required
def demand_summary_scope_logs(scope: str):
    """AJAX: журнал изменений (ОЭС / ФО / энергозоны) для текущей версии БД."""
    if scope not in ("oes", "fo", "ez"):
        return jsonify(ok=False, error="Неверная область журнала."), 400
    offset = request.args.get("offset", 0, type=int) or 0
    limit = request.args.get("limit", 150, type=int)
    if limit == 0:
        vid = get_current_version()
        total = count_ec_summary_logs(scope, vid)
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
        limit = 150
    limit = max(1, min(int(limit), 500))
    vid = get_current_version()
    rows = load_ec_summary_logs_raw(scope, vid, limit=limit, offset=offset)
    formatted = format_logs_for_display(rows)
    total = count_ec_summary_logs(scope, vid)
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


@energy_consumption_bp.route("/summary/oes/")
@login_required
def demand_summary_oes():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
    )
    oes_ordered = _parse_oes_territory_ordered()
    ues_l, res_l, rd_l, eu_l = oes_ordered
    context = build_oes_summary_context(
        _parse_rounding_digits(),
        start_year=sy,
        end_year=ey,
        data_start_year=eff_sy,
        data_end_year=eff_ey,
        filter_year_list=_filter_year_list_for_summary(),
        oes_territory_ordered=oes_ordered,
        ees_top_from_db=True,
        russia_country_summary_ec_divisor=1,
        include_ees_russia_rows=False,
        include_synchronous_area_rows=False,
        include_oes_summary_table_sync_sa_ees_verification=False,
        expand_south_ues_perimeter_variants=True,
        summary_table_top_order=True,
    )
    context = _apply_summary_table_variant_behaviour_to_summary_page(context)
    context["summary_variant_toggle_default_off"] = False
    context.update(get_demand_summary_filter_refdata())
    context["pd_oes_filters_cascade"] = get_energy_consumption_oes_filter_cascade_data()
    context["can_edit_summary_cells"] = getattr(current_user, "has_admin", False)
    context["has_active_summary_filters"] = bool(ues_l or res_l or rd_l or eu_l)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = _summary_period_base_year_n()
    context["summary_include_medium_years"] = include_medium
    _attach_ec_summary_logs(context)
    return render_template("energy_consumption/energy_consumption_summary.html", **context)


@energy_consumption_bp.route("/summary/energy-zones/")
@login_required
def demand_summary_energy_zones():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
    )
    ez_ordered = _parse_ez_territory_ordered()
    ez_l, res_l = ez_ordered
    context = build_energy_zones_summary_context(
        _parse_rounding_digits(),
        start_year=sy,
        end_year=ey,
        data_start_year=eff_sy,
        data_end_year=eff_ey,
        filter_year_list=_filter_year_list_for_summary(),
        ez_territory_ordered=ez_ordered,
        expand_entity_perimeter_variants=True,
    )
    context = _apply_summary_table_variant_behaviour_to_summary_page(context)
    context.update(get_demand_summary_filter_refdata())
    context["pd_ez_filters_cascade"] = get_energy_consumption_ez_filter_cascade_data()
    context["can_edit_summary_cells"] = getattr(current_user, "has_admin", False)
    context["has_active_summary_filters"] = bool(ez_l or res_l)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = _summary_period_base_year_n()
    context["summary_include_medium_years"] = include_medium
    _attach_ec_summary_logs(context)
    return render_template("energy_consumption/energy_consumption_summary.html", **context)


@energy_consumption_bp.route("/summary/federal-districts/")
@login_required
def demand_summary_federal_districts():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
    )
    fo_sets = _parse_fo_filter_sets()
    f_fd, f_res = fo_sets
    context = build_federal_district_summary_context(
        _parse_rounding_digits(),
        start_year=sy,
        end_year=ey,
        data_start_year=eff_sy,
        data_end_year=eff_ey,
        filter_year_list=_filter_year_list_for_summary(),
        fo_filter_sets=fo_sets,
        expand_entity_perimeter_variants=True,
    )
    context = _apply_summary_table_variant_behaviour_to_summary_page(context)
    context.update(get_demand_summary_filter_refdata())
    context["pd_fo_filters_cascade"] = get_energy_consumption_fo_filter_cascade_data()
    context["can_edit_summary_cells"] = getattr(current_user, "has_admin", False)
    context["has_active_summary_filters"] = bool(f_fd or f_res)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = _summary_period_base_year_n()
    context["summary_include_medium_years"] = include_medium
    _attach_ec_summary_logs(context)
    return render_template("energy_consumption/energy_consumption_summary.html", **context)


@energy_consumption_bp.route("/summary/oes/gaes-charge/")
@login_required
def demand_summary_oes_gaes_charge():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
    )
    oes_ordered = _parse_oes_territory_ordered()
    ues_l, res_l, rd_l, eu_l = oes_ordered
    context = build_oes_summary_context(
        _parse_rounding_digits(),
        start_year=sy,
        end_year=ey,
        data_start_year=eff_sy,
        data_end_year=eff_ey,
        filter_year_list=_filter_year_list_for_summary(),
        oes_territory_ordered=oes_ordered,
        include_synchronous_area_rows=False,
        include_russia_top_row=False,
    )
    context.update(get_demand_summary_filter_refdata())
    context["pd_oes_filters_cascade"] = get_energy_consumption_oes_filter_cascade_data()
    context["can_edit_summary_cells"] = getattr(current_user, "has_admin", False)
    context["has_active_summary_filters"] = bool(ues_l or res_l or rd_l or eu_l)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = _summary_period_base_year_n()
    context["summary_include_medium_years"] = include_medium
    _attach_ec_summary_logs(context)
    context = build_energy_consumption_gaes_charge_only_context(context)
    return render_template("energy_consumption/energy_consumption_gaes_charge_summary.html", **context)


@energy_consumption_bp.route("/summary/federal-districts/gaes-charge/")
@login_required
def demand_summary_federal_districts_gaes_charge():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
    )
    fo_sets = _parse_fo_filter_sets()
    f_fd, f_res = fo_sets
    context = build_federal_district_summary_context(
        _parse_rounding_digits(),
        start_year=sy,
        end_year=ey,
        data_start_year=eff_sy,
        data_end_year=eff_ey,
        filter_year_list=_filter_year_list_for_summary(),
        fo_filter_sets=fo_sets,
    )
    context.update(get_demand_summary_filter_refdata())
    context["pd_fo_filters_cascade"] = get_energy_consumption_fo_filter_cascade_data()
    context["can_edit_summary_cells"] = getattr(current_user, "has_admin", False)
    context["has_active_summary_filters"] = bool(f_fd or f_res)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = _summary_period_base_year_n()
    context["summary_include_medium_years"] = include_medium
    _attach_ec_summary_logs(context)
    context = build_energy_consumption_gaes_charge_only_context(context)
    return render_template("energy_consumption/energy_consumption_gaes_charge_summary.html", **context)


@energy_consumption_bp.route("/summary/energy-zones/gaes-charge/")
@login_required
def demand_summary_energy_zones_gaes_charge():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
    )
    ez_ordered = _parse_ez_territory_ordered()
    ez_l, res_l = ez_ordered
    context = build_energy_zones_summary_context(
        _parse_rounding_digits(),
        start_year=sy,
        end_year=ey,
        data_start_year=eff_sy,
        data_end_year=eff_ey,
        filter_year_list=_filter_year_list_for_summary(),
        ez_territory_ordered=ez_ordered,
    )
    context.update(get_demand_summary_filter_refdata())
    context["pd_ez_filters_cascade"] = get_energy_consumption_ez_filter_cascade_data()
    context["can_edit_summary_cells"] = getattr(current_user, "has_admin", False)
    context["has_active_summary_filters"] = bool(ez_l or res_l)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = _summary_period_base_year_n()
    context["summary_include_medium_years"] = include_medium
    _attach_ec_summary_logs(context)
    context = build_energy_consumption_gaes_charge_only_context(context)
    return render_template("energy_consumption/energy_consumption_gaes_charge_summary.html", **context)


@energy_consumption_bp.route("/summary-table/oes/")
@login_required
def demand_summary_table_oes():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
    )
    oes_ordered = _parse_oes_territory_ordered()
    ues_l, res_l, rd_l, eu_l = oes_ordered
    context = build_oes_summary_context(
        _parse_rounding_digits(),
        start_year=sy,
        end_year=ey,
        data_start_year=eff_sy,
        data_end_year=eff_ey,
        filter_year_list=_filter_year_list_for_summary(),
        oes_territory_ordered=oes_ordered,
        ees_top_from_db=True,
        russia_country_summary_ec_divisor=1,
        include_oes_summary_table_sync_sa_ees_verification=True,
        expand_south_ues_perimeter_variants=True,
        summary_table_top_order=True,
    )
    context = _convert_context_to_summary_table_page(context)
    context.update(get_demand_summary_filter_refdata())
    context["pd_oes_filters_cascade"] = get_energy_consumption_oes_filter_cascade_data()
    context["can_edit_summary_cells"] = getattr(current_user, "has_admin", False)
    context["has_active_summary_filters"] = bool(ues_l or eu_l)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = _summary_period_base_year_n()
    context["summary_include_medium_years"] = include_medium
    _attach_ec_summary_logs(context)
    return render_template("energy_consumption/energy_consumption_summary.html", **context)


@energy_consumption_bp.route("/summary-table/oes/gaes-charge/")
@login_required
def demand_summary_table_oes_gaes_charge():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
    )
    oes_ordered = _parse_oes_territory_ordered()
    ues_l, res_l, rd_l, eu_l = oes_ordered
    context = build_oes_summary_context(
        _parse_rounding_digits(),
        start_year=sy,
        end_year=ey,
        data_start_year=eff_sy,
        data_end_year=eff_ey,
        filter_year_list=_filter_year_list_for_summary(),
        oes_territory_ordered=oes_ordered,
        include_synchronous_area_rows=False,
        include_russia_top_row=False,
    )
    context = _convert_context_to_summary_table_page(
        context,
        keep_gaes_charge_territory_rows=True,
        hide_gaes_charge_aggregate_rows=False,
    )
    context.update(get_demand_summary_filter_refdata())
    context["pd_oes_filters_cascade"] = get_energy_consumption_oes_filter_cascade_data()
    context["can_edit_summary_cells"] = getattr(current_user, "has_admin", False)
    context["has_active_summary_filters"] = bool(ues_l or res_l or rd_l or eu_l)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = _summary_period_base_year_n()
    context["summary_include_medium_years"] = include_medium
    _attach_ec_summary_logs(context)
    context = build_energy_consumption_gaes_charge_only_context(context)
    context = remove_oes_and_subject_rows_from_gaes_charge_context(context)
    return render_template("energy_consumption/energy_consumption_gaes_charge_summary.html", **context)


@energy_consumption_bp.route("/summary-table/federal-districts/")
@login_required
def demand_summary_table_federal_districts():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
    )
    fo_sets = _parse_fo_filter_sets()
    f_fd, _f_res = fo_sets
    context = build_federal_district_summary_context(
        _parse_rounding_digits(),
        start_year=sy,
        end_year=ey,
        data_start_year=eff_sy,
        data_end_year=eff_ey,
        filter_year_list=_filter_year_list_for_summary(),
        fo_filter_sets=fo_sets,
        expand_entity_perimeter_variants=True,
    )
    context = _convert_context_to_summary_table_page(context)
    context.update(get_demand_summary_filter_refdata())
    context["pd_fo_filters_cascade"] = get_energy_consumption_fo_filter_cascade_data()
    context["can_edit_summary_cells"] = getattr(current_user, "has_admin", False)
    context["has_active_summary_filters"] = bool(f_fd)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = _summary_period_base_year_n()
    context["summary_include_medium_years"] = include_medium
    _attach_ec_summary_logs(context)
    return render_template("energy_consumption/energy_consumption_summary.html", **context)


@energy_consumption_bp.route("/summary-table/federal-districts/gaes-charge/")
@login_required
def demand_summary_table_federal_districts_gaes_charge():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
    )
    fo_sets = _parse_fo_filter_sets()
    f_fd, _f_res = fo_sets
    context = build_federal_district_summary_context(
        _parse_rounding_digits(),
        start_year=sy,
        end_year=ey,
        data_start_year=eff_sy,
        data_end_year=eff_ey,
        filter_year_list=_filter_year_list_for_summary(),
        fo_filter_sets=fo_sets,
        expand_entity_perimeter_variants=True,
    )
    context = _convert_context_to_summary_table_page(
        context,
        keep_gaes_charge_territory_rows=True,
        hide_gaes_charge_aggregate_rows=False,
    )
    context.update(get_demand_summary_filter_refdata())
    context["pd_fo_filters_cascade"] = get_energy_consumption_fo_filter_cascade_data()
    context["can_edit_summary_cells"] = getattr(current_user, "has_admin", False)
    context["has_active_summary_filters"] = bool(f_fd)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = _summary_period_base_year_n()
    context["summary_include_medium_years"] = include_medium
    _attach_ec_summary_logs(context)
    context = build_energy_consumption_gaes_charge_only_context(context)
    return render_template("energy_consumption/energy_consumption_gaes_charge_summary.html", **context)


@energy_consumption_bp.route("/summary-table/energy-zones/gaes-charge/")
@login_required
def demand_summary_table_energy_zones_gaes_charge():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
    )
    ez_ordered = _parse_ez_territory_ordered()
    ez_l, _res_l = ez_ordered
    context = build_energy_zones_summary_context(
        _parse_rounding_digits(),
        start_year=sy,
        end_year=ey,
        data_start_year=eff_sy,
        data_end_year=eff_ey,
        filter_year_list=_filter_year_list_for_summary(),
        ez_territory_ordered=ez_ordered,
        expand_entity_perimeter_variants=True,
    )
    context = _convert_context_to_summary_table_page(
        context,
        keep_gaes_charge_territory_rows=True,
        hide_gaes_charge_aggregate_rows=False,
    )
    context.update(get_demand_summary_filter_refdata())
    context["pd_ez_filters_cascade"] = get_energy_consumption_ez_filter_cascade_data()
    context["can_edit_summary_cells"] = getattr(current_user, "has_admin", False)
    context["has_active_summary_filters"] = bool(ez_l)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = _summary_period_base_year_n()
    context["summary_include_medium_years"] = include_medium
    _attach_ec_summary_logs(context)
    context = build_energy_consumption_gaes_charge_only_context(context)
    return render_template("energy_consumption/energy_consumption_gaes_charge_summary.html", **context)


@energy_consumption_bp.route("/summary-table/energy-zones/")
@login_required
def demand_summary_table_energy_zones():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
    )
    ez_ordered = _parse_ez_territory_ordered()
    ez_l, _res_l = ez_ordered
    context = build_energy_zones_summary_context(
        _parse_rounding_digits(),
        start_year=sy,
        end_year=ey,
        data_start_year=eff_sy,
        data_end_year=eff_ey,
        filter_year_list=_filter_year_list_for_summary(),
        ez_territory_ordered=ez_ordered,
        expand_entity_perimeter_variants=True,
    )
    context = _convert_context_to_summary_table_page(context)
    context.update(get_demand_summary_filter_refdata())
    context["pd_ez_filters_cascade"] = get_energy_consumption_ez_filter_cascade_data()
    context["can_edit_summary_cells"] = getattr(current_user, "has_admin", False)
    context["has_active_summary_filters"] = bool(ez_l)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = _summary_period_base_year_n()
    context["summary_include_medium_years"] = include_medium
    _attach_ec_summary_logs(context)
    return render_template("energy_consumption/energy_consumption_summary.html", **context)

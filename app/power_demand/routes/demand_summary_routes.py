from __future__ import annotations

from flask import jsonify, render_template, request, send_file
from flask_login import current_user, login_required

from app.common.services.get_services.years.years_get_services import (
    get_filter_end_year,
    get_filter_start_year,
    get_ges_tep_current_price_year_number,
    get_year_list_full,
)
from app.power_demand.routes.power_demand_bp import power_demand_bp
from app.power_demand.services.demand_summary_export_services import (
    build_demand_summary_excel_stream,
)
from app.power_demand.services import demand_parameter_services as dps
from app.power_demand.services.demand_summary_services import (
    EZ_EXPORT_PARAMETER_KEYS,
    FO_COEFF_EXPORT_PARAMETER_KEYS,
    FO_EXPORT_PARAMETER_KEYS,
    OES_EXPORT_PARAMETER_KEYS,
    apply_power_demand_oes_summary_nt_export_ui,
    apply_power_demand_summary_territory_compact_export_ui,
    build_energy_zones_summary_context,
    build_energy_zones_summary_context_coeff,
    build_federal_district_summary_context,
    build_federal_district_summary_context_coeff,
    build_oes_summary_context,
    build_oes_summary_context_coeff,
    enrich_summary_rows_coeff_k_columns,
    filter_summary_rows_for_parameter_keys,
    get_demand_summary_filter_refdata,
    get_power_demand_ez_filter_cascade_data,
    get_power_demand_fo_filter_cascade_data,
    get_power_demand_oes_filter_cascade_data,
    parse_power_demand_export_nt_detail,
    parse_power_demand_export_territory_compact,
    slice_coeff_summary_for_lazy_long_segment,
    slice_power_demand_summary_context_for_export_years,
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
    """Округление строк k на сводках «Коэффициенты…»; без параметра — как rounding_digits."""
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
        frozenset(_parse_ordered_unique_int_ids("ds_rd")),
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


def _apply_coeff_year_k_columns(context: dict) -> None:
    """Для «Коэффициенты…»: k = значение / макс. мощность года (блок строк)."""
    coeff_n = context.get("coeff_base_year")
    if coeff_n is None:
        coeff_n = _coeff_base_year_n()
    rd_k = context.get("rounding_digits_k")
    if rd_k is None:
        rd_k = context["rounding_digits"]
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
    stream = build_demand_summary_excel_stream(
        summary_rows=context["summary_rows"],
        years=context["years"],
        sheet_title=context["page_title"],
        year_is_plan=context.get("year_is_plan"),
        export_coeff_k_columns=export_coeff_k_columns,
        coeff_base_year=int(coeff_excel) if coeff_excel is not None else None,
    )
    fn = f"{filename_prefix}_{context['start_year']}_{context['end_year']}.xlsx"
    return send_file(
        stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=fn,
    )


@power_demand_bp.route("/summary/oes/export.xlsx")
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
    sub_years = _parse_export_years_list(list(context.get("years") or []))
    if sub_years is not None:
        context = slice_power_demand_summary_context_for_export_years(context, sub_years)
    visible = _parse_oes_export_visible_keys()
    if visible is not None:
        context["summary_rows"] = filter_summary_rows_for_parameter_keys(
            context["summary_rows"], visible
        )
    context["summary_rows"] = apply_power_demand_oes_summary_nt_export_ui(
        context["summary_rows"],
        nt_detail_on=parse_power_demand_export_nt_detail(),
    )
    context["summary_rows"] = apply_power_demand_summary_territory_compact_export_ui(
        context["summary_rows"],
        territory_compact_on=parse_power_demand_export_territory_compact(),
    )
    return _demand_summary_excel_response(context, "power_demand_svodka_oes")


@power_demand_bp.route("/summary/federal-districts/export.xlsx")
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
    )
    sub_years = _parse_export_years_list(list(context.get("years") or []))
    if sub_years is not None:
        context = slice_power_demand_summary_context_for_export_years(context, sub_years)
    visible = _parse_summary_export_visible_keys(FO_EXPORT_PARAMETER_KEYS)
    if visible is not None:
        context["summary_rows"] = filter_summary_rows_for_parameter_keys(
            context["summary_rows"], visible
        )
    context["summary_rows"] = apply_power_demand_oes_summary_nt_export_ui(
        context["summary_rows"],
        nt_detail_on=parse_power_demand_export_nt_detail(),
    )
    context["summary_rows"] = apply_power_demand_summary_territory_compact_export_ui(
        context["summary_rows"],
        territory_compact_on=parse_power_demand_export_territory_compact(),
    )
    return _demand_summary_excel_response(context, "power_demand_svodka_fo")


@power_demand_bp.route("/summary/energy-zones/export.xlsx")
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
    )
    sub_years = _parse_export_years_list(list(context.get("years") or []))
    if sub_years is not None:
        context = slice_power_demand_summary_context_for_export_years(context, sub_years)
    visible = _parse_summary_export_visible_keys(EZ_EXPORT_PARAMETER_KEYS)
    if visible is not None:
        context["summary_rows"] = filter_summary_rows_for_parameter_keys(
            context["summary_rows"], visible
        )
    context["summary_rows"] = apply_power_demand_oes_summary_nt_export_ui(
        context["summary_rows"],
        nt_detail_on=parse_power_demand_export_nt_detail(),
    )
    context["summary_rows"] = apply_power_demand_summary_territory_compact_export_ui(
        context["summary_rows"],
        territory_compact_on=parse_power_demand_export_territory_compact(),
    )
    return _demand_summary_excel_response(context, "power_demand_svodka_ez")


# --- «Коэффициенты и совмещенные максимумы» (независимые URL и выгрузки, те же данные) ---


@power_demand_bp.route("/summary/coeff/oes/export.xlsx")
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
    context["rounding_digits_k"] = _parse_rounding_digits_k(fallback=rd)
    visible = _parse_oes_export_visible_keys()
    if visible is not None:
        context["summary_rows"] = filter_summary_rows_for_parameter_keys(
            context["summary_rows"], visible
        )
    context["summary_rows"] = apply_power_demand_oes_summary_nt_export_ui(
        context["summary_rows"],
        nt_detail_on=parse_power_demand_export_nt_detail(),
    )
    context["summary_rows"] = apply_power_demand_summary_territory_compact_export_ui(
        context["summary_rows"],
        territory_compact_on=parse_power_demand_export_territory_compact(),
    )
    _apply_coeff_year_k_columns(context)
    return _demand_summary_excel_response(
        context, "power_demand_svodka_oes_coeff", export_coeff_k_columns=True
    )


@power_demand_bp.route("/summary/coeff/federal-districts/export.xlsx")
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
    context["rounding_digits_k"] = _parse_rounding_digits_k(fallback=rd)
    visible = _parse_summary_export_visible_keys(FO_COEFF_EXPORT_PARAMETER_KEYS)
    if visible is not None:
        context["summary_rows"] = filter_summary_rows_for_parameter_keys(
            context["summary_rows"], visible
        )
    context["summary_rows"] = apply_power_demand_oes_summary_nt_export_ui(
        context["summary_rows"],
        nt_detail_on=parse_power_demand_export_nt_detail(),
    )
    context["summary_rows"] = apply_power_demand_summary_territory_compact_export_ui(
        context["summary_rows"],
        territory_compact_on=parse_power_demand_export_territory_compact(),
    )
    _apply_coeff_year_k_columns(context)
    return _demand_summary_excel_response(
        context, "power_demand_svodka_fo_coeff", export_coeff_k_columns=True
    )


@power_demand_bp.route("/summary/coeff/energy-zones/export.xlsx")
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
    context["rounding_digits_k"] = _parse_rounding_digits_k(fallback=rd)
    visible = _parse_summary_export_visible_keys(EZ_EXPORT_PARAMETER_KEYS)
    if visible is not None:
        context["summary_rows"] = filter_summary_rows_for_parameter_keys(
            context["summary_rows"], visible
        )
    context["summary_rows"] = apply_power_demand_oes_summary_nt_export_ui(
        context["summary_rows"],
        nt_detail_on=parse_power_demand_export_nt_detail(),
    )
    context["summary_rows"] = apply_power_demand_summary_territory_compact_export_ui(
        context["summary_rows"],
        territory_compact_on=parse_power_demand_export_territory_compact(),
    )
    _apply_coeff_year_k_columns(context)
    return _demand_summary_excel_response(
        context, "power_demand_svodka_ez_coeff", export_coeff_k_columns=True
    )


@power_demand_bp.route("/summary/cell", methods=["POST"])
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
        rd_k_raw = data.get("rounding_digits_k")
        rounding_digits_k = (
            int(rd_k_raw)
            if rd_k_raw is not None and str(rd_k_raw).strip() != ""
            else rounding_digits
        )
    except (TypeError, ValueError):
        return jsonify(ok=False, error="Неверный запрос"), 400
    if rounding_digits not in (-1, 0, 1, 2, 3):
        rounding_digits = 1
    if rounding_digits_k not in (-1, 0, 1, 2, 3):
        rounding_digits_k = rounding_digits

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
        )
    except ValueError as e:
        return jsonify(ok=False, error=str(e)), 400
    return jsonify(ok=True, display_value=display)


@power_demand_bp.route("/summary/oes/")
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
    )
    context.update(get_demand_summary_filter_refdata())
    context["pd_oes_filters_cascade"] = get_power_demand_oes_filter_cascade_data()
    context["can_edit_summary_cells"] = getattr(current_user, "has_admin", False)
    context["has_active_summary_filters"] = bool(ues_l or res_l or rd_l or eu_l)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = _summary_period_base_year_n()
    context["summary_include_medium_years"] = include_medium
    return render_template("perimeter_variants/power_demand_summary.html", **context)


@power_demand_bp.route("/summary/energy-zones/")
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
    )
    context.update(get_demand_summary_filter_refdata())
    context["pd_ez_filters_cascade"] = get_power_demand_ez_filter_cascade_data()
    context["can_edit_summary_cells"] = getattr(current_user, "has_admin", False)
    context["has_active_summary_filters"] = bool(ez_l or res_l)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = _summary_period_base_year_n()
    context["summary_include_medium_years"] = include_medium
    return render_template("perimeter_variants/power_demand_summary.html", **context)


@power_demand_bp.route("/summary/federal-districts/")
@login_required
def demand_summary_federal_districts():
    sy, ey = _parse_summary_year_range()
    n = _summary_period_base_year_n()
    include_medium = _parse_summary_include_medium_years()
    eff_sy, eff_ey = _expand_summary_years_for_period_segments(
        sy, ey, n, include_medium_years=include_medium
    )
    fo_sets = _parse_fo_filter_sets()
    f_fd, f_rd = fo_sets
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
    context["pd_fo_filters_cascade"] = get_power_demand_fo_filter_cascade_data()
    context["can_edit_summary_cells"] = getattr(current_user, "has_admin", False)
    context["has_active_summary_filters"] = bool(f_fd or f_rd)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = _summary_period_base_year_n()
    context["summary_include_medium_years"] = include_medium
    return render_template("perimeter_variants/power_demand_summary.html", **context)


@power_demand_bp.route("/summary/coeff/oes/")
@login_required
def demand_summary_oes_coeff():
    coeff_n, start_year, end_year = _parse_coeff_summary_year_range()
    coeff_include_long = _parse_coeff_include_long()
    oes_ordered = _parse_oes_territory_ordered()
    ues_l, res_l, rd_l, eu_l = oes_ordered
    rd = _parse_rounding_digits()
    context = build_oes_summary_context_coeff(
        rd,
        start_year=start_year,
        end_year=end_year,
        filter_year_list=_filter_year_list_for_summary(),
        oes_territory_ordered=oes_ordered,
    )
    context["rounding_digits_k"] = _parse_rounding_digits_k(fallback=rd)
    context.update(get_demand_summary_filter_refdata())
    context["pd_oes_filters_cascade"] = get_power_demand_oes_filter_cascade_data()
    context["can_edit_summary_cells"] = getattr(current_user, "has_admin", False)
    context["has_active_summary_filters"] = bool(ues_l or res_l or rd_l or eu_l)
    context["summary_route_variant"] = "coeff"
    context["coeff_base_year"] = coeff_n
    context["coeff_period_header_groups"] = _coeff_period_header_groups_html(
        include_long=coeff_include_long
    )
    _apply_coeff_year_k_columns(context)
    slice_coeff_summary_for_lazy_long_segment(
        context, coeff_n, include_long=coeff_include_long
    )
    return render_template("perimeter_variants/power_demand_summary.html", **context)


@power_demand_bp.route("/summary/coeff/federal-districts/")
@login_required
def demand_summary_federal_districts_coeff():
    coeff_n, start_year, end_year = _parse_coeff_summary_year_range()
    coeff_include_long = _parse_coeff_include_long()
    fo_sets = _parse_fo_filter_sets()
    f_fd, f_rd = fo_sets
    rd = _parse_rounding_digits()
    context = build_federal_district_summary_context_coeff(
        rd,
        start_year=start_year,
        end_year=end_year,
        filter_year_list=_filter_year_list_for_summary(),
        fo_filter_sets=fo_sets,
    )
    context["rounding_digits_k"] = _parse_rounding_digits_k(fallback=rd)
    context.update(get_demand_summary_filter_refdata())
    context["pd_fo_filters_cascade"] = get_power_demand_fo_filter_cascade_data()
    context["can_edit_summary_cells"] = getattr(current_user, "has_admin", False)
    context["has_active_summary_filters"] = bool(f_fd or f_rd)
    context["summary_route_variant"] = "coeff"
    context["coeff_base_year"] = coeff_n
    context["coeff_period_header_groups"] = _coeff_period_header_groups_html(
        include_long=coeff_include_long
    )
    _apply_coeff_year_k_columns(context)
    slice_coeff_summary_for_lazy_long_segment(
        context, coeff_n, include_long=coeff_include_long
    )
    return render_template("perimeter_variants/power_demand_summary.html", **context)


@power_demand_bp.route("/summary/coeff/energy-zones/")
@login_required
def demand_summary_energy_zones_coeff():
    coeff_n, start_year, end_year = _parse_coeff_summary_year_range()
    coeff_include_long = _parse_coeff_include_long()
    ez_ordered = _parse_ez_territory_ordered()
    ez_l, res_l = ez_ordered
    rd = _parse_rounding_digits()
    context = build_energy_zones_summary_context_coeff(
        rd,
        start_year=start_year,
        end_year=end_year,
        filter_year_list=_filter_year_list_for_summary(),
        ez_territory_ordered=ez_ordered,
    )
    context["rounding_digits_k"] = _parse_rounding_digits_k(fallback=rd)
    context.update(get_demand_summary_filter_refdata())
    context["pd_ez_filters_cascade"] = get_power_demand_ez_filter_cascade_data()
    context["can_edit_summary_cells"] = getattr(current_user, "has_admin", False)
    context["has_active_summary_filters"] = bool(ez_l or res_l)
    context["summary_route_variant"] = "coeff"
    context["coeff_base_year"] = coeff_n
    context["coeff_period_header_groups"] = _coeff_period_header_groups_html(
        include_long=coeff_include_long
    )
    _apply_coeff_year_k_columns(context)
    slice_coeff_summary_for_lazy_long_segment(
        context, coeff_n, include_long=coeff_include_long
    )
    return render_template("perimeter_variants/power_demand_summary.html", **context)

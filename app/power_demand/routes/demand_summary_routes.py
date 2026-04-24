from __future__ import annotations

from flask import jsonify, render_template, request, send_file
from flask_login import current_user, login_required

from app.common.services.get_services.years.years_get_services import (
    get_filter_end_year,
    get_filter_start_year,
    get_year_list_full,
)
from app.power_demand.routes.power_demand_bp import power_demand_bp
from app.power_demand.services.demand_summary_export_services import (
    build_demand_summary_excel_stream,
)
from app.power_demand.services import demand_parameter_services as dps
from app.power_demand.services.demand_summary_services import (
    EZ_EXPORT_PARAMETER_KEYS,
    FO_EXPORT_PARAMETER_KEYS,
    OES_EXPORT_PARAMETER_KEYS,
    build_energy_zones_summary_context,
    build_federal_district_summary_context,
    build_oes_summary_context,
    filter_summary_rows_for_parameter_keys,
    get_demand_summary_filter_refdata,
    get_power_demand_ez_filter_cascade_data,
    get_power_demand_fo_filter_cascade_data,
    get_power_demand_oes_filter_cascade_data,
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
    nums = sorted({y.number for y in get_year_list_full()})
    if nums:
        return nums
    return list(range(get_filter_start_year(), get_filter_end_year() + 1))


def _parse_summary_year_range() -> tuple[int, int]:
    default_sy = get_filter_start_year()
    default_ey = get_filter_end_year()
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
    bounds = _filter_year_list_for_summary()
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


def _demand_summary_excel_response(context: dict, filename_prefix: str):
    stream = build_demand_summary_excel_stream(
        summary_rows=context["summary_rows"],
        years=context["years"],
        sheet_title=context["page_title"],
        year_is_plan=context.get("year_is_plan"),
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
    start_year, end_year = _parse_summary_year_range()
    oes_ordered = _parse_oes_territory_ordered()
    context = build_oes_summary_context(
        _parse_rounding_digits(),
        start_year=start_year,
        end_year=end_year,
        filter_year_list=_filter_year_list_for_summary(),
        oes_territory_ordered=oes_ordered,
    )
    visible = _parse_oes_export_visible_keys()
    if visible is not None:
        context["summary_rows"] = filter_summary_rows_for_parameter_keys(
            context["summary_rows"], visible
        )
    return _demand_summary_excel_response(context, "power_demand_svodka_oes")


@power_demand_bp.route("/summary/federal-districts/export.xlsx")
@login_required
def demand_summary_federal_districts_export():
    start_year, end_year = _parse_summary_year_range()
    fo_sets = _parse_fo_filter_sets()
    context = build_federal_district_summary_context(
        _parse_rounding_digits(),
        start_year=start_year,
        end_year=end_year,
        filter_year_list=_filter_year_list_for_summary(),
        fo_filter_sets=fo_sets,
    )
    visible = _parse_summary_export_visible_keys(FO_EXPORT_PARAMETER_KEYS)
    if visible is not None:
        context["summary_rows"] = filter_summary_rows_for_parameter_keys(
            context["summary_rows"], visible
        )
    return _demand_summary_excel_response(context, "power_demand_svodka_fo")


@power_demand_bp.route("/summary/energy-zones/export.xlsx")
@login_required
def demand_summary_energy_zones_export():
    start_year, end_year = _parse_summary_year_range()
    ez_ordered = _parse_ez_territory_ordered()
    context = build_energy_zones_summary_context(
        _parse_rounding_digits(),
        start_year=start_year,
        end_year=end_year,
        filter_year_list=_filter_year_list_for_summary(),
        ez_territory_ordered=ez_ordered,
    )
    visible = _parse_summary_export_visible_keys(EZ_EXPORT_PARAMETER_KEYS)
    if visible is not None:
        context["summary_rows"] = filter_summary_rows_for_parameter_keys(
            context["summary_rows"], visible
        )
    return _demand_summary_excel_response(context, "power_demand_svodka_ez")


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

    if row_id is None and (slice_key is None or str(slice_key).strip() == ""):
        return jsonify(ok=False, error="Укажите срез (год или исторический максимум)."), 400

    try:
        display = dps.save_demand_summary_cell(
            demand_model_name,
            parameter_key,
            raw_value,
            rounding_digits=rounding_digits,
            row_id=row_id,
            slice_key=slice_key,
            parent_fk_column=parent_fk_column,
            parent_id=parent_id,
        )
    except ValueError as e:
        return jsonify(ok=False, error=str(e)), 400
    return jsonify(ok=True, display_value=display)


@power_demand_bp.route("/summary/oes/")
@login_required
def demand_summary_oes():
    start_year, end_year = _parse_summary_year_range()
    oes_ordered = _parse_oes_territory_ordered()
    ues_l, res_l, rd_l, eu_l = oes_ordered
    context = build_oes_summary_context(
        _parse_rounding_digits(),
        start_year=start_year,
        end_year=end_year,
        filter_year_list=_filter_year_list_for_summary(),
        oes_territory_ordered=oes_ordered,
    )
    context.update(get_demand_summary_filter_refdata())
    context["pd_oes_filters_cascade"] = get_power_demand_oes_filter_cascade_data()
    context["can_edit_summary_cells"] = getattr(current_user, "has_admin", False)
    context["has_active_summary_filters"] = bool(ues_l or res_l or rd_l or eu_l)
    return render_template("power_demand/demand_summary.html", **context)


@power_demand_bp.route("/summary/energy-zones/")
@login_required
def demand_summary_energy_zones():
    start_year, end_year = _parse_summary_year_range()
    ez_ordered = _parse_ez_territory_ordered()
    ez_l, res_l = ez_ordered
    context = build_energy_zones_summary_context(
        _parse_rounding_digits(),
        start_year=start_year,
        end_year=end_year,
        filter_year_list=_filter_year_list_for_summary(),
        ez_territory_ordered=ez_ordered,
    )
    context.update(get_demand_summary_filter_refdata())
    context["pd_ez_filters_cascade"] = get_power_demand_ez_filter_cascade_data()
    context["can_edit_summary_cells"] = getattr(current_user, "has_admin", False)
    context["has_active_summary_filters"] = bool(ez_l or res_l)
    return render_template("power_demand/demand_summary.html", **context)


@power_demand_bp.route("/summary/federal-districts/")
@login_required
def demand_summary_federal_districts():
    start_year, end_year = _parse_summary_year_range()
    fo_sets = _parse_fo_filter_sets()
    f_fd, f_rd = fo_sets
    context = build_federal_district_summary_context(
        _parse_rounding_digits(),
        start_year=start_year,
        end_year=end_year,
        filter_year_list=_filter_year_list_for_summary(),
        fo_filter_sets=fo_sets,
    )
    context.update(get_demand_summary_filter_refdata())
    context["pd_fo_filters_cascade"] = get_power_demand_fo_filter_cascade_data()
    context["can_edit_summary_cells"] = getattr(current_user, "has_admin", False)
    context["has_active_summary_filters"] = bool(f_fd or f_rd)
    return render_template("power_demand/demand_summary.html", **context)

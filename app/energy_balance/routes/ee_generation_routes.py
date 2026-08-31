# -*- coding: utf-8 -*-
from datetime import datetime

from flask import current_app, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from flask_login import login_required

from app.energy_balance.routes.energy_balance_bp import energy_balance_bp
from app.energy_balance.services.station_ee_generation_page_services import (
    CONTROL_TOOLTIP,
    EE_PERIOD_MODE_MONTHS,
    EE_PERIOD_MODE_YEARS,
    TOTAL_TOOLTIP_ENERGY_UNIT,
    TOTAL_TOOLTIP_REGIONAL_DISTRICT,
    TOTAL_TOOLTIP_RUSSIA,
    TOTAL_TOOLTIP_UES,
    VERIFICATION_TOOLTIP,
    format_generation_cell,
    format_generation_input_value,
    get_station_ee_generation_page_data,
    is_verification_nonzero,
    resolve_single_year_filter,
    update_res_control_generation_value,
)
from app.generation.forms.station_forms import StationFilterForm
from app.generation.services.station_services.filters_services import (
    extract_filters_from_args,
    extract_filters_from_form,
    has_any_filters,
)
from app.energy_balance.services.energy_balance_year_filter_services import (
    get_ee_default_end_year,
    get_ee_default_start_year,
    resolve_ee_year_filters_for_request,
)
from app.generation.services.station_services.station_services import (
    get_station_list_template_context,
)
from app.energy_balance.services.ee_generation_export_services import export_ee_generation_to_excel
from app.energy_balance.services.ee_generation_import_services import (
    import_ee_generation_from_excel,
)


def _parse_ee_period_mode() -> str:
    mode = request.args.get("ee_period_mode", EE_PERIOD_MODE_YEARS)
    if mode not in (EE_PERIOD_MODE_YEARS, EE_PERIOD_MODE_MONTHS):
        return EE_PERIOD_MODE_YEARS
    return mode


@energy_balance_bp.route("/ee_generation/", methods=["GET", "POST"])
@login_required
def ee_generation():
    form = StationFilterForm()
    ee_period_mode = _parse_ee_period_mode()

    if request.method == "POST":
        return redirect(
            url_for(
                "energy_balance_bp.ee_generation",
                **extract_filters_from_form(request.form),
            )
        )

    filter_year_list = None
    selected_year = None
    start_year = end_year = None

    if ee_period_mode == EE_PERIOD_MODE_YEARS:
        if request.method == "GET":
            start_year, end_year, year_redirect = resolve_ee_year_filters_for_request()
            if year_redirect:
                return year_redirect
    else:
        selected_year, filter_year_list = resolve_single_year_filter()

    filters = extract_filters_from_args(request.args)
    page = request.args.get("page", 1, type=int)
    filters.pop("page", None)
    filters.pop("start_year", None)
    filters.pop("end_year", None)
    filters.pop("year", None)
    filters.pop("ee_period_mode", None)
    filters.pop("show_totals", None)

    per_page_param = request.args.get("per_page", "50")
    show_all = str(per_page_param).lower() == "all"
    per_page = "all" if show_all else int(per_page_param) if str(per_page_param).isdigit() else 50
    show_totals = request.args.get("show_totals", "0") == "1"

    try:
        rounding_digits = int(request.args.get("rounding_digits"))
    except (ValueError, TypeError):
        rounding_digits = 1
    if rounding_digits is None or rounding_digits < 0:
        rounding_digits = 1

    page_data = get_station_ee_generation_page_data(
        filters=filters,
        page=page,
        per_page=per_page,
        period_mode=ee_period_mode,
        selected_year=selected_year,
        start_year=start_year,
        end_year=end_year,
        rounding_digits=rounding_digits,
        show_totals=show_totals,
    )

    if (not page_data["stations"]) and page_data["total_count"] > 0 and page > 1:
        target_page = max(1, page - 1)
        args_multi = request.args.to_dict(flat=False)
        args_multi["page"] = [str(target_page)]
        redirect_args = {}
        for key, values in args_multi.items():
            if not values:
                continue
            redirect_args[key] = values[0] if len(values) == 1 else values
        return redirect(url_for("energy_balance_bp.ee_generation", **redirect_args))

    data = {
        "stations": [],
        "stations_grouped": {},
        "station_ids": page_data["station_ids"],
        "total_count": page_data["total_count"],
        "total_pages": page_data["total_pages"],
        "page": page_data["page"],
        "per_page": page_data["per_page"],
        "show_headers": page_data.get("show_headers"),
        "station_totals": {},
        "show_p_ogr": False,
        "show_p_rasp": False,
        "should_show_totals": page_data.get("should_show_totals", {}),
    }

    year_filters = (
        {"start_year": selected_year, "end_year": selected_year}
        if ee_period_mode == EE_PERIOD_MODE_MONTHS
        else {"start_year": start_year, "end_year": end_year}
    )

    context = get_station_list_template_context(
        form,
        data,
        rounding_digits,
        {**filters, **year_filters},
        show_all=show_all,
        hierarchy_data=None,
    )
    if ee_period_mode == EE_PERIOD_MODE_MONTHS and filter_year_list is not None:
        context["filter_year_list"] = filter_year_list
    context["selected_year"] = selected_year
    context["start_year"] = page_data["start_year"]
    context["end_year"] = page_data["end_year"]
    context["ee_period_mode"] = ee_period_mode
    context["hierarchy"] = page_data["hierarchy"]
    context["period_columns"] = page_data["period_columns"]
    context["format_generation_cell"] = lambda val: format_generation_cell(val, rounding_digits)
    context["format_verification_cell"] = lambda val: format_generation_cell(
        val, rounding_digits, show_zero=True
    )
    context["generation_aggregates"] = page_data.get("generation_aggregates", {})
    context["res_show_rd_level_map"] = page_data.get("res_show_rd_level_map", {})
    context["res_control_by_res"] = page_data.get("res_control_by_res", {})
    context["res_stations_left_by_res"] = page_data.get("res_stations_left_by_res", {})
    context["res_verification_by_res"] = page_data.get("res_verification_by_res", {})
    context["is_verification_nonzero"] = is_verification_nonzero
    context["format_generation_input_value"] = format_generation_input_value
    context["total_tooltip_energy_unit"] = TOTAL_TOOLTIP_ENERGY_UNIT
    context["total_tooltip_regional_district"] = TOTAL_TOOLTIP_REGIONAL_DISTRICT
    context["total_tooltip_ues"] = TOTAL_TOOLTIP_UES
    context["total_tooltip_russia"] = TOTAL_TOOLTIP_RUSSIA
    context["control_tooltip"] = CONTROL_TOOLTIP
    context["verification_tooltip"] = VERIFICATION_TOOLTIP
    context["show_ee_generation_import"] = True
    context["ee_control_save_url"] = url_for("energy_balance_bp.ee_generation_control_value")

    has_active_filters = has_any_filters(request.args)

    return render_template(
        "energy_balance/ee_generation/ee_generation.html",
        has_active_filters=has_active_filters,
        **context,
    )


@energy_balance_bp.route("/ee_generation/control_value/", methods=["PATCH"])
@login_required
def ee_generation_control_value():
    """Сохранение контрольного значения выработки ЭЭ по РЭС."""
    data = request.get_json(silent=True) or {}
    if "res_id" not in data or "period" not in data:
        return jsonify(ok=False, error="Неверный запрос"), 400

    ee_period_mode = data.get("ee_period_mode") or _parse_ee_period_mode()
    if ee_period_mode not in (EE_PERIOD_MODE_YEARS, EE_PERIOD_MODE_MONTHS):
        ee_period_mode = EE_PERIOD_MODE_YEARS

    selected_year = data.get("selected_year")
    if selected_year is None and ee_period_mode == EE_PERIOD_MODE_MONTHS:
        selected_year = request.args.get("year", type=int)
    try:
        selected_year_int = int(selected_year) if selected_year is not None else None
    except (TypeError, ValueError):
        selected_year_int = None

    try:
        rounding_digits = int(
            data.get("rounding_digits", request.args.get("rounding_digits", 1))
        )
    except (TypeError, ValueError):
        rounding_digits = 1

    try:
        saved = update_res_control_generation_value(
            data.get("res_id"),
            data.get("period"),
            data.get("value"),
            period_mode=ee_period_mode,
            selected_year=selected_year_int,
        )
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        current_app.logger.exception("Не удалось сохранить контрольное значение выработки")
        return jsonify(ok=False, error="Не удалось сохранить значение"), 500

    value = saved.get("value")
    display = format_generation_input_value(value, rounding_digits)
    return jsonify(
        ok=True,
        res_id=saved["res_id"],
        period=saved["period_key"],
        value=None if value is None else str(value),
        display=display,
    )


@energy_balance_bp.route("/ee_generation/export", methods=["GET"])
@login_required
def export_ee_generation():
    """Экспорт выработки ЭЭ в Excel с учётом фильтров и настроек отображения."""
    try:
        ee_period_mode = _parse_ee_period_mode()
        selected_year = None
        start_year = end_year = None

        if ee_period_mode == EE_PERIOD_MODE_MONTHS:
            selected_year, _ = resolve_single_year_filter()
        else:
            start_year = request.args.get("start_year", type=int) or get_ee_default_start_year()
            end_year = request.args.get("end_year", type=int) or get_ee_default_end_year()
            if start_year > end_year:
                start_year, end_year = end_year, start_year

        filters = extract_filters_from_args(request.args)
        for key in ("page", "start_year", "end_year", "year", "ee_period_mode", "show_totals", "export_verification"):
            filters.pop(key, None)

        try:
            rounding_digits = int(request.args.get("rounding_digits"))
        except (ValueError, TypeError):
            rounding_digits = 1
        if rounding_digits is None or rounding_digits < 0:
            rounding_digits = 1

        show_totals = request.args.get("show_totals", "0") == "1"
        export_verification = request.args.get("export_verification", "0") == "1"

        excel_file = export_ee_generation_to_excel(
            filters=filters,
            period_mode=ee_period_mode,
            selected_year=selected_year,
            start_year=start_year,
            end_year=end_year,
            rounding_digits=rounding_digits,
            show_totals=show_totals,
            export_verification=export_verification,
            per_page="all",
            page=1,
        )
        if excel_file is None:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("energy_balance_bp.ee_generation", **request.args.to_dict()))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Выработка_ЭЭ_{timestamp}.xlsx"
        return send_file(
            excel_file,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        current_app.logger.error("Ошибка экспорта выработки ЭЭ: %s", exc, exc_info=True)
        flash(f"Ошибка экспорта данных: {exc}", "danger")
        return redirect(url_for("energy_balance_bp.ee_generation", **request.args.to_dict()))


@energy_balance_bp.route("/ee_generation/import", methods=["POST"])
@login_required
def import_ee_generation():
    user = session.get("username", "Неизвестный пользователь")

    if "file" not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(request.referrer or url_for("energy_balance_bp.ee_generation"))

    file = request.files["file"]
    if not file or not file.filename:
        flash("Файл не выбран.", "danger")
        return redirect(request.referrer or url_for("energy_balance_bp.ee_generation"))

    if not file.filename.lower().endswith((".xlsx", ".xls")):
        flash("Неверный формат файла. Ожидается .xlsx или .xls.", "danger")
        return redirect(request.referrer or url_for("energy_balance_bp.ee_generation"))

    try:
        result = import_ee_generation_from_excel(file, user)
        flash(result["message"], "warning" if result.get("errors_count") else "success")
        for error in (result.get("errors") or [])[:8]:
            flash(error, "warning")
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        current_app.logger.error("Ошибка импорта выработки ЭЭ: %s", exc, exc_info=True)
        flash("Ошибка импорта выработки ЭЭ. Пожалуйста, попробуйте снова.", "danger")

    return redirect(request.referrer or url_for("energy_balance_bp.ee_generation"))

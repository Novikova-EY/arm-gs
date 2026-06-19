# -*- coding: utf-8 -*-
from datetime import datetime
from urllib.parse import parse_qs, urlparse

from flask import current_app, flash, redirect, render_template, request, send_file, session, url_for
from flask_login import login_required

from app.energy_balance.routes.energy_balance_bp import energy_balance_bp
from app.energy_balance.services.ee_transfers_export_services import export_ee_transfers_to_excel
from app.energy_balance.services.ee_transfers_import_services import import_ee_transfers_from_excel
from app.energy_balance.services.ee_transfers_page_services import (
    format_transfer_cell,
    get_ee_transfers_page_data,
)
from app.energy_balance.services.station_ee_generation_page_services import (
    EE_PERIOD_MODE_MONTHS,
    EE_PERIOD_MODE_YEARS,
    resolve_single_year_filter,
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
    get_ee_filter_year_list,
    resolve_ee_transfers_year_filters_for_request,
    resolve_ee_transfers_year_range,
)
from app.generation.services.station_services.station_services import (
    get_station_list_template_context,
)


def _parse_ee_period_mode() -> str:
    mode = request.args.get("ee_period_mode", EE_PERIOD_MODE_YEARS)
    if mode not in (EE_PERIOD_MODE_YEARS, EE_PERIOD_MODE_MONTHS):
        return EE_PERIOD_MODE_YEARS
    return mode


def _redirect_after_ee_transfers_import(imported_year: int | None = None):
    """После импорта возвращает на страницу с диапазоном лет, включающим загруженный год."""
    redirect_args: dict[str, str | int] = {}

    referrer = request.referrer or ""
    parsed_url = urlparse(referrer)
    if parsed_url.path.rstrip("/").endswith("/ee_transfers"):
        for key, values in parse_qs(parsed_url.query).items():
            if not values:
                continue
            redirect_args[key] = values[0] if len(values) == 1 else values

    for key, value in request.args.items():
        if value is not None and value != "":
            redirect_args[key] = value

    start_year_raw = redirect_args.get("start_year")
    end_year_raw = redirect_args.get("end_year")
    try:
        start_year = int(start_year_raw) if start_year_raw is not None else get_ee_default_start_year()
    except (TypeError, ValueError):
        start_year = get_ee_default_start_year()
    try:
        end_year = int(end_year_raw) if end_year_raw is not None else get_ee_default_end_year()
    except (TypeError, ValueError):
        end_year = get_ee_default_end_year()
    if start_year > end_year:
        start_year, end_year = end_year, start_year

    if imported_year is not None:
        start_year = min(start_year, imported_year)
        end_year = max(end_year, imported_year)

    redirect_args["start_year"] = start_year
    redirect_args["end_year"] = end_year
    redirect_args["ee_period_mode"] = EE_PERIOD_MODE_YEARS
    redirect_args.pop("page", None)

    return redirect(url_for("energy_balance_bp.ee_transfers", **redirect_args))


@energy_balance_bp.route("/ee_transfers/", methods=["GET", "POST"])
@login_required
def ee_transfers():
    form = StationFilterForm()
    ee_period_mode = _parse_ee_period_mode()

    if request.method == "POST":
        return redirect(
            url_for(
                "energy_balance_bp.ee_transfers",
                **extract_filters_from_form(request.form),
            )
        )

    filter_year_list = None
    selected_year = None
    start_year = end_year = None

    if ee_period_mode == EE_PERIOD_MODE_YEARS:
        if request.method == "GET":
            start_year, end_year, year_redirect = resolve_ee_transfers_year_filters_for_request()
            if year_redirect:
                return year_redirect
        filter_year_list = get_ee_filter_year_list()
    else:
        selected_year, _ = resolve_single_year_filter()
        filter_year_list = get_ee_filter_year_list()

    filters = extract_filters_from_args(request.args)
    filters["transfer_to_res_filter"] = request.args.getlist("transfer_to_res_filter", type=int)
    filters["transfer_to_country_filter"] = request.args.getlist("transfer_to_country_filter", type=int)
    filters["transfer_to_rd_filter"] = request.args.getlist("transfer_to_rd_filter", type=int)
    filters["transfer_to_energy_unit_filter"] = request.args.getlist("transfer_to_energy_unit_filter", type=int)
    page = request.args.get("page", 1, type=int)
    filters.pop("page", None)
    filters.pop("start_year", None)
    filters.pop("end_year", None)
    filters.pop("year", None)
    filters.pop("ee_period_mode", None)
    filters.pop("show_totals", None)

    per_page_param = request.args.get("per_page", "10")
    show_all = str(per_page_param).lower() == "all"
    per_page = "all" if show_all else int(per_page_param) if str(per_page_param).isdigit() else 10
    show_totals = request.args.get("show_totals", "0") == "1"

    try:
        rounding_digits = int(request.args.get("rounding_digits"))
    except (ValueError, TypeError):
        rounding_digits = 1
    if rounding_digits is None or rounding_digits < 0:
        rounding_digits = 1

    page_data = get_ee_transfers_page_data(
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

    if page_data["total_count"] > 0 and page > page_data["total_pages"] and page > 1:
        target_page = max(1, page_data["total_pages"])
        args_multi = request.args.to_dict(flat=False)
        args_multi["page"] = [str(target_page)]
        redirect_args = {}
        for key, values in args_multi.items():
            if not values:
                continue
            redirect_args[key] = values[0] if len(values) == 1 else values
        return redirect(url_for("energy_balance_bp.ee_transfers", **redirect_args))

    data = {
        "stations": [],
        "stations_grouped": {},
        "station_ids": [],
        "total_count": page_data["total_count"],
        "total_pages": page_data["total_pages"],
        "page": page_data["page"],
        "per_page": page_data["per_page"],
        "show_headers": {},
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
    context["filter_year_list"] = filter_year_list or get_ee_filter_year_list()
    context["ee_reporting_start_year"] = get_ee_default_start_year()
    context["ee_reporting_end_year"] = get_ee_default_end_year()
    context["selected_year"] = selected_year
    context["start_year"] = page_data["start_year"]
    context["end_year"] = page_data["end_year"]
    context["ee_period_mode"] = ee_period_mode
    context["hierarchy"] = page_data["hierarchy"]
    context["period_columns"] = page_data["period_columns"]
    context["format_transfer_cell"] = lambda val: format_transfer_cell(val, rounding_digits)
    context["transfer_aggregates"] = page_data.get("transfer_aggregates", {})
    context["show_ee_transfers_import"] = True
    context["transfer_to_res_filter"] = filters.get("transfer_to_res_filter") or []
    context["transfer_to_country_filter"] = filters.get("transfer_to_country_filter") or []
    context["transfer_to_rd_filter"] = filters.get("transfer_to_rd_filter") or []
    context["transfer_to_energy_unit_filter"] = filters.get("transfer_to_energy_unit_filter") or []
    context["foreign_border_country_list"] = page_data.get("foreign_border_country_list") or []
    context["transfer_regional_district_list"] = page_data.get("transfer_regional_district_list") or []
    context["transfer_energy_unit_list"] = page_data.get("transfer_energy_unit_list") or []

    has_active_filters = has_any_filters(request.args) or bool(
        context["transfer_to_res_filter"]
        or context["transfer_to_country_filter"]
        or context["transfer_to_rd_filter"]
        or context["transfer_to_energy_unit_filter"]
    )

    return render_template(
        "energy_balance/ee_transfers/ee_transfers.html",
        has_active_filters=has_active_filters,
        **context,
    )


@energy_balance_bp.route("/ee_transfers/export", methods=["GET"])
@login_required
def export_ee_transfers():
    """Экспорт перетоков ЭЭ в Excel с учётом фильтров и настроек отображения."""
    try:
        ee_period_mode = _parse_ee_period_mode()
        selected_year = None
        start_year = end_year = None

        if ee_period_mode == EE_PERIOD_MODE_MONTHS:
            selected_year, _ = resolve_single_year_filter()
        else:
            start_year, end_year = resolve_ee_transfers_year_range()

        filters = extract_filters_from_args(request.args)
        filters["transfer_to_res_filter"] = request.args.getlist("transfer_to_res_filter", type=int)
        filters["transfer_to_country_filter"] = request.args.getlist("transfer_to_country_filter", type=int)
        filters["transfer_to_rd_filter"] = request.args.getlist("transfer_to_rd_filter", type=int)
        filters["transfer_to_energy_unit_filter"] = request.args.getlist("transfer_to_energy_unit_filter", type=int)
        for key in (
            "page",
            "start_year",
            "end_year",
            "year",
            "ee_period_mode",
            "show_totals",
        ):
            filters.pop(key, None)

        try:
            rounding_digits = int(request.args.get("rounding_digits"))
        except (ValueError, TypeError):
            rounding_digits = 1
        if rounding_digits is None or rounding_digits < 0:
            rounding_digits = 1

        show_totals = request.args.get("show_totals", "0") == "1"

        excel_file = export_ee_transfers_to_excel(
            filters=filters,
            period_mode=ee_period_mode,
            selected_year=selected_year,
            start_year=start_year,
            end_year=end_year,
            rounding_digits=rounding_digits,
            show_totals=show_totals,
            per_page="all",
            page=1,
        )
        if excel_file is None:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("energy_balance_bp.ee_transfers", **request.args.to_dict()))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Перетоки_ЭЭ_{timestamp}.xlsx"
        return send_file(
            excel_file,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        current_app.logger.error("Ошибка экспорта перетоков ЭЭ: %s", exc, exc_info=True)
        flash(f"Ошибка экспорта данных: {exc}", "danger")
        return redirect(url_for("energy_balance_bp.ee_transfers", **request.args.to_dict()))


@energy_balance_bp.route("/ee_transfers/import", methods=["POST"])
@login_required
def import_ee_transfers():
    user = session.get("username", "Неизвестный пользователь")

    if "file" not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(request.referrer or url_for("energy_balance_bp.ee_transfers"))

    file = request.files["file"]
    if not file or not file.filename:
        flash("Файл не выбран.", "danger")
        return redirect(request.referrer or url_for("energy_balance_bp.ee_transfers"))

    if not file.filename.lower().endswith((".xlsx", ".xls")):
        flash("Неверный формат файла. Ожидается .xlsx или .xls.", "danger")
        return redirect(request.referrer or url_for("energy_balance_bp.ee_transfers"))

    try:
        result = import_ee_transfers_from_excel(file, user)
        flash(result["message"], "warning" if result.get("errors_count") else "success")
        for error in (result.get("errors") or [])[:8]:
            flash(error, "warning")
        return _redirect_after_ee_transfers_import(imported_year=result.get("year_number"))
    except ValueError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        current_app.logger.error("Ошибка импорта перетоков ЭЭ: %s", exc, exc_info=True)
        flash("Ошибка импорта перетоков ЭЭ. Пожалуйста, попробуйте снова.", "danger")

    return _redirect_after_ee_transfers_import()

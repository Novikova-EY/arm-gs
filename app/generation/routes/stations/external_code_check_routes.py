# -*- coding: utf-8 -*-
"""Страница проверки external_code по версиям БД."""

from flask import redirect, render_template, request, session, url_for
from flask_login import login_required

from app.generation.forms.station_forms import StationFilterForm
from app.generation.routes.stations import station_bp
from app.generation.routes.stations.station_routes import (
    _build_redirect_args_from_multi_dict,
    _serialize_request_args_for_session,
)
from app.generation.services.station_services.external_code_check_services import (
    all_db_versions_context,
    attach_external_codes_by_version,
    get_database_versions_for_check,
)
from app.generation.services.station_services.filters_services import (
    extract_filters_from_args,
    extract_filters_from_form,
    has_any_filters,
)
from app.generation.services.station_services.generation_year_filter_services import (
    resolve_generation_year_filters_for_request,
)
from app.common.services.get_services.years.years_get_services import (
    get_filter_end_year,
    get_filter_start_year,
)
from app.generation.services.station_services.station_services import (
    get_station_list_data,
    get_station_list_template_context,
)

EXTERNAL_CODE_CHECK_FILTERS_SESSION_KEY = "external_code_check_filters"


@station_bp.route("/external_code_check", methods=["GET", "POST"])
@login_required
def external_code_check():
    """Список станций с external_code по всем версиям БД."""
    form = StationFilterForm()

    if request.method == "GET":
        _, _, year_redirect = resolve_generation_year_filters_for_request()
        if year_redirect:
            return year_redirect

    if request.method == "POST":
        return redirect(
            url_for(
                "station_bp.external_code_check",
                **extract_filters_from_form(request.form),
            )
        )

    if request.args.get("reset_filters") == "1":
        session.pop(EXTERNAL_CODE_CHECK_FILTERS_SESSION_KEY, None)
        return redirect(url_for("station_bp.external_code_check"))

    if not request.args:
        saved_args_multi = session.get(EXTERNAL_CODE_CHECK_FILTERS_SESSION_KEY) or {}
        redirect_args = _build_redirect_args_from_multi_dict(saved_args_multi)
        if redirect_args:
            return redirect(url_for("station_bp.external_code_check", **redirect_args))
    else:
        session[EXTERNAL_CODE_CHECK_FILTERS_SESSION_KEY] = _serialize_request_args_for_session(
            request.args
        )

    filters = extract_filters_from_args(request.args)
    filters["all_db_versions"] = True
    page = filters.pop("page", 1)
    start_year = filters.pop("start_year", get_filter_start_year())
    end_year = filters.pop("end_year", get_filter_end_year())

    per_page_param = request.args.get("per_page", "10")
    show_all = per_page_param.lower() == "all"
    if show_all:
        per_page = "all"
    else:
        try:
            per_page = int(per_page_param)
        except ValueError:
            per_page = 10

    with all_db_versions_context():
        data = get_station_list_data(
            filters=filters,
            per_page=per_page,
            page=page,
            rounding_digits=0,
            start_year=start_year,
            end_year=end_year,
            show_p_ogr=False,
            show_p_rasp=False,
            show_all=show_all,
            show_totals=False,
        )

    if (not data.get("stations")) and data.get("total_count", 0) > 0 and page > 1:
        target_page = data.get("total_pages") or 1
        if target_page >= page:
            target_page = max(1, page - 1)
        args_multi = request.args.to_dict(flat=False)
        args_multi["page"] = [str(target_page)]
        redirect_args = _build_redirect_args_from_multi_dict(args_multi)
        return redirect(url_for("station_bp.external_code_check", **redirect_args))

    if data["page"] > data["total_pages"]:
        return redirect(
            url_for(
                "station_bp.external_code_check",
                page=data["total_pages"],
                per_page=per_page,
            )
        )

    database_versions = get_database_versions_for_check()
    attach_external_codes_by_version(data["stations"], database_versions)

    context = get_station_list_template_context(
        form,
        data,
        0,
        {**filters, "start_year": start_year, "end_year": end_year},
        show_all=show_all,
        hierarchy_data=data.get("hierarchy_data"),
    )
    context.update(
        {
            "page_title": "Проверка external_code",
            "database_versions": database_versions,
            "table_total_colspan": 3 + len(database_versions),
            "external_code_check_mode": True,
            "station_list_endpoint": "station_bp.external_code_check",
            "pagination_endpoint": "station_bp.external_code_check",
        }
    )

    return render_template(
        "generation/stations/external_code_check.html",
        has_active_filters=has_any_filters(request.args),
        **context,
    )

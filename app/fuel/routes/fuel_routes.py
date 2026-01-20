from flask import render_template, request, redirect, url_for, session, current_app, send_file, flash
from flask_login import login_required
from datetime import datetime
from io import BytesIO

from . import fuel_bp

from app.generation.forms.station_forms import StationFilterForm
from app.generation.services.station_services.station_services import (
    get_station_list_data,
    get_station_list_template_context,
)
from app.generation.services.station_services.export_cache import (
    build_export_key,
    set_export_payload,
)
from app.generation.services.station_services.filters_services import (
    has_any_filters,
    extract_filters_from_args,
    extract_filters_from_form,
)
from app.common.services.get_services.years.years_get_services import (
    get_filter_start_year,
    get_filter_end_year,
)
from app.common.services.database_version_filter import get_current_db_version_id
from app.fuel.services.export_stations_equipment_groups_services import (
    export_stations_equipment_groups_to_excel,
)


@fuel_bp.route("/")
def fuel_start():
    return render_template("fuel/fuel_start.html")


@fuel_bp.route("/stations_equipment_groups", methods=["GET", "POST"])
@login_required
def stations_equipment_groups():
    form = StationFilterForm()

    if request.method == "POST":
        return redirect(url_for("fuel_bp.stations_equipment_groups", **extract_filters_from_form(request.form)))

    filters = extract_filters_from_args(request.args)
    page = filters.pop("page", 1)
    start_year = filters.pop("start_year", get_filter_start_year())
    end_year = filters.pop("end_year", get_filter_end_year())
    show_p_ogr = request.args.get("show_p_ogr", "0") == "1"
    show_p_rasp = request.args.get("show_p_rasp", "1") == "1"
    show_totals = request.args.get("show_totals", "0") == "1"
    per_page_param = request.args.get("per_page", "10")

    show_all = per_page_param.lower() == "all"
    if show_all:
        per_page = "all"
    else:
        try:
            per_page = int(per_page_param)
        except ValueError:
            per_page = 10

    try:
        rounding_digits = int(request.args.get("rounding_digits"))
    except (ValueError, TypeError):
        rounding_digits = 1

    if rounding_digits is None or rounding_digits < 0:
        rounding_digits = 1

    data = get_station_list_data(
        filters=filters,
        per_page=per_page,
        page=page,
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        show_p_ogr=show_p_ogr,
        show_p_rasp=show_p_rasp,
        show_all=show_all,
        show_totals=show_totals,
    )

    if (not data.get("stations")) and data.get("total_count", 0) > 0 and page > 1:
        target_page = data.get("total_pages") or 1
        if target_page >= page:
            target_page = max(1, page - 1)
        args_multi = request.args.to_dict(flat=False)
        args_multi["page"] = [str(target_page)]
        redirect_args = {}
        for key, values in args_multi.items():
            if not values:
                continue
            if len(values) == 1:
                redirect_args[key] = values[0]
            else:
                redirect_args[key] = values
        return redirect(url_for("fuel_bp.stations_equipment_groups", **redirect_args))

    try:
        export_key = build_export_key(
            {**filters},
            rounding_digits,
            start_year,
            end_year,
            show_p_ogr,
            show_p_rasp,
        )
        export_payload = {
            "data": data,
            "params": {
                "rounding_digits": rounding_digits,
                "start_year": start_year,
                "end_year": end_year,
                "show_p_ogr": show_p_ogr,
                "show_p_rasp": show_p_rasp,
            },
        }
        set_export_payload(session.get("username") or "anonymous", export_key, export_payload)
    except Exception as exc:
        current_app.logger.warning(f"[EXPORT_CACHE] Failed to store export payload: {exc}")

    if data["page"] > data["total_pages"]:
        return redirect(url_for("fuel_bp.stations_equipment_groups", page=data["total_pages"], per_page=per_page))

    context = get_station_list_template_context(
        form,
        data,
        rounding_digits,
        {**filters, "start_year": start_year, "end_year": end_year},
        show_all=show_all,
        hierarchy_data=data.get("hierarchy_data"),
    )

    has_active_filters = has_any_filters(request.args)

    return render_template(
        "fuel/stations_equipment_groups.html",
        has_active_filters=has_active_filters,
        **context,
    )


@fuel_bp.route("/stations_equipment_groups/export", methods=["GET"])
@login_required
def export_stations_equipment_groups():
    """Экспорт данных stations_equipment_groups в Excel с id станций и агрегатов."""
    try:
        filters = extract_filters_from_args(request.args)
        start_year = int(request.args.get("start_year", get_filter_start_year()))
        end_year = int(request.args.get("end_year", get_filter_end_year()))
        
        # Генерируем Excel файл через отдельный сервис
        excel_file = export_stations_equipment_groups_to_excel(filters, start_year, end_year)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Электростанции_с_группами_оборудования_{timestamp}.xlsx"
        
        excel_file.seek(0)
        return send_file(
            excel_file,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        current_app.logger.error(f"Ошибка экспорта stations_equipment_groups: {e}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        flash(f"Ошибка экспорта данных: {str(e)}", "danger")
        return redirect(url_for("fuel_bp.stations_equipment_groups", **request.args.to_dict()))

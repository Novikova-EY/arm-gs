from config import Config
from . import station_changes_bp
from app.logs.services.logging_service import log_to_db
from flask_login import login_required
from flask import send_file, render_template, request, session, flash, redirect, url_for
from app.generation.services.station_services.filters_services import (
    has_any_filters,
    extract_filters_from_args, 
    extract_filters_from_form,
)
from app.generation.services.station_changes_services.station_changes_services import (
    get_station_changes_list_data, 
    get_station_list_template_context
)
from app.generation.forms.station_changes.station_changes_forms import StationPowerChangeFilterForm

@station_changes_bp.route('/station_changes_list', methods=['GET', 'POST'])
@login_required
def station_changes_list():
    import time

    start_data = time.time()

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница изменений установленной мощности электростанций")

    form = StationPowerChangeFilterForm()

    if request.method == "POST":
        return redirect(url_for("station_changes_bp.station_changes_list", **extract_filters_from_form(request.form)))

    per_page_param = request.args.get("per_page", "10")
    show_all = per_page_param.lower() == "all"

    if show_all:
        per_page = "all"
    else:
        try:
            per_page = int(per_page_param)
        except ValueError:
            per_page = 10

    filters = extract_filters_from_args(request.args)
    page = filters.pop("page", 1)
    start_year = filters.pop("start_year", Config.START_YEAR)
    end_year = filters.pop("end_year", Config.END_YEAR)

    try:
        rounding_digits = int(request.args.get('rounding_digits'))
    except (ValueError, TypeError):
        rounding_digits = 1

    if rounding_digits is None or rounding_digits < 0:
        rounding_digits = 1

    data = get_station_changes_list_data(
        filters=filters,
        per_page=per_page,
        page=page,
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        show_all=show_all,
    )
    print(f"⏱ get_station_changes_list_data заняла: {time.time() - start_data:.2f} сек")

    if data["page"] > data["total_pages"]:
        return redirect(url_for("station_changes_bp.station_changes_list", page=data["total_pages"], per_page=per_page))

    context = get_station_list_template_context(
        form,
        data,
        rounding_digits,
        {**filters, "start_year": start_year, "end_year": end_year},
        show_all=show_all,
    )

    has_active_filters = has_any_filters(request.args)
    
    overall = time.time() - start_data
    print(f"⏱⏱ station_changes_list загрузка заняла: {overall:.2f} сек")

    return render_template("station_changes/station_changes.html", has_active_filters=has_active_filters, **context)


@station_changes_bp.route('/report_sipr_pril_2/export', methods=['GET'])
@login_required
def report_sipr_pril_2_export():
    return
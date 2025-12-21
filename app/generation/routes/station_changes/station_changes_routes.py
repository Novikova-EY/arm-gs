from config import Config
from . import station_changes_bp
from flask import current_app

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
from app.generation.services.station_changes_services.export_station_changes_services import (
    export_station_changes_to_excel,
)
from app.generation.services.station_services.export_cache import (
    build_export_key,
    set_export_payload,
    get_export_payload,
)

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

    # Управление отображением агрегированных сумм (по умолчанию скрыты)
    show_totals = request.args.get("show_totals", "0") == "1"

    data = get_station_changes_list_data(
        filters=filters,
        per_page=per_page,
        page=page,
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        show_all=show_all,
    )
    print(f"[TIME] get_station_changes_list_data заняла: {time.time() - start_data:.2f} сек")

    # Сохраняем данные в кэш для последующей быстрой выгрузки
    try:
        from app.common.services.database_version_filter import get_current_db_version_id
        current_db_version_id = get_current_db_version_id()
        
        export_key = build_export_key(
            {**filters},
            rounding_digits,
            start_year,
            end_year,
            False,  # show_p_ogr для station_changes не используется
            False,  # show_p_rasp для station_changes не используется
        )
        # Добавляем database_version_id в данные для проверки при экспорте
        if isinstance(data, dict):
            data["database_version_id"] = current_db_version_id
        
        export_payload = {
            "data": data,
            "params": {
                "rounding_digits": rounding_digits,
                "start_year": start_year,
                "end_year": end_year,
                "show_totals": show_totals,
                "database_version_id": current_db_version_id,
            },
        }
        set_export_payload(session.get('username') or 'anonymous', export_key, export_payload)
    except Exception as _e:
        current_app.logger.warning(f"[EXPORT_CACHE] station_changes: failed to store export payload: {_e}")

    if data["page"] > data["total_pages"]:
        return redirect(url_for("station_changes_bp.station_changes_list", page=data["total_pages"], per_page=per_page))

    context = get_station_list_template_context(
        form,
        data,
        rounding_digits,
        {**filters, "start_year": start_year, "end_year": end_year},
        show_all=show_all,
    )

    # Прокидываем флаг отображения итогов в шаблон
    context["show_totals"] = show_totals

    has_active_filters = has_any_filters(request.args)
    
    overall = time.time() - start_data
    print(f"[TIME] station_changes_list загрузка заняла: {overall:.2f} сек")

    return render_template("generation/station_changes/station_changes.html", has_active_filters=has_active_filters, **context)


@station_changes_bp.route('/report_sipr_pril_2/export', methods=['GET'])
@login_required
def report_sipr_pril_2_export():
    return


@station_changes_bp.route('/station_changes_list/export', methods=['GET'])
@login_required
def station_changes_list_export():
    user = session.get('username', 'Неизвестный пользователь')

    # Параметры из запроса
    filters = extract_filters_from_args(request.args)
    try:
        rounding_digits = int(request.args.get('rounding_digits'))
    except (ValueError, TypeError):
        rounding_digits = 1
    if rounding_digits is None:
        rounding_digits = 1

    start_year = int(request.args.get('start_year', Config.START_YEAR))
    end_year = int(request.args.get('end_year', Config.END_YEAR))
    show_totals = request.args.get("show_totals", "0") == "1"

    # Пытаемся использовать кэш, чтобы не пересчитывать и не вешать страницу
    from app.common.services.database_version_filter import get_current_db_version_id
    current_db_version_id = get_current_db_version_id()
    
    cache_key = build_export_key(
        {**filters},
        rounding_digits,
        start_year,
        end_year,
        False,
        False,
    )
    cached = get_export_payload(session.get('username') or 'anonymous', cache_key)
    # Проверяем, что версия БД в кэше совпадает с текущей
    use_cache = False
    if cached:
        cached_data = cached.get("data") or {}
        params = cached.get("params") or {}
        cached_version_id = params.get("database_version_id")
        
        # Если версия БД совпадает, используем кэш
        if cached_version_id == current_db_version_id:
            use_cache = True
            rounding_digits = params.get("rounding_digits", rounding_digits)
            start_year = params.get("start_year", start_year)
            end_year = params.get("end_year", end_year)
            show_totals = params.get("show_totals", show_totals)
            filename, output = export_station_changes_to_excel(
                user=user,
                filters=filters,
                rounding_digits=rounding_digits,
                start_year=start_year,
                end_year=end_year,
                show_totals=show_totals,
                data=cached_data,
            )
    
    if not use_cache:
        filename, output = export_station_changes_to_excel(
            user=user,
            filters=filters,
            rounding_digits=rounding_digits,
            start_year=start_year,
            end_year=end_year,
            show_totals=show_totals,
        )

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
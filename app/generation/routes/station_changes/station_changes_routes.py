from config import Config
from . import station_changes_bp
from flask import current_app

from app.logs.services.logging_service import log_to_db
from flask_login import login_required
from flask import send_file, render_template, request, session, flash, redirect, url_for, g
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
    export_station_changes_pril_b_to_excel,
    export_station_changes_pril_2_russia_to_excel,
)
from app.generation.services.station_services.export_cache import (
    build_export_key,
    set_export_payload,
    get_export_payload,
)
from app.common.services.get_services.years.years_get_services import (
    get_filter_start_year,
    get_filter_end_year,
)

# Версия структуры/смысла данных, которые кладём в export_cache для station_changes.
# При изменениях логики группировок/агрегаций — увеличивать, чтобы не использовать устаревший кэш.
STATION_CHANGES_EXPORT_PAYLOAD_VERSION = 8

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
    start_year = filters.pop("start_year", None)
    end_year = filters.pop("end_year", None)
    if start_year is None:
        start_year = get_filter_start_year()
    if end_year is None:
        end_year = get_filter_end_year()

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

    # Текущая версия БД (выбранная в сессии) — фиксируем в контексте страницы,
    # чтобы выгрузки из этой вкладки не "перепрыгивали" на версию,
    # которую пользователь мог выбрать в другой вкладке позже.
    current_db_version_id = None
    try:
        from app.common.services.database_version_filter import get_current_db_version_id
        current_db_version_id = get_current_db_version_id()
    except Exception as _e:
        current_app.logger.warning(f"[DB_VERSION] station_changes: failed to resolve current db version: {_e}")

    # Сохраняем данные в кэш для последующей быстрой выгрузки
    try:
        export_key = build_export_key(
            {**filters},
            rounding_digits,
            start_year,
            end_year,
            False,  # show_p_ogr для station_changes не используется
            False,  # show_p_rasp для station_changes не используется
        )
        export_key_appendix_b = build_export_key(
            {**filters, "_export_kind": "appendix_b"},
            rounding_digits,
            start_year,
            end_year,
            False,
            False,
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
                "export_payload_version": STATION_CHANGES_EXPORT_PAYLOAD_VERSION,
            },
        }
        set_export_payload(session.get('username') or 'anonymous', export_key, export_payload)
        # Отдельный кэш-ключ для кнопки «Приложение Б» (на случай дальнейшего расхождения форматов)
        set_export_payload(session.get('username') or 'anonymous', export_key_appendix_b, export_payload)
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
    # Прокидываем версию БД в шаблон для фиксации выгрузок на версии, отображенной на странице
    context["database_version_id"] = current_db_version_id

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

    # Если выгрузка вызвана из конкретной вкладки со "своей" версией БД,
    # принимаем database_version_id из query params и используем его только в рамках текущего запроса
    explicit_version_raw = request.args.get("database_version_id")
    if explicit_version_raw is not None:
        try:
            if explicit_version_raw == "" or explicit_version_raw.lower() in ("none", "null"):
                g.current_db_version = None
            else:
                g.current_db_version = int(explicit_version_raw)
        except Exception:
            # Если параметр некорректен — просто игнорируем и используем версию из middleware/сессии
            pass

    # Параметры из запроса
    filters = extract_filters_from_args(request.args)
    try:
        rounding_digits = int(request.args.get('rounding_digits'))
    except (ValueError, TypeError):
        rounding_digits = 1
    if rounding_digits is None:
        rounding_digits = 1

    start_year = int(request.args.get('start_year', get_filter_start_year()))
    end_year = int(request.args.get('end_year', get_filter_end_year()))
    # Для экспорта «Приложение Б» итоги/агрегации должны выводиться независимо от переключателей на странице
    show_totals = True

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
        cached_payload_version = params.get("export_payload_version")
        
        # Если версия БД совпадает, используем кэш
        if (
            cached_version_id == current_db_version_id
            and cached_payload_version == STATION_CHANGES_EXPORT_PAYLOAD_VERSION
        ):
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


@station_changes_bp.route('/station_changes_list/export_appendix_b', methods=['GET'])
@login_required
def station_changes_list_export_appendix_b():
    user = session.get('username', 'Неизвестный пользователь')

    # Фиксируем версию БД из query params (аналогично основному экспорту)
    explicit_version_raw = request.args.get("database_version_id")
    if explicit_version_raw is not None:
        try:
            if explicit_version_raw == "" or explicit_version_raw.lower() in ("none", "null"):
                g.current_db_version = None
            else:
                g.current_db_version = int(explicit_version_raw)
        except Exception:
            pass

    filters = extract_filters_from_args(request.args)
    try:
        rounding_digits = int(request.args.get('rounding_digits'))
    except (ValueError, TypeError):
        rounding_digits = 1
    if rounding_digits is None:
        rounding_digits = 1

    start_year = int(request.args.get('start_year', get_filter_start_year()))
    end_year = int(request.args.get('end_year', get_filter_end_year()))
    show_totals = request.args.get("show_totals", "0") == "1"

    # Для «Приложение Б» используем отдельный cache key
    from app.common.services.database_version_filter import get_current_db_version_id
    current_db_version_id = get_current_db_version_id()

    cache_key = build_export_key(
        {**filters, "_export_kind": "appendix_b"},
        rounding_digits,
        start_year,
        end_year,
        False,
        False,
    )
    cached = get_export_payload(session.get('username') or 'anonymous', cache_key)

    use_cache = False
    if cached:
        cached_data = cached.get("data") or {}
        params = cached.get("params") or {}
        cached_version_id = params.get("database_version_id")
        cached_payload_version = params.get("export_payload_version")

        if (
            cached_version_id == current_db_version_id
            and cached_payload_version == STATION_CHANGES_EXPORT_PAYLOAD_VERSION
        ):
            use_cache = True
            rounding_digits = params.get("rounding_digits", rounding_digits)
            start_year = params.get("start_year", start_year)
            end_year = params.get("end_year", end_year)
            filename, output = export_station_changes_pril_b_to_excel(
                user=user,
                filters=filters,
                rounding_digits=rounding_digits,
                start_year=start_year,
                end_year=end_year,
                show_totals=show_totals,
                data=cached_data,
            )

    if not use_cache:
        filename, output = export_station_changes_pril_b_to_excel(
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


@station_changes_bp.route('/station_changes_list/export_pril_2_russia', methods=['GET'])
@login_required
def station_changes_list_export_pril_2_russia():
    """
    Приложение 2 (Россия): копия функционала экспорта изменений в Excel.
    """
    user = session.get('username', 'Неизвестный пользователь')

    # Фиксируем версию БД из query params (аналогично основному экспорту)
    explicit_version_raw = request.args.get("database_version_id")
    if explicit_version_raw is not None:
        try:
            if explicit_version_raw == "" or explicit_version_raw.lower() in ("none", "null"):
                g.current_db_version = None
            else:
                g.current_db_version = int(explicit_version_raw)
        except Exception:
            pass

    # Для «Приложение 2 (Россия)» выгрузка должна быть независимой от фильтров на странице:
    # всегда выгружаем по всей РФ.
    _filters_from_args = extract_filters_from_args(request.args)
    filters = {}
    try:
        rounding_digits = int(request.args.get('rounding_digits'))
    except (ValueError, TypeError):
        rounding_digits = 1
    if rounding_digits is None:
        rounding_digits = 1

    start_year = int(request.args.get('start_year', get_filter_start_year()))
    end_year = int(request.args.get('end_year', get_filter_end_year()))
    show_totals = request.args.get("show_totals", "0") == "1"

    from app.common.services.database_version_filter import get_current_db_version_id
    current_db_version_id = get_current_db_version_id()

    cache_key = build_export_key(
        {"_export_kind": "pril_2_russia"},
        rounding_digits,
        start_year,
        end_year,
        False,
        False,
    )
    cached = get_export_payload(session.get('username') or 'anonymous', cache_key)

    use_cache = False
    if cached:
        cached_data = cached.get("data") or {}
        params = cached.get("params") or {}
        cached_version_id = params.get("database_version_id")
        cached_payload_version = params.get("export_payload_version")

        if (
            cached_version_id == current_db_version_id
            and cached_payload_version == STATION_CHANGES_EXPORT_PAYLOAD_VERSION
        ):
            use_cache = True
            rounding_digits = params.get("rounding_digits", rounding_digits)
            start_year = params.get("start_year", start_year)
            end_year = params.get("end_year", end_year)
            show_totals = params.get("show_totals", show_totals)
            filename, output = export_station_changes_pril_2_russia_to_excel(
                user=user,
                filters=filters,
                rounding_digits=rounding_digits,
                start_year=start_year,
                end_year=end_year,
                show_totals=show_totals,
                data=cached_data,
            )

    if not use_cache:
        filename, output = export_station_changes_pril_2_russia_to_excel(
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
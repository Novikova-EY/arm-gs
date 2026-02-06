from app.generation.routes.stations import station_bp
from app.extensions import db
from flask import (
    request, redirect, url_for, flash, session, current_app
)
from app.logs.services.logging_service import log_to_db
from flask_login import login_required
from app.auth.routes import roles_required
from flask import session
from app.generation.services.station_services.import_station_services import (
    import_station_list_from_excel,
    import_fuel_tes_station_from_excel,
)
from app.generation.services.station_services.station_services import clear_station_aggregation_cache
from app.generation.services.station_services.aggregation_cache import warmup_station_cache
from app.common.services.cache_decorator import invalidate_cache_pattern
from app.common.services.cache_services import CacheService
from app.common.services.choices_cache_service import ChoicesCacheService


@station_bp.route("/import_stations_from_excel", methods=["POST"])
def import_station_list_from_excel_routes():
    """Маршрут для импорта данных электростанций из Excel."""
    
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат импорт данных электростанций из Excel")
    current_app.logger.info(
        "[IMPORT_STATIONS_ROUTE] start user=%s filename=%s mimetype=%s remote_addr=%s",
        user,
        getattr(request.files.get("file"), "filename", None),
        getattr(request.files.get("file"), "mimetype", None),
        request.remote_addr,
    )

    if 'file' not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("station_bp.station_list"))

    file = request.files['file']
    if file.mimetype not in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("station_bp.station_list"))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("station_bp.station_list"))

    try:
        result = import_station_list_from_excel(file, user)
        flash(result['message'], "success")
        current_app.logger.info(
            "[IMPORT_STATIONS_ROUTE] done user=%s filename=%s processed=%s errors=%s",
            user,
            getattr(file, "filename", None),
            result.get("processed_rows"),
            result.get("errors_count"),
        )

        # После успешного импорта перечня станций полностью обновляем кэши,
        # чтобы station_list и связанные агрегированные суммы использовали новые данные.
        try:
            # Кэш агрегированных сумм и постраничных списков станций
            clear_station_aggregation_cache("after station list import")
            # Инвалидация всех station_list-* ключей в Redis-кэше
            invalidate_cache_pattern("station_list:*")
            # Прогрев кэша отсортированного списка станций (как при ручном /refresh_cache)
            warmup_station_cache(force=True)
            # Очистка кэша справочников и зависимых LRU-кэшей
            CacheService.clear_cache()
            ChoicesCacheService.clear_cache()
        except Exception as cache_exc:
            current_app.logger.warning(f"[IMPORT_STATIONS_ROUTE] cache clear failed after import: {cache_exc}")

    except ValueError as e:
        current_app.logger.warning(
            "[IMPORT_STATIONS_ROUTE] validation error user=%s filename=%s: %s",
            user,
            getattr(file, "filename", None),
            str(e),
            exc_info=True,
        )
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.exception(
            "[IMPORT_STATIONS_ROUTE] import failed user=%s filename=%s",
            user,
            getattr(file, "filename", None),
        )
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("station_bp.station_list"))


@station_bp.route("/import_fuel_tes_station_from_excel", methods=["POST"])
def import_fuel_tes_station_from_excel_routes():
    """Маршрут для импорта данных по топливу электростанций из Excel."""
    
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат импорт данных по топливу электростанций из Excel")
    current_app.logger.info(
        "[IMPORT_FUEL_ROUTE] start user=%s filename=%s mimetype=%s remote_addr=%s",
        user,
        getattr(request.files.get("file"), "filename", None),
        getattr(request.files.get("file"), "mimetype", None),
        request.remote_addr,
    )

    if 'file' not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("station_bp.station_list"))

    file = request.files['file']
    if file.mimetype not in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("station_bp.station_list"))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("station_bp.station_list"))

    try:
        result = import_fuel_tes_station_from_excel(file, user)
        flash(result['message'], "success")
        current_app.logger.info(
            "[IMPORT_FUEL_ROUTE] done user=%s filename=%s processed=%s errors=%s",
            user,
            getattr(file, "filename", None),
            result.get("processed_rows"),
            result.get("errors_count"),
        )

        # После успешного импорта топлива по станциям обновляем кэши,
        # чтобы station_list и агрегированные суммы сразу использовали новые данные по топливу.
        try:
            clear_station_aggregation_cache("after station fuel import")
            invalidate_cache_pattern("station_list:*")
            warmup_station_cache(force=True)
            CacheService.clear_cache()
            ChoicesCacheService.clear_cache()
        except Exception as cache_exc:
            current_app.logger.warning(f"[IMPORT_FUEL_ROUTE] cache clear failed after import: {cache_exc}")

    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.exception(
            "[IMPORT_FUEL_ROUTE] import failed user=%s filename=%s",
            user,
            getattr(file, "filename", None),
        )
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("station_bp.station_list"))
from . import station_bp
from app import db
from flask import (
    request, redirect, url_for, flash, session, current_app
)
from app.services.logging_services.logging_service import log_to_db
from flask_login import login_required
from app.routes.auth import roles_required
from flask import session
from app.services.station_services.import_station_services import (
    import_station_list_from_excel, 
    import_fuel_tes_station_from_excel, 
)


@station_bp.route("/import_stations_from_excel", methods=["POST"])
def import_station_list_from_excel_routes():
    """Маршрут для импорта данных электростанций из Excel."""
    
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат импорт данных электростанций из Excel")

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
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("station_bp.station_list"))


@station_bp.route("/import_fuel_tes_station_from_excel", methods=["POST"])
def import_fuel_tes_station_from_excel_routes():
    """Маршрут для импорта данных по топливу электростанций из Excel."""
    
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат импорт данных по топливу электростанций из Excel")

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
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("station_bp.station_list"))
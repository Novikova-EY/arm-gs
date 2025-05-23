from . import station_bp
from config import Config
from zipfile import ZipFile
from io import BytesIO
from datetime import datetime
from flask import request, send_file
from app.services.logging_services.logging_service import log_to_db
from flask_login import login_required
from app.routes.auth import role_required
from flask import (
    request, redirect, url_for, flash, session, current_app, send_file
)
from app.services.station_services.station_services import (
    get_station_list_data
)
from app.services.station_services.filters_services import (
    extract_filters_from_args
)
from app.services.station_services.station_export_services import (
    export_station_sipr_ees_application_2_service, 
    generate_excel_export_with_all_totals,
)

@station_bp.route('/export_station_sipr_ees_application_2', methods=['GET'])
def export_station_sipr_ees_application_2_routes():
    """Маршрут для экспорта данных в Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    
    filters = {
        key: request.args.get(key)
        for key in [
            'energy_system_type_filter', 'union_energy_system_filter', 
            'regional_energy_system_filter', 'federal_district_filter', 
            'regional_district_filter'
        ]
    }

    # Фильтруем None-значения, чтобы `url_for()` не получил их
    filters = {k: v for k, v in filters.items() if v}


    try:
        # Получение данных для экспорта
        excel_files = export_station_sipr_ees_application_2_service(user, filters)

        # Проверка наличия данных
        if not excel_files:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("station_bp.station_list"))

        # Если возвращён один файл, отправляем его напрямую
        if isinstance(excel_files, tuple):
            file_name, file_obj = excel_files
            return send_file(
                file_obj,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=file_name
            )

        # Если файлов несколько, создаём ZIP-архив
        zip_buffer = BytesIO()
        with ZipFile(zip_buffer, 'w') as zip_file:
            for file_name, file_obj in excel_files:
                zip_file.writestr(file_name, file_obj.getvalue())

        zip_buffer.seek(0)

        return send_file(
            zip_buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"Экспорт_станций_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        )

    except Exception as e:
        current_app.logger.error(f"Ошибка экспорта: {e}")
        print(f"Ошибка экспорта: {e}")
        flash("Ошибка экспорта данных. Пожалуйста, попробуйте снова.", "danger")
        return redirect(url_for("station_bp.station_list", **filters))


@station_bp.route('/export_station_full', methods=['GET'])
def export_station_full_routes():
    filters = extract_filters_from_args(request.args)
    start_year = int(request.args.get("start_year", Config.START_YEAR))
    end_year = int(request.args.get("end_year", Config.END_YEAR))
    rounding_digits = request.args.get("rounding_digits", "1")
    per_page = request.args.get("per_page", "all")
    show_p_ogr = request.args.get("show_p_ogr") == "1"
    show_p_rasp = request.args.get("show_p_rasp") == "1"

    try:
        rounding_digits = int(rounding_digits)
        if rounding_digits == 0:
            rounding_digits = None
    except (ValueError, TypeError):
        rounding_digits = 1

    data = get_station_list_data(
        filters=filters,
        per_page=None,
        page=1,
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        show_p_ogr=show_p_ogr,
        show_p_rasp=show_p_rasp,
    )

    excel_file = generate_excel_export_with_all_totals(
        data=data,
        start_year=start_year,
        end_year=end_year,
        rounding_digits=rounding_digits,
        show_p_ogr=show_p_ogr,
        show_p_rasp=show_p_rasp,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"stations_export_{timestamp}.xlsx"

    return send_file(
        excel_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

    
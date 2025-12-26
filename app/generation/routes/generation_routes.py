from . import generation_bp
from . import totals_summary_routes  # noqa: F401  # регистрирует маршруты totals_summary
from flask import (
    render_template, request, send_file, flash, redirect, url_for, current_app
)
from flask_login import login_required
from datetime import datetime

@generation_bp.route("/generation")
def generation_start():
    """Простой роут для главной страницы модуля Генерация."""
    return render_template("generation/generation_start.html")

@generation_bp.route("/totals_summary_export")
@login_required
def totals_summary_export():
    """Маршрут для экспорта итоговых сумм в Excel.
    Открывается в новом окне и автоматически закрывается после выгрузки файла."""
    from config import Config
    from app.generation.services.station_services.export_totals_summary_services import export_totals_summary_to_excel
    
    # Получение параметров запроса
    start_year = request.args.get("start_year", type=int) or Config.START_YEAR
    end_year = request.args.get("end_year", type=int) or Config.END_YEAR
    show_p_ogr = request.args.get("show_p_ogr", "0") == "1"
    show_p_rasp = request.args.get("show_p_rasp", "0") == "1"
    
    # Типы агрегации: можно выбрать несколько (ees, tites, russia, sync_area_{id})
    aggregation_types = request.args.getlist("aggregation_type")
    if not aggregation_types:
        aggregation_types = ["ees"]  # По умолчанию только ЕЭС

    valid_types = ["ees", "tites", "russia"]
    filtered_aggregation_types = []
    for at in aggregation_types:
        if at in valid_types:
            filtered_aggregation_types.append(at)
        elif at.startswith("sync_area_"):
            # Разрешаем синхронные зоны в экспорте (как на экране)
            try:
                int(at.replace("sync_area_", ""))
                filtered_aggregation_types.append(at)
            except ValueError:
                pass
    aggregation_types = filtered_aggregation_types
    if not aggregation_types:
        aggregation_types = ["ees"]  # Если все невалидные, возвращаемся к умолчанию
    
    try:
        rounding_digits = int(request.args.get('rounding_digits', 1))
    except (ValueError, TypeError):
        rounding_digits = 1

    if rounding_digits is None or rounding_digits < 0:
        rounding_digits = 1
    
    try:
        excel_file = export_totals_summary_to_excel(
            start_year=start_year,
            end_year=end_year,
            show_p_ogr=show_p_ogr,
            show_p_rasp=show_p_rasp,
            rounding_digits=rounding_digits,
            aggregation_types=aggregation_types,
        )
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"totals_summary_{timestamp}.xlsx"
        
        return send_file(
            excel_file,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f"Ошибка экспорта totals_summary: {e}\n{error_details}")
        # В новом окне показываем ошибку и закрываем окно
        return render_template("generation/stations_total_summary/export_error.html", 
                             error_message="Ошибка экспорта данных. Пожалуйста, попробуйте снова.")
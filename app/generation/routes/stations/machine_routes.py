from config import Config
from app.generation.routes.stations import station_bp
from app.extensions import db
from flask import render_template, request, session, flash, redirect, url_for
from flask_login import login_required
from app.auth.routes import roles_required
from app.generation.services.machine_services.machine_services import (
    handle_machine_get,
    handle_machine_post, 
    handle_pgu_machine_get,
    handle_pgu_machine_post, 
    _fill_pgu_machines_form_choices,
    to_decimal
)
from app.generation.services.station_services.station_services import (
    get_machine_by_id,
    get_station_by_id, 
    recalculate_station_power,
)
from app.common.services.help_services import (
    convert_to_date,
)
from app.common.services.get_services.years.years_get_services import (
    get_year_feature_dict,
)
from app.logs.models.log_model import Log
from sqlalchemy import or_
from app.common.middleware import handle_stale_data
from app.common.services.cache_decorator import invalidate_cache, invalidate_cache_pattern


def _format_logs_for_display(logs):
    """
    Предварительное форматирование логов для оптимизации рендеринга шаблона.
    Форматирует даты и применяет lower() в Python вместо Jinja2.
    """
    formatted_logs = []
    for log in logs:
        formatted_log = {
            'date': log.timestamp.strftime('%Y-%m-%d') if log.timestamp else '',
            'time': log.timestamp.strftime('%H:%M:%S') if log.timestamp else '',
            'username': log.username or '',
            'username_lower': (log.username or '').lower(),
            'action': log.action or '',
            'action_lower': (log.action or '').lower(),
            'details': log.details or '',
            'details_lower': (log.details or '').lower(),
        }
        formatted_logs.append(formatted_log)
    return formatted_logs


@station_bp.route("/machine_logs/<int:station_id>/<int:machine_id>", methods=["GET"])
@login_required
def machine_logs(station_id, machine_id):
    """AJAX endpoint для загрузки всех логов агрегата."""
    from flask import jsonify
    
    machine = get_machine_by_id(machine_id)
    if not machine:
        return jsonify({'error': 'Machine not found'}), 404
    
    # Получаем параметр offset для пагинации
    offset = request.args.get("offset", 0, type=int)
    limit = request.args.get("limit", 150, type=int)
    
    logs_query = (
        db.session.query(Log)
        .filter(
            or_(
                (Log.entity_type == 'machine') & (Log.entity_id == machine_id),
                Log.details.ilike(f"%machine_id={machine_id}%"),
                Log.details.ilike(f"%агрегата №{machine.machine_number}%")
            )
        )
        .order_by(Log.timestamp.desc())
    )
    
    total_count = logs_query.count()
    logs_raw = logs_query.offset(offset).limit(limit).all()
    logs_formatted = _format_logs_for_display(logs_raw)
    
    return jsonify({
        'logs': logs_formatted,
        'offset': offset,
        'limit': limit,
        'count': len(logs_formatted),
        'total': total_count,
        'has_more': (offset + len(logs_formatted)) < total_count
    })


@station_bp.route("/machine_details/<int:station_id>/<int:machine_id>", methods=["GET", "POST"])
@login_required
@handle_stale_data
def machine_details(station_id, machine_id):
    import time
    start_time = time.time()
    
    user = session.get('username', 'Неизвестный пользователь')

    start_year = request.args.get("start_year", Config.START_YEAR, type=int)
    end_year = request.args.get("end_year", Config.END_YEAR, type=int)
    rounding_digits = request.args.get("rounding_digits", 1, type=int)

    if request.method == "POST":
        result = handle_machine_post(
            station_id=station_id,
            machine_id=machine_id,
            form_data=request.form,
            user=user,
            start_year=start_year,
            end_year=end_year,
            rounding_digits=rounding_digits,
        )
        elapsed = time.time() - start_time
        print(f"[TIME] machine_details POST (station: {station_id}, machine: {machine_id}) заняла: {elapsed:.2f} сек")
        return result
    else:
        result = handle_machine_get(station_id, machine_id, start_year, end_year, rounding_digits)
        
        # Для нового агрегата (machine=None) логов еще нет
        if result['machine'] and result['machine'].machine_number:
            machine_logs = _format_logs_for_display(
                db.session.query(Log)
                .filter(
                    or_(
                        (Log.entity_type == 'machine') & (Log.entity_id == machine_id),
                        Log.details.ilike(f"%machine_id={machine_id}%"),
                        Log.details.ilike(f"%агрегата №{result['machine'].machine_number}%")
                    )
                )
                .order_by(Log.timestamp.desc())
                .limit(20)  # Уменьшено со 200 до 50 для ускорения рендеринга
                .all()
            )
        else:
            machine_logs = []
        
        elapsed = time.time() - start_time
        print(f"[TIME] machine_details GET (station: {station_id}, machine: {machine_id}) заняла: {elapsed:.2f} сек")
        
        return render_template(
            "generation/stations/machine_details.html",
            main_form=result['main_form'],
            advanced_form=result['advanced_form'],
            pgu_machines_form=result['pgu_machines_form'],
            pgu_machines=result['pgu_machines'],
            station=result['station'],
            machine=result['machine'],
            start_year=start_year,
            end_year=end_year,
            rounding_digits=rounding_digits,
            year_features=result['year_features'],
            machine_logs=machine_logs,
            all_documents=result['all_documents']
        )

@station_bp.route("/pgu_machine_details/<int:station_id>/<int:machine_id>/<int:pgu_machine_id>", methods=["GET", "POST"])
@login_required
@handle_stale_data
def pgu_machine_details(station_id, machine_id, pgu_machine_id):
    import time
    start_time = time.time()
    
    user = session.get('username', 'Неизвестный пользователь')

    start_year = request.args.get("start_year", Config.START_YEAR, type=int)
    end_year = request.args.get("end_year", Config.END_YEAR, type=int)
    rounding_digits = request.args.get("rounding_digits", 1, type=int)

    if request.method == "POST":
        result = handle_pgu_machine_post(
            station_id=station_id,
            machine_id=machine_id,
            pgu_machine_id=pgu_machine_id,
            form_data=request.form,
            user=user,
            start_year=start_year,
            end_year=end_year
        )
        elapsed = time.time() - start_time
        print(f"[TIME] pgu_machine_details POST (station: {station_id}, machine: {machine_id}, pgu: {pgu_machine_id}) заняла: {elapsed:.2f} сек")
        return result

    else:
        result = handle_pgu_machine_get(
            station_id=station_id,
            machine_id=machine_id,
            pgu_machine_id=pgu_machine_id,
            start_year=start_year,
            end_year=end_year
        )

        # Загружаем журнал изменений для ПГУ-агрегата (если он существует)
        pgu_machine_logs = []
        try:
            if result.get('pgu_machine') and result['pgu_machine'].id:
                pm_id = result['pgu_machine'].id
                pgu_machine_logs = _format_logs_for_display(
                    db.session.query(Log)
                    .filter(
                        or_(
                            Log.action.ilike("%ПГУ агрегат%"),
                            Log.details.ilike("%ПГУ агрегат%"),
                            Log.details.ilike(f"%ID: {pm_id}%"),
                            Log.details.ilike(f"%pgu_machine_id={pm_id}%")
                        )
                    )
                    .order_by(Log.timestamp.desc())
                    .limit(50)  # Уменьшено со 200 до 50 для ускорения рендеринга
                    .all()
                )
        except Exception:
            pgu_machine_logs = []

        elapsed = time.time() - start_time
        print(f"[TIME] pgu_machine_details GET (station: {station_id}, machine: {machine_id}, pgu: {pgu_machine_id}) заняла: {elapsed:.2f} сек")

        return render_template(
            "generation/stations/pgu_machine_details.html",
            station=result['station'],
            parent_machine=result['parent_machine'],
            pgu_form=result['pgu_form'],
            start_year=result['start_year'],
            end_year=result['end_year'],
            pgu_machine_id=result['pgu_machine_id'],
            year_features=result['year_features'],
            pgu_machine=result.get('pgu_machine'),
            pgu_machine_logs=pgu_machine_logs,
            rounding_digits=rounding_digits,
        )
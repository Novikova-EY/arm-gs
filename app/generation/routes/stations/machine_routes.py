from config import Config
from app.generation.routes.stations import station_bp
from app.extensions import db
from urllib.parse import urlencode

from flask import render_template, request, session, flash, redirect, url_for, abort, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import time
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
    get_filter_start_year,
    get_filter_end_year,
)
from app.logs.models.log_model import Log
from app.logs.services.log_display_utils import format_logs_for_display as _format_logs_for_display
from sqlalchemy import or_
from app.common.middleware import handle_stale_data
from app.generation.services.station_services.station_services import get_station_by_id
from app.logs.services.logging_service import log_to_db
from app.generation.services.station_services.generation_year_filter_services import (
    resolve_generation_year_filters_for_request,
)


def _normalize_start_end_years(start_year: int, end_year: int) -> tuple[int, int]:
    """
    Если «год начала» больше «года конца», в шаблоне и в handle_machine_get
    получается пустой range(start_year, end_year + 1) — таблицы без столбцов данных.
    Приводим к допустимому интервалу [min, max].
    """
    if start_year > end_year:
        return end_year, start_year
    return start_year, end_year


def _machine_log_entity_ids(machine_id: int) -> list[int]:
    """Все id агрегата по версиям БД (external_code) для журнала изменений."""
    from app.generation.models.machine.machine_model import Machine
    from app.common.services.version_entity_resolve_services import (
        entity_log_ids_by_external_code,
    )

    return entity_log_ids_by_external_code(Machine, machine_id)


def _query_machine_logs_fast(machine_id: int, machine_number: int | None, limit: int = 20):
    """Возвращает последние `limit` логов для агрегата, приоритизируя быстрые фильтры.

    Сначала берем записи, где явно установлен entity_type/entity_id — этот запрос использует
    индексы и выполняется мгновенно. Если записей меньше, добираем по старому шаблону из details,
    где агрегат упоминается только текстом.
    """
    machine_entity_ids = _machine_log_entity_ids(machine_id)
    primary_query = (
        db.session.query(Log)
        .filter(
            (Log.entity_type == "machine") & (Log.entity_id.in_(machine_entity_ids))
        )
        .order_by(Log.timestamp.desc())
    )

    primary_logs = primary_query.limit(limit).all()
    if len(primary_logs) >= limit:
        return primary_logs

    remaining = limit - len(primary_logs)
    excluded_ids = {log.id for log in primary_logs}

    fallback_conditions = [Log.details.ilike(f"%machine_id={machine_id}%")]
    if machine_number is not None:
        fallback_conditions.append(Log.details.ilike(f"%агрегата №{machine_number}%"))

    MAX_SCAN = 5000
    recent_ids_subq = (
        db.session.query(Log.id)
        .order_by(Log.timestamp.desc())
        .limit(MAX_SCAN)
        .subquery()
    )

    fallback_base = (
        db.session.query(Log)
        .join(recent_ids_subq, Log.id == recent_ids_subq.c.id)
        .filter(or_(*fallback_conditions))
        .order_by(Log.timestamp.desc())
    )

    now_utc = datetime.utcnow()
    time_windows = [timedelta(days=365), timedelta(days=3 * 365), None]
    fallback_logs = []

    for window in time_windows:
        if remaining <= 0:
            break

        query = fallback_base
        if window is not None:
            threshold = now_utc - window
            query = query.filter(Log.timestamp >= threshold)

        if excluded_ids:
            query = query.filter(~Log.id.in_(excluded_ids))

        chunk = query.limit(remaining).all()
        if not chunk:
            continue

        fallback_logs.extend(chunk)
        excluded_ids.update(log.id for log in chunk)
        remaining = limit - len(primary_logs) - len(fallback_logs)

    combined = primary_logs + fallback_logs
    combined.sort(key=lambda rec: rec.timestamp or datetime.min, reverse=True)
    return combined[:limit]


def _resolved_station_id_for_current_version(station_id: int) -> int | None:
    """ID станции в выбранной версии БД, если исходный URL указывает на ее копию."""
    from app.common.services.database_version_filter import get_current_db_version_id
    from app.common.services.version_entity_resolve_services import load_by_id_with_version
    from app.generation.models.station.station_model import Station

    station = load_by_id_with_version(
        Station,
        station_id,
        get_current_db_version_id(),
    )
    return station.id if station else None


@station_bp.route("/machine_logs/<int:station_id>/<int:machine_id>", methods=["GET"])
@login_required
def machine_logs(station_id, machine_id):
    """AJAX endpoint для загрузки всех логов агрегата."""
    from flask import jsonify
    from app.common.services.version_entity_resolve_services import resolve_machine_details_ids

    resolved = resolve_machine_details_ids(station_id, machine_id)
    if not resolved:
        return jsonify({'error': 'Machine not found'}), 404
    _, machine_id = resolved

    machine = get_machine_by_id(machine_id)
    if not machine:
        return jsonify({'error': 'Machine not found'}), 404
    
    # Получаем параметр offset для пагинации
    offset = request.args.get("offset", 0, type=int)
    limit = request.args.get("limit", 150, type=int)
    
    machine_entity_ids = _machine_log_entity_ids(machine_id)
    logs_query = (
        db.session.query(Log)
        .filter(
            or_(
                (Log.entity_type == "machine") & (Log.entity_id.in_(machine_entity_ids)),
                Log.details.ilike(f"%machine_id={machine_id}%"),
                Log.details.ilike(f"%агрегата №{machine.machine_number}%"),
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
    start_time = time.perf_counter()
    
    user = session.get('username', 'Неизвестный пользователь')

    rounding_digits = request.values.get("rounding_digits", 1, type=int)

    if request.method == "GET":
        start_year, end_year, year_redirect = resolve_generation_year_filters_for_request()
        if year_redirect:
            return year_redirect
    else:
        start_year = request.values.get("start_year", get_filter_start_year(), type=int)
        end_year = request.values.get("end_year", get_filter_end_year(), type=int)

    nsy, ney = _normalize_start_end_years(start_year, end_year)
    if request.method == "GET" and (nsy, ney) != (start_year, end_year):
        q = request.args.to_dict(flat=True)
        q["start_year"] = nsy
        q["end_year"] = ney
        target = url_for(
            "station_bp.machine_details",
            station_id=station_id,
            machine_id=machine_id,
        )
        return redirect(f"{target}?{urlencode(q)}")
    start_year, end_year = nsy, ney

    from app.common.services.version_entity_resolve_services import resolve_machine_details_ids

    resolved = resolve_machine_details_ids(station_id, machine_id)
    if not resolved:
        if request.method == "GET" and machine_id != 0:
            resolved_station_id = _resolved_station_id_for_current_version(station_id)
            if resolved_station_id is not None:
                flash(
                    "Агрегат отсутствует в выбранной версии БД. "
                    "Открыта карточка электростанции в текущей версии.",
                    "warning",
                )
                q = request.args.to_dict(flat=True)
                q["start_year"] = start_year
                q["end_year"] = end_year
                return redirect(
                    url_for(
                        "station_bp.station_details",
                        station_id=resolved_station_id,
                        **q,
                    )
                )
        abort(404)
    resolved_station_id, resolved_machine_id = resolved
    if request.method == "GET" and (
        resolved_station_id != station_id or resolved_machine_id != machine_id
    ):
        q = request.args.to_dict(flat=True)
        q["start_year"] = start_year
        q["end_year"] = end_year
        target = url_for(
            "station_bp.machine_details",
            station_id=resolved_station_id,
            machine_id=resolved_machine_id,
        )
        return redirect(f"{target}?{urlencode(q)}")
    station_id, machine_id = resolved_station_id, resolved_machine_id

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
        elapsed = time.perf_counter() - start_time
        print(f"[TIME] machine_details POST (station: {station_id}, machine: {machine_id}) заняла: {elapsed:.2f} сек")
        return result
    else:
        handle_start = time.perf_counter()
        result = handle_machine_get(station_id, machine_id, start_year, end_year, rounding_digits)
        handle_elapsed = time.perf_counter() - handle_start
        
        # Загружаем журнал изменений, если агрегат существует
        machine_obj = result.get('machine')
        if machine_obj:
            logs_start = time.perf_counter()
            machine_logs = _format_logs_for_display(
                _query_machine_logs_fast(
                    machine_obj.id,
                    machine_obj.machine_number or None,
                    limit=20,
                )
            )
            logs_elapsed = time.perf_counter() - logs_start
        else:
            machine_logs = []
            logs_elapsed = 0.0

        render_start = time.perf_counter()
        can_save_machine_all_versions = (
            current_user.is_authenticated
            and getattr(current_user, "has_admin", False)
            and machine_obj is not None
        )
        response = render_template(
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
            version_year_start=result.get('version_year_start'),
            version_year_end=result.get('version_year_end'),
            machine_logs=machine_logs,
            all_documents=result['all_documents'],
            fallback_gen_company=result.get('fallback_gen_company'),
            can_save_machine_all_versions=can_save_machine_all_versions,
            can_create_machine=result.get('can_create_machine', False),
        )
        render_elapsed = time.perf_counter() - render_start
        total_elapsed = time.perf_counter() - start_time
        print(
            f"[PERF][machine_details] station={station_id} machine={machine_id} total={total_elapsed:.2f}s"
            f" (handle={handle_elapsed:.2f}s, logs={logs_elapsed:.2f}s, render={render_elapsed:.2f}s)"
        )
        return response

@station_bp.route("/pgu_machine_details/<int:station_id>/<int:machine_id>/<int:pgu_machine_id>", methods=["GET", "POST"])
@login_required
@handle_stale_data
def pgu_machine_details(station_id, machine_id, pgu_machine_id):
    import time
    start_time = time.time()
    
    user = session.get('username', 'Неизвестный пользователь')

    # При POST start_year/end_year приходят в теле формы, при GET — в URL.
    # Для pgu_machine_details поведение должно совпадать с machine_details:
    # берем значения из запроса без принудительного "зажатия" к диапазону версии.
    start_year = request.values.get("start_year", get_filter_start_year(), type=int)
    end_year = request.values.get("end_year", get_filter_end_year(), type=int)
    rounding_digits = request.values.get("rounding_digits", 1, type=int)

    nsy, ney = _normalize_start_end_years(start_year, end_year)
    if request.method == "GET" and (nsy, ney) != (start_year, end_year):
        q = request.args.to_dict(flat=True)
        q["start_year"] = nsy
        q["end_year"] = ney
        target = url_for(
            "station_bp.pgu_machine_details",
            station_id=station_id,
            machine_id=machine_id,
            pgu_machine_id=pgu_machine_id,
        )
        return redirect(f"{target}?{urlencode(q)}")
    start_year, end_year = nsy, ney

    if request.method == "POST":
        result = handle_pgu_machine_post(
            station_id=station_id,
            machine_id=machine_id,
            pgu_machine_id=pgu_machine_id,
            form_data=request.form,
            user=user,
            start_year=start_year,
            end_year=end_year,
            rounding_digits=rounding_digits,
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
                # Оптимизация: используем entity_type/entity_id (индексы) вместо ILIKE (полный скан)
                pgu_machine_logs = _format_logs_for_display(
                    db.session.query(Log)
                    .filter(
                        or_(
                            (Log.entity_type == "pgu_machine") & (Log.entity_id == pm_id),
                            Log.details.ilike(f"%pgu_machine_id={pm_id}%"),
                        )
                    )
                    .order_by(Log.timestamp.desc())
                    .limit(20)
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
            version_year_end=result.get('version_year_end'),
            all_documents=result.get('all_documents', []),
        )
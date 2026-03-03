from config import Config
from app.generation.routes.stations import station_bp
from app.extensions import db
from flask import render_template, request, session, flash, redirect, url_for
from flask_login import login_required
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
from sqlalchemy import or_
from app.common.middleware import handle_stale_data
from app.common.services.cache_decorator import invalidate_cache, invalidate_cache_pattern
from datetime import timezone
from zoneinfo import ZoneInfo

MOSCOW = ZoneInfo("Europe/Moscow")


def _format_logs_for_display(logs):
    """
    Предварительное форматирование логов для оптимизации рендеринга шаблона.
    Форматирует даты и применяет lower() в Python вместо Jinja2.
    """
    if not logs:
        return []
    
    # Получаем все уникальные версии БД одним запросом для оптимизации
    from app.common.models.database_version_model import DatabaseVersion
    version_ids = {log.database_version_id for log in logs if log.database_version_id}
    versions_map = {}
    if version_ids:
        # Используем оптимизированный запрос с загрузкой только нужных полей
        try:
            versions = db.session.query(DatabaseVersion.id, DatabaseVersion.version_number).filter(
                DatabaseVersion.id.in_(version_ids)
            ).all()
            versions_map = {v.id: v.version_number for v in versions}
        except Exception:
            # Если ошибка - просто показываем ID версии вместо названия
            versions_map = {vid: str(vid) for vid in version_ids}
    
    def _suppress_noop_changes(details_text: str) -> str:
        if not details_text:
            return ''
        def _norm(s: str) -> str:
            if s is None:
                return ''
            # нормализуем регистр, пробелы (включая NBSP) и множественные пробелы
            s2 = s.replace('\u00A0', ' ').replace('\xa0', ' ').strip().lower()
            while '  ' in s2:
                s2 = s2.replace('  ', ' ')
            return s2
        parts = [p.strip() for p in details_text.split(';')]
        filtered = []
        for p in parts:
            if not p:
                continue
            if '→' in p:
                left, right = p.split('→', 1)
                if _norm(left) == _norm(right):
                    continue
                left_value = left.rsplit('-', 1)[-1].strip() if '-' in left else left
                right_value = right
                if _norm(left_value) == _norm(right_value):
                    continue
            filtered.append(p)
        return '; '.join(filtered)

    formatted_logs = []
    for log in logs:
        details_clean = _suppress_noop_changes(log.details or '')
        ts = log.timestamp
        if ts is not None:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            ts_msk = ts.astimezone(MOSCOW)
        else:
            ts_msk = None
        formatted_log = {
            'date': ts_msk.strftime('%Y-%m-%d') if ts_msk else '',
            'time': ts_msk.strftime('%H:%M:%S') if ts_msk else '',
            'username': log.username or '',
            'username_lower': (log.username or '').lower(),
            'action': log.action or '',
            'action_lower': (log.action or '').lower(),
            'details': details_clean,
            'details_lower': details_clean.lower(),
            'database_version': versions_map.get(log.database_version_id, '—') if log.database_version_id else '—',
        }
        formatted_logs.append(formatted_log)
    return formatted_logs


def _query_machine_logs_fast(machine_id: int, machine_number: int | None, limit: int = 20):
    """Возвращает последние `limit` логов для агрегата, приоритизируя быстрые фильтры.

    Сначала берем записи, где явно установлен entity_type/entity_id — этот запрос использует
    индексы и выполняется мгновенно. Если записей меньше, добираем по старому шаблону из details,
    где агрегат упоминается только текстом.
    """
    primary_query = (
        db.session.query(Log)
        .filter((Log.entity_type == 'machine') & (Log.entity_id == machine_id))
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
    start_time = time.perf_counter()
    
    user = session.get('username', 'Неизвестный пользователь')

    start_year = request.args.get("start_year", get_filter_start_year(), type=int)
    end_year = request.args.get("end_year", get_filter_end_year(), type=int)
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

    start_year = request.args.get("start_year", get_filter_start_year(), type=int)
    end_year = request.args.get("end_year", get_filter_end_year(), type=int)
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
                # Оптимизированная загрузка ПГУ логов одним запросом с лимитом
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
                    .limit(20)  # Уменьшено с 50 до 20 для ускорения рендеринга
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
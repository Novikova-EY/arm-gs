from flask import Blueprint, render_template, request
from flask_login import current_user
from app.logs.models.log_model import Log
from app.extensions import db
from datetime import datetime, timezone, timedelta, time
from zoneinfo import ZoneInfo
from sqlalchemy import text

MOSCOW = ZoneInfo("Europe/Moscow")

logs_bp = Blueprint('logs', __name__)


def _parse_date_arg(raw: str):
    """Parse YYYY-MM-DD from query; return date or None."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


@logs_bp.route('/logs', methods=['GET'])
def view_logs():
    username_filter = request.args.get('username', '').strip()
    action_filter = request.args.get('action', '').strip()
    details_filter = request.args.get('details', '').strip()
    date_from_raw = request.args.get('date_from', '').strip()
    date_to_raw = request.args.get('date_to', '').strip()
    date_from = _parse_date_arg(date_from_raw)
    date_to = _parse_date_arg(date_to_raw)

    # Доступ к чувствительным данным — строго только для роли admin
    role_names = getattr(current_user, "role_names", []) or []
    if not isinstance(role_names, (list, tuple, set)):
        role_names = [role_names]
    is_strict_admin = bool(
        getattr(current_user, "is_authenticated", False)
        and (
            getattr(current_user, "username", None) == "admin"
            or "admin" in role_names
        )
    )
    # Столбец «Версия» и фильтр по версии доступны всем; ранее — только admin
    database_version_filter = request.args.get('database_version_id', '').strip()
    sort_by = request.args.get('sort_by', 'timestamp')
    sort_dir = request.args.get('sort_dir', 'desc')
    per_page = request.args.get('per_page', 25, type=int)
    show_page_events = request.args.get('show_page_events', 'false').lower() == 'true'
    
    if per_page not in [10, 25, 50, 100]:
        per_page = 25

    query = Log.query
    
    # Исключаем события типа "Открыта страница..." для более чистого отображения
    # Показываем их только если явно запрошено через параметр show_page_events=true
    if not show_page_events:
        query = query.filter(~Log.action.ilike("Открыта страница%"))
    
    if username_filter:
        query = query.filter(Log.username.ilike(f"%{username_filter}%"))
    if action_filter:
        query = query.filter(Log.action.ilike(f"%{action_filter}%"))
    if details_filter:
        query = query.filter(Log.details.ilike(f"%{details_filter}%"))
    if database_version_filter:
        try:
            database_version_id = int(database_version_filter)
        except (TypeError, ValueError):
            database_version_id = None
        if database_version_id:
            query = query.filter(Log.database_version_id == database_version_id)

    # Фильтр по дате: границы в МСК, сравнение с timestamp (UTC-aware в БД)
    if date_from:
        start_msk = datetime.combine(date_from, time.min, tzinfo=MOSCOW)
        query = query.filter(Log.timestamp >= start_msk.astimezone(timezone.utc))
    if date_to:
        end_exclusive_msk = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=MOSCOW)
        query = query.filter(Log.timestamp < end_exclusive_msk.astimezone(timezone.utc))

    if hasattr(Log, sort_by):
        column = getattr(Log, sort_by)
        query = query.order_by(db.desc(column) if sort_dir == 'desc' else db.asc(column))

    page = request.args.get('page', 1, type=int)
    logs = query.paginate(page=page, per_page=per_page, error_out=False)

    versions_map = {}
    database_versions = []
    from app.common.models.database_version_model import DatabaseVersion
    version_ids = {log.database_version_id for log in logs.items if log.database_version_id}
    if version_ids:
        try:
            versions = db.session.query(DatabaseVersion.id, DatabaseVersion.version_number).filter(
                DatabaseVersion.id.in_(version_ids)
            ).all()
            versions_map = {v.id: v.version_number for v in versions}
        except Exception:
            versions_map = {vid: str(vid) for vid in version_ids}
    try:
        database_versions = db.session.query(DatabaseVersion.id, DatabaseVersion.version_number).order_by(
            DatabaseVersion.version_number.asc()
        ).all()
    except Exception:
        database_versions = []

    for log in logs.items:
        ts = log.timestamp
        if ts is not None:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            log.timestamp_msk = ts.astimezone(MOSCOW)
        else:
            log.timestamp_msk = None

        log.database_version_display = (
            versions_map.get(log.database_version_id, '—')
            if log.database_version_id
            else '—'
        )

    # ✦ Контрольные часы (один раз за запрос)
    db_now_utc  = db.session.execute(text("SELECT now() AT TIME ZONE 'UTC'")).scalar()
    db_now_msk  = db.session.execute(text("SELECT now() AT TIME ZONE 'Europe/Moscow'")).scalar()
    app_now_utc = datetime.now(timezone.utc)
    app_now_msk = app_now_utc.astimezone(MOSCOW)

    return render_template(
        'logs/logs.html',
        logs=logs,
        username_filter=username_filter,
        action_filter=action_filter,
        details_filter=details_filter,
        date_from=date_from_raw if date_from else '',
        date_to=date_to_raw if date_to else '',
        database_version_filter=database_version_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page,
        show_page_events=show_page_events,
        is_strict_admin=is_strict_admin,
        database_versions=database_versions,
        db_now_utc=db_now_utc, db_now_msk=db_now_msk,
        app_now_utc=app_now_utc, app_now_msk=app_now_msk
    )

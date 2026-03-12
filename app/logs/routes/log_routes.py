from flask import Blueprint, render_template, request
from flask_login import current_user
from app.logs.models.log_model import Log
from app.extensions import db
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import text

MOSCOW = ZoneInfo("Europe/Moscow")

logs_bp = Blueprint('logs', __name__)

@logs_bp.route('/logs', methods=['GET'])
def view_logs():
    username_filter = request.args.get('username', '').strip()
    action_filter = request.args.get('action', '').strip()
    details_filter = request.args.get('details', '').strip()

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
    database_version_filter = request.args.get('database_version_id', '').strip() if is_strict_admin else ''
    sort_by = request.args.get('sort_by', 'timestamp')
    sort_dir = request.args.get('sort_dir', 'desc')
    per_page = request.args.get('per_page', 10, type=int)
    show_page_events = request.args.get('show_page_events', 'false').lower() == 'true'
    
    if per_page not in [10, 25, 50, 100]:
        per_page = 10

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

    if hasattr(Log, sort_by):
        column = getattr(Log, sort_by)
        query = query.order_by(db.desc(column) if sort_dir == 'desc' else db.asc(column))

    page = request.args.get('page', 1, type=int)
    logs = query.paginate(page=page, per_page=per_page, error_out=False)

    versions_map = {}
    database_versions = []
    if is_strict_admin:
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

        # Не отдаём тип/ID сущности не-admin даже в исходнике HTML
        if is_strict_admin:
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
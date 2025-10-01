from flask import Blueprint, render_template, request
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
    entity_type_filter = request.args.get('entity_type', '').strip()
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
    if entity_type_filter:
        query = query.filter(Log.entity_type.ilike(f"%{entity_type_filter}%"))

    if hasattr(Log, sort_by):
        column = getattr(Log, sort_by)
        query = query.order_by(db.desc(column) if sort_dir == 'desc' else db.asc(column))

    page = request.args.get('page', 1, type=int)
    logs = query.paginate(page=page, per_page=per_page, error_out=False)

    for log in logs.items:
        ts = log.timestamp
        if ts is not None:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            log.timestamp_msk = ts.astimezone(MOSCOW)
        else:
            log.timestamp_msk = None

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
        entity_type_filter=entity_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page,
        show_page_events=show_page_events,
        db_now_utc=db_now_utc, db_now_msk=db_now_msk,
        app_now_utc=app_now_utc, app_now_msk=app_now_msk
    )
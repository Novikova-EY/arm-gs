from flask import Blueprint, render_template, request
from app.models import Log
from app import db

logs_bp = Blueprint('logs', __name__)

@logs_bp.route('/logs', methods=['GET'])
def view_logs():
    # Получение параметров фильтрации и сортировки
    username_filter = request.args.get('username', '').strip()
    action_filter = request.args.get('action', '').strip()
    sort_by = request.args.get('sort_by', 'timestamp')  # Поле для сортировки
    sort_dir = request.args.get('sort_dir', 'desc')  # Направление сортировки

    # Запрос с фильтрацией
    query = Log.query
    if username_filter:
        query = query.filter(Log.username.ilike(f"%{username_filter}%"))
    if action_filter:
        query = query.filter(Log.action.ilike(f"%{action_filter}%"))

    # Сортировка
    if sort_by in ['timestamp', 'username', 'action']:
        if sort_dir == 'desc':
            query = query.order_by(db.desc(getattr(Log, sort_by)))
        else:
            query = query.order_by(db.asc(getattr(Log, sort_by)))

    # Пагинация
    page = request.args.get('page', 1, type=int)
    per_page = 10
    logs = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('logs.html', logs=logs, username_filter=username_filter, action_filter=action_filter, sort_by=sort_by, sort_dir=sort_dir)

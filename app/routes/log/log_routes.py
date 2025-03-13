from flask import Blueprint, render_template, request
from app.models.logs_models import Log
from app import db

logs_bp = Blueprint('logs', __name__)

@logs_bp.route('/logs', methods=['GET'])
def view_logs():
    # Получение параметров фильтрации и сортировки
    username_filter = request.args.get('username', '').strip()
    action_filter = request.args.get('action', '').strip()
    sort_by = request.args.get('sort_by', 'timestamp')  # Поле для сортировки
    sort_dir = request.args.get('sort_dir', 'desc')  # Направление сортировки

    # Получение количества записей на странице (по умолчанию 10)
    per_page = request.args.get('per_page', 10, type=int)
    if per_page not in [10, 25, 50, 100]:  # Защита от некорректных значений
        per_page = 10

    # Запрос с фильтрацией
    query = Log.query
    if username_filter:
        query = query.filter(Log.username.ilike(f"%{username_filter}%"))
    if action_filter:
        query = query.filter(Log.action.ilike(f"%{action_filter}%"))

    # Проверка, существует ли поле сортировки, чтобы избежать ошибок
    if hasattr(Log, sort_by):
        column = getattr(Log, sort_by)
        query = query.order_by(db.desc(column) if sort_dir == 'desc' else db.asc(column))

    # Пагинация
    page = request.args.get('page', 1, type=int)
    logs = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        'logs/logs.html',
        logs=logs,
        username_filter=username_filter,
        action_filter=action_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page  # Передаем, чтобы сохранить в шаблоне
    )

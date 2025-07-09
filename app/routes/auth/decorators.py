from functools import wraps
from flask import abort
from flask_login import current_user
from flask import has_request_context

def roles_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Если нет активного запроса — считаем, что доступа нет
            if not has_request_context():
                abort(403)

            # Если current_user не определён или не авторизован
            if not current_user or not current_user.is_authenticated:
                abort(403)

            if not current_user.roles:
                return "Роль пользователя не назначена"

            user_role_names = [role.name for role in current_user.roles]
            if not any(role in user_role_names for role in allowed_roles):
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator

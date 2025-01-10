from flask import abort
from flask_login import current_user
from functools import wraps

def role_required(role_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.role:
                return "Роль пользователя не назначена"
            if not current_user.is_authenticated or current_user.role.name != role_name:
                abort(403)  # Доступ запрещен
            return f(*args, **kwargs)
        return decorated_function
    return decorator



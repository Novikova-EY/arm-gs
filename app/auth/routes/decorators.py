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

            # Если current_user не определен или не авторизован
            if not current_user or not current_user.is_authenticated:
                abort(403)

            if not current_user.roles:
                abort(403)

            user_role_names = [role.name for role in current_user.roles]
            if not any(role in user_role_names for role in allowed_roles):
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def has_admin_required(f):
    """Доступ только для пользователей, у которых в роли есть слово 'admin' (admin, generation-admin и т.д.)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not has_request_context():
            abort(403)
        if not current_user or not current_user.is_authenticated:
            abort(403)
        if not getattr(current_user, "has_admin", False):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

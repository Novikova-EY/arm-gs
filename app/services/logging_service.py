from app import db
from app.models.logs_models import Log


def log_to_db(username, action, details=None):
    """
    Записывает лог действия пользователя в базу данных.

    :param username: имя пользователя
    :param action: краткое описание действия
    :param details: дополнительные детали (опционально)
    """
    try:
        log_entry = Log(username=username, action=action, details=details)
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        print(f"Ошибка записи лога: {e}")
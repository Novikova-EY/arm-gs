from app import db
from app.models.logs_models import Log
from datetime import datetime


def log_to_db(username, action, details=None):
    max_action_len = 255
    action = action[:max_action_len]

    log = Log(timestamp=datetime.now(), username=username, action=action, details=details)
    try:
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Ошибка записи лога:", e)
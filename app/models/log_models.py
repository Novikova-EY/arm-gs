from app import db
from datetime import datetime

# Модель хранения логов
class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    username = db.Column(db.String(100), nullable=False)
    action = db.Column(db.String(500), nullable=False)
    details = db.Column(db.Text, nullable=True)
from app.extensions import db
from datetime import datetime
from config import SCHEMA_LOGS

# Модель хранения логов
class Log(db.Model):
    __tablename__ = 'logs'
    __table_args__ = {"schema": SCHEMA_LOGS}
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    username = db.Column(db.String(100), nullable=False)
    action = db.Column(db.String(500), nullable=False)
    details = db.Column(db.Text, nullable=True)
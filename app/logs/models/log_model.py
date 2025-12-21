# -*- coding: utf-8 -*-
"""
Log model (Аудит действий).
- Хранит событие, пользователя и произвольные детали.
- Таймстемп задается на стороне БД (UTC) через func.now().
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_LOGS, SCHEMA_REFDATA

class Log(db.Model):
    __tablename__ = 'logs'
    __table_args__ = {"schema": SCHEMA_LOGS}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Время события
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Идентификатор пользователя (логин/почта) на момент события
    username = db.Column(db.String(100), nullable=False, index=True)

    # Краткое действие + детали (опционально)
    action = db.Column(db.String(500), nullable=False, index=True)
    details = db.Column(db.Text, nullable=True)

    # Привязка к сущности (например, entity_type='station', entity_id=123)
    entity_type = db.Column(db.String(50), nullable=True, index=True)
    entity_id = db.Column(db.Integer, nullable=True, index=True)

    # Версия базы данных на момент создания записи
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    def __repr__(self) -> str:
        return f"<Log id={self.id} ts={self.timestamp} user={self.username!r} action={self.action!r}>"

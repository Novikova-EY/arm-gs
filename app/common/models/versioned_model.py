# -*- coding: utf-8 -*-
"""
Миксин для добавления версионирования к моделям.
Обеспечивает оптимистическую блокировку для предотвращения конфликтов
при параллельной работе нескольких пользователей с одной сущностью.
"""
from sqlalchemy import Column, Integer
from sqlalchemy.orm import validates
from sqlalchemy.orm.exc import StaleDataError
from flask import flash


class VersionedModelMixin:
    """
    Миксин для добавления версионирования к моделям.
    
    Использование:
        class MyModel(db.Model, VersionedModelMixin):
            __tablename__ = 'my_table'
            id = db.Column(db.Integer, primary_key=True)
            ...
    
    Версионирование работает автоматически при использовании session.commit().
    При возникновении конфликта (concurrent update) будет выброшено исключение StaleDataError.
    """
    
    # Номер версии записи (инкрементируется при каждом обновлении)
    version = Column(Integer, nullable=False, default=1, server_default='1')
    
    __mapper_args__ = {
        "version_id_col": version,
    }
    
    @validates('version')
    def validate_version(self, key, value):
        """Валидация версии."""
        if value is None:
            return 1
        return value


class ConcurrentUpdateError(Exception):
    """
    Исключение, которое выбрасывается при обнаружении конфликта 
    параллельного обновления данных.
    """
    def __init__(self, message="Данные были изменены другим пользователем. Пожалуйста, обновите страницу и попробуйте снова."):
        self.message = message
        super().__init__(self.message)


def handle_concurrent_update(func):
    """
    Декоратор для обработки ошибок параллельного обновления.
    
    Использование:
        @handle_concurrent_update
        def update_station(station_id, data):
            station = Station.query.get(station_id)
            station.name = data['name']
            db.session.commit()
    """
    from functools import wraps
    from app.extensions import db
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except StaleDataError:
            db.session.rollback()
            flash("Данные были изменены другим пользователем. Пожалуйста, обновите страницу и попробуйте снова.", "warning")
            raise ConcurrentUpdateError()
        except Exception as e:
            db.session.rollback()
            raise e
    
    return wrapper


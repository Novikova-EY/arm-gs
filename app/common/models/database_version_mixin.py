# -*- coding: utf-8 -*-
"""
Миксин для добавления поля database_version_id к моделям.
Используется для связи данных с конкретной версией базы данных.
"""
from sqlalchemy import Column, Integer, ForeignKey
from config import SCHEMA_REFDATA


class DatabaseVersionMixin:
    """
    Миксин для добавления поля database_version_id к моделям.
    
    Использование:
        class MyModel(db.Model, DatabaseVersionMixin):
            __tablename__ = 'my_table'
            id = db.Column(db.Integer, primary_key=True)
            ...
    
    После добавления миксина данные будут автоматически связаны
    с текущей активной версией БД при создании новых записей.
    """
    
    # Поле для связи с версией БД
    database_version_id = Column(
        Integer,
        ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )



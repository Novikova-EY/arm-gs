# -*- coding: utf-8 -*-
"""
Association table: User <-> Role (многие-ко-многим).
- Таблица в схеме AUTH, составной первичный ключ исключает дубли.
"""
from app.extensions import db
from config import SCHEMA_AUTH

user_roles = db.Table(
    'user_roles',
    db.Column('user_id', db.Integer,
              db.ForeignKey(f'{SCHEMA_AUTH}.users.id', ondelete='CASCADE'),  # удаление пользователя чистит связи
              primary_key=True),
    db.Column('role_id', db.Integer,
              db.ForeignKey(f'{SCHEMA_AUTH}.roles.id', ondelete='RESTRICT'),
              primary_key=True),
    schema=SCHEMA_AUTH
)

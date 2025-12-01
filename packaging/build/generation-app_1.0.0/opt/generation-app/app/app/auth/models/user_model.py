# -*- coding: utf-8 -*-
"""
User model (Пользователь системы).
- Таймстемпы на стороне БД (UTC) через func.now().
- M2M с Role через таблицу user_roles.
- Пароли храним только в виде хэша.
"""
from sqlalchemy.sql import func
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from config import SCHEMA_AUTH
from app.auth.models.user_role_model import user_roles

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    __table_args__ = {"schema": SCHEMA_AUTH}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(150), nullable=False, index=True)  # уникальность не навязываем, но индексируем
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)

    # Таймстемпы базы (UTC)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # M2M: User <-> Role
    roles = db.relationship('Role', secondary=user_roles, back_populates='users', lazy='selectin')

    # --- Вспомогательные методы ---
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} email={self.email!r}>"
    
    @property
    def role_names(self):
        return [role.name for role in self.roles]

    @property
    def is_admin(self):
        if not self.roles:
            return False
        for role in self.roles:
            # на всякий случай уберем случайные пробелы в БД
            if (role.name or '').strip() == 'admin':
                return True
        return False

    @property
    def has_admin(self):
        return any('admin' in (getattr(r, 'name', '') or getattr(r, 'code', '')) for r in self.roles)
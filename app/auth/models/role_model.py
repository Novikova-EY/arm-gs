# -*- coding: utf-8 -*-
"""
Role model (Роль пользователя).
- M2M с User через таблицу user_roles.
- Таймстемпы на стороне БД (UTC).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_AUTH
from app.auth.models.user_role_model import user_roles
from app.common.models.audit_mixin import AuditMixin

class Role(db.Model, AuditMixin):
    __tablename__ = 'roles'
    __table_args__ = {"schema": SCHEMA_AUTH}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name_full = db.Column(db.String(50), unique=True, nullable=False, index=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # обратная сторона M2M
    users = db.relationship('User', secondary=user_roles, back_populates='roles')

    def __repr__(self) -> str:
        return f"<Role id={self.id} name={self.name!r}>"

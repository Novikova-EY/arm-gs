# -*- coding: utf-8 -*-
"""
Database Version model (Версия базы данных).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_GENERATION

class DatabaseVersion(db.Model):
    __tablename__ = 'database_versions'
    __table_args__ = {"schema": SCHEMA_GENERATION}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    version_number = db.Column(db.Integer, unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=False, nullable=False, index=True)
    
    # Родительская версия (на основе какой версии создана)
    parent_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Для хранения снимка в виде файла (опционально)
    snapshot_path = db.Column(db.String(500), nullable=True)
    snapshot_size = db.Column(db.BigInteger, nullable=True)  # Размер в байтах
    
    # Отношения
    parent_version = db.relationship(
        'DatabaseVersion',
        remote_side=[id],
        backref=db.backref('child_versions', lazy='dynamic'),
        foreign_keys=[parent_version_id]
    )

    def __repr__(self) -> str:
        return f"<DatabaseVersion id={self.id} version_number={self.version_number} name={self.name!r} is_active={self.is_active}>"



# -*- coding: utf-8 -*-
"""
Document model (Номативный документ).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_GENERATION

class Document(db.Model):
    __tablename__ = 'documents_kommod'
    __table_args__ = {"schema": SCHEMA_GENERATION}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # Уникальность обеспечивается constraint documents_kommod_name_version_key (name, database_version_id)
    name = db.Column(db.String(255), nullable=False, index=True)

    # Поля для хранения файла
    file_path = db.Column(db.String(500), nullable=True)  # Путь к файлу в файловой системе
    file_name = db.Column(db.String(255), nullable=True)  # Оригинальное имя файла
    file_size = db.Column(db.Integer, nullable=True)      # Размер файла в байтах
    file_type = db.Column(db.String(100), nullable=True)  # MIME тип файла
    uploaded_at = db.Column(db.DateTime(timezone=True), nullable=True)  # Дата загрузки файла

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    @property
    def has_file(self):
        """Проверяет, есть ли загруженный файл."""
        return bool(self.file_path and self.file_name)

    @property
    def file_size_mb(self):
        """Возвращает размер файла в МБ."""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return 0

    def __repr__(self) -> str:
        return f"<Document id={self.id} name={self.name!r}>"


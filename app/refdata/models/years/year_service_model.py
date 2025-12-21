# -*- coding: utf-8 -*-
"""
YearService model (Сервис управления годами СиПР).
"""

from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin


class YearService(db.Model, AuditMixin, VersionedModelMixin):
    __tablename__ = 'gs_year_service'
    __table_args__ = {
        "schema": SCHEMA_REFDATA,
        "extend_existing": True
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # Годы СиПР
    year_sipr_start = db.Column(db.Integer, nullable=True)  # Год начала СиПР
    year_sipr_end = db.Column(db.Integer, nullable=True)    # Год конца СиПР
    
    # Даты СиПР
    date_sipr_start = db.Column(db.Date, nullable=True)  # Дата начала СиПР
    date_sipr_end = db.Column(db.Date, nullable=True)    # Дата конца СиПР
    
    # Аудит
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # FK -> DatabaseVersion
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Связь с версией БД
    database_version = db.relationship('DatabaseVersion', backref='year_services')

    def __repr__(self) -> str:
        return f"<YearService id={self.id} year_sipr_start={self.year_sipr_start} year_sipr_end={self.year_sipr_end} database_version_id={self.database_version_id}>"


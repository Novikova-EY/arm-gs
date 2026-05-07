# -*- coding: utf-8 -*-
"""
GenCompany model (Генерирующая компания).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA, SCHEMA_GENERATION
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin
from app.refdata.models.refdata_uuid_mixin import RefdataUuidMixin


class GenCompany(db.Model, AuditMixin, VersionedModelMixin, RefdataUuidMixin):
    __tablename__ = 'gs_sys_companies'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name_short = db.Column(db.String(80), unique=False, nullable=True, index=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # связь с таблицей "Агрегаты  электростанции"
    machines = db.relationship('Machine', back_populates='gen_company')

    def __repr__(self) -> str:
        return f"<GenCompany id={self.id} name={self.name!r}>"

# -*- coding: utf-8 -*-
"""
TechnologyAvailability model (Доступность технологии).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA, SCHEMA_GENERATION
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin
from app.refdata.models.refdata_uuid_mixin import RefdataUuidMixin


class TechnologyAvailability(db.Model, AuditMixin, VersionedModelMixin, RefdataUuidMixin):
    __tablename__ = 'gs_technology_availabilities'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # Сохраняем исходную nullable=True, чтобы не трогать существующие данные.
    name = db.Column(db.String(80), unique=True, nullable=True, index=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    equipment_groups = db.relationship('EquipmentGroup', back_populates='technology_availability')
    machines = db.relationship('Machine', back_populates='technology_availability')

    def __repr__(self) -> str:
        return f"<TechnologyAvailability id={self.id} name={self.name!r}>"

# -*- coding: utf-8 -*-
"""
FuelType model (Тип топлива).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA, SCHEMA_GENERATION
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin
from app.refdata.models.refdata_uuid_mixin import RefdataUuidMixin


class FuelType(db.Model, AuditMixin, VersionedModelMixin, RefdataUuidMixin):
    __tablename__ = 'gs_fuel_types'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # Порядок отображения в справочнике
    display_order = db.Column(db.Integer, nullable=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)

    # Название типа топлива из базы Топливо
    topl_nazvl = db.Column(db.String(80), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # связь с таблицей "Виды топлива"
    fuels = db.relationship('Fuel', back_populates='fuel_type')

    def __repr__(self) -> str:
        return f"<FuelType id={self.id} name={self.name!r}>"

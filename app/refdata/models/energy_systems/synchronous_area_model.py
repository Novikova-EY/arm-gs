# -*- coding: utf-8 -*-
"""
SynchronousArea model (Синхронная зона).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA, SCHEMA_GENERATION
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin
from app.refdata.models.refdata_uuid_mixin import RefdataUuidMixin


class SynchronousArea(db.Model, AuditMixin, VersionedModelMixin, RefdataUuidMixin):
    __tablename__ = 'gs_sys_synchronous_areas'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # Порядок отображения в справочнике
    display_order = db.Column(db.Integer, nullable=True)
    number = db.Column(db.String(256), unique=True, nullable=True, index=True)
    name = db.Column(db.String(256), unique=True, nullable=False, index=True)
    name_full = db.Column(db.String(256), nullable=True, index=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # связь с моделью RegionalDistrict
    regional_districts = db.relationship(
        'RegionalDistrict',
        back_populates='synchronous_area',
        foreign_keys='RegionalDistrict.id_synchronous_area',
    )

    demand_parameters = db.relationship(
        'SynchronousAreaDemandParameter',
        back_populates='synchronous_area',
        cascade='all, delete-orphan',
    )

    def __repr__(self) -> str:
        return f"<SynchronousArea id={self.id} number={self.number!r} name={self.name!r} name_full={self.name_full!r}>"

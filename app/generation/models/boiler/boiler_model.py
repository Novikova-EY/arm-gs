# -*- coding: utf-8 -*-
"""
Boiler model (Котел  электростанции).
- Связь: Boiler.boiler_station -> Station.boilers (back_populates).
- Таймстемпы на стороне БД (UTC) через func.now().
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin

class Boiler(db.Model, AuditMixin):
    __tablename__ = 'gs_gen_boilers'
    __table_args__ = {"schema": SCHEMA_GENERATION}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # Уникальность будет обеспечиваться через миграцию с database_version_id
    name = db.Column(db.String(80), nullable=False, index=True)

    # FK -> Station
    id_station = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_GENERATION}.gs_gen_stations.id', ondelete='RESTRICT'),
        nullable=True,
        index=True
    )
    boiler_station = db.relationship('Station', back_populates='boilers')

    # timestamps (UTC, server-side)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    def __repr__(self) -> str:
        return f"<Boiler id={self.id} name={self.name!r} station_id={self.id_station}>"

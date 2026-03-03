# -*- coding: utf-8 -*-
"""
StationPower model (Мощности электростанции).
- Связи сохранены: year (Year.station_powers), station_power (Station.station_powers).
"""
from sqlalchemy.sql import func
from sqlalchemy import Numeric
from sqlalchemy.schema import Index
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin

class StationPower(db.Model, AuditMixin):
    __tablename__ = 'station_powers'
    __table_args__ = (
        Index('ix_station_power_id_station', 'id_station'),
        Index('ix_station_power_year_number', 'year_number'),
        # Составной индекс для оптимизации запросов по станции и году
        Index('ix_station_powers_station_year', 'id_station', 'year_number'),
        {"schema": SCHEMA_GENERATION},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # FK -> Year (по полю years.number)
    year_number = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_years.number', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    year = db.relationship('Year', back_populates='station_powers')

    # FK -> Station
    id_station = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_GENERATION}.stations.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    station_power = db.relationship('Station', back_populates='station_powers')

    # Мощности (до 16 знаков после запятой для согласования с импортом Excel)
    p_ust = db.Column(Numeric(25, 16))
    p_ogr = db.Column(Numeric(25, 16))
    p_rasp = db.Column(Numeric(25, 16))

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
        return f"<StationPower id={self.id} station_id={self.id_station} year={self.year_number} p_ust={self.p_ust}>"

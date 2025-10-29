# -*- coding: utf-8 -*-
"""
Fuel model (Тип топлива).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA, SCHEMA_GENERATION

class Fuel(db.Model):
    __tablename__ = 'fuels'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)

    # FK -> FuelType
    id_fuel_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.fuel_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True
    )
    fuel_type = db.relationship('FuelType', back_populates='fuels')

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # связь с таблицей топлив агрегатов электростанции
    machine_fuels = db.relationship('MachineFuel', back_populates='fuel')

    def __repr__(self) -> str:
        return f"<Fuel id={self.id} name={self.name!r} type_id={self.id_fuel_type}>"

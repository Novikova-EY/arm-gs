# -*- coding: utf-8 -*-
"""
MachinePower model (Мощности агрегатов).
- Связи сохранены: year (Year.machine_powers), machine_power (Machine.machine_powers).
"""
from sqlalchemy.sql import func
from sqlalchemy import Numeric
from sqlalchemy.schema import Index
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA

class MachinePower(db.Model):
    __tablename__ = 'machine_powers'
    __table_args__ = (
        Index('ix_machine_power_id_machine', 'id_machine'),
        Index('ix_machine_power_year_number', 'year_number'),
        Index('ix_machine_powers_station_year', 'id_machine', 'year_number'),
        {"schema": SCHEMA_GENERATION},
    )
    __mapper_args__ = {"confirm_deleted_rows": False}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # FK -> Year (по полю years.number)
    year_number = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.years.number', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    year = db.relationship('Year', back_populates='machine_powers')

    # FK -> Machine
    id_machine = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_GENERATION}.machines.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    machine_power = db.relationship('Machine', back_populates='machine_powers')

    # Мощности
    p_ust = db.Column(Numeric(25, 15))
    p_ogr = db.Column(Numeric(25, 15))
    p_rasp = db.Column(Numeric(25, 15))

    # timestamps (UTC, server-side)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    def __repr__(self) -> str:
        return f"<MachinePower id={self.id} machine_id={self.id_machine} year={self.year_number} p_ust={self.p_ust}>"

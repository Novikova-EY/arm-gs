# -*- coding: utf-8 -*-
"""
MachineFuel model (Топливо агрегата).
- Связи сохранены: year (Year.machine_fuels), machine_fuel (Machine.machine_fuels), fuel (Fuel.machine_fuels).
"""
from sqlalchemy.sql import func
from sqlalchemy.schema import Index
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA

class MachineFuel(db.Model):
    __tablename__ = 'machine_fuels'
    __table_args__ = (
        Index('ix_machine_fuel_id_machine', 'id_machine'),
        Index('ix_machine_fuel_id_fuel', 'id_fuel'),
        Index('ix_machine_fuel_id_year_number', 'year_number'),
        Index('ix_machine_fuels_machine_year', 'id_machine', 'year_number'),
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
    year = db.relationship('Year', back_populates='machine_fuels')

    # FK -> Machine
    id_machine = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_GENERATION}.machines.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    machine_fuel = db.relationship('Machine', back_populates='machine_fuels')

    # FK -> Fuel
    id_fuel = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.fuels.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    fuel = db.relationship('Fuel', back_populates='machine_fuels')

    # timestamps (UTC, server-side)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<MachineFuel id={self.id} machine_id={self.id_machine} year={self.year_number} fuel_id={self.id_fuel}>"

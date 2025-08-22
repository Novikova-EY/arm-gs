# -*- coding: utf-8 -*-
"""
EnergyArea model (Энергорайон).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA

class EnergyArea(db.Model):
    __tablename__ = 'energy_areas'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(256), unique=True, nullable=False, index=True)

    # FK -> RegionalDistrict
    id_regional_district = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.regional_districts.id', ondelete='RESTRICT'),
        index=True,
        nullable=False
    )
    regional_district = db.relationship(
        'RegionalDistrict',
        back_populates='energy_areas'
    )

    # FK -> RegionalEnergySystem
    id_regional_energy_system = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.regional_energy_systems.id', ondelete='RESTRICT'),
        index=True,
        nullable=False
    )
    regional_energy_system = db.relationship(
        'RegionalEnergySystem',
        back_populates='energy_areas'
    )

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # связь с агрегатами (Machine)
    machines = db.relationship(
        'Machine',
        back_populates='energy_area'
    )

    @property
    def union_energy_system(self):
        if self.regional_energy_system and self.regional_energy_system.union_energy_system:
            return self.regional_energy_system.union_energy_system
        return None

    def __repr__(self) -> str:
        return f"<EnergyArea id={self.id} name={self.name!r}>"

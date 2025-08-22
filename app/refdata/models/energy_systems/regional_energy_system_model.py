# -*- coding: utf-8 -*-
"""
RegionalEnergySystem model (Региональная энергосистема).
- Имеет связь многие-к-одному с UnionEnergySystem.
- M2M с RegionalDistrict через региональный ассоциативный стол.
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA
from app.refdata.models.energy_systems.regional_district_regional_energy_system_model import regional_district_regional_energy_system

class RegionalEnergySystem(db.Model):
    __tablename__ = 'regional_energy_systems'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Короткое и полное наименование
    name = db.Column(db.String(255), nullable=False, index=True)
    name_full = db.Column(db.String(255), nullable=False)

    # FK -> UnionEnergySystem
    id_union_energy_system = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.union_energy_systems.id', ondelete='RESTRICT'),
        index=True,
        nullable=True
    )
    union_energy_system = db.relationship(
        'UnionEnergySystem',
        back_populates='regional_energy_systems'
    )

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # M2M: RegionalDistrict <-> RegionalEnergySystem
    regional_districts = db.relationship(
        'RegionalDistrict',
        secondary=regional_district_regional_energy_system,
        back_populates='regional_energy_systems'
    )

    # Children: EnergyUnit / EnergyArea
    energy_units = db.relationship(
        'EnergyUnit',
        back_populates='regional_energy_system',
        cascade='all, delete-orphan'
    )
    energy_areas = db.relationship(
        'EnergyArea',
        back_populates='regional_energy_system',
        cascade='all, delete-orphan'
    )

    @property
    def regional_district_count(self):
        return len(self.regional_districts)

    def __repr__(self) -> str:
        return f"<RegionalEnergySystem id={self.id} name={self.name!r}>"

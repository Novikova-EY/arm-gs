# -*- coding: utf-8 -*-
"""
EnergyUnit model (Энергоузел).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA, SCHEMA_GENERATION

class EnergyUnit(db.Model):
    __tablename__ = 'energy_units'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(256), nullable=False, index=True)

    # FK -> RegionalDistrict
    id_regional_district = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.regional_districts.id', ondelete='RESTRICT'),
        index=True,
        nullable=False
    )
    regional_district = db.relationship(
        'RegionalDistrict',
        back_populates='energy_units'
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
        back_populates='energy_units'
    )

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    __table_args__ = (
        db.UniqueConstraint('database_version_id', 'name', name='uq_refdata_energy_units_ver_name'),
        {"schema": SCHEMA_REFDATA},
    )

    # связь со станциями
    stations = db.relationship(
        'Station',
        back_populates='energy_unit'
    )

    @property
    def union_energy_system(self):
        if self.regional_energy_system and self.regional_energy_system.union_energy_system:
            return self.regional_energy_system.union_energy_system
        return None

    def __repr__(self) -> str:
        return f"<EnergyUnit id={self.id} name={self.name!r}>"

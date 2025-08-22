# -*- coding: utf-8 -*-
"""
Station model (Электростанция).
- Сохранены все исходные связи и индексы/уникальные ограничения.
- Добавлены серверные таймстемпы (UTC).
"""
from sqlalchemy.sql import func
from sqlalchemy.schema import UniqueConstraint, Index
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA

class Station(db.Model):
    __tablename__ = 'stations'
    __table_args__ = (
        UniqueConstraint('name', 'id_regional_district', name='uq_station_name_district'),
        Index('ix_station_id_regional_district', 'id_regional_district'),
        Index('ix_station_name', 'name'),
            Index('ix_station_id_station_group', 'id_station_group'),
        {"schema": SCHEMA_GENERATION},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # FK -> StationGroup
    id_station_group = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.station_groups.id", ondelete="RESTRICT"),
        nullable=True,
        index=True
    )
    group = db.relationship(
        "StationGroup",
        back_populates="stations",
        foreign_keys=[id_station_group]
    )

    # FK -> ConditionType
    id_condition_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.condition_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    condition_type = db.relationship('ConditionType', back_populates='stations')

    # Наименования
    name = db.Column(db.String(255), nullable=False)
    name_so = db.Column(db.String(80), unique=True, nullable=True)
    name_combined = db.Column(db.String(80), unique=True, nullable=True)
    name_archive = db.Column(db.String(80), unique=True, nullable=True)

    # FK -> RegionalDistrict
    id_regional_district = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.regional_districts.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    regional_district = db.relationship('RegionalDistrict', back_populates='stations')

    # FK -> EnergyUnit
    id_energy_unit = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.energy_units.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    energy_unit = db.relationship('EnergyUnit', back_populates='stations')

    # Children
    station_powers = db.relationship('StationPower', back_populates='station_power', cascade="all, delete-orphan")
    machines = db.relationship('Machine', back_populates='machine_station')
    boilers = db.relationship('Boiler', back_populates='boiler_station')

    # Прочее
    kto = db.Column(db.String(80), unique=True, nullable=True)
    location = db.Column(db.String(255), unique=True, nullable=True)
    note = db.Column(db.String(1000), nullable=True)

    # timestamps (UTC, server-side)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # ----- Aggregated helpers (не маппятся в БД) -----
    @property
    def regional_energy_system(self):
        if self.regional_district and self.regional_district.regional_energy_systems:
            return ", ".join(res.name for res in self.regional_district.regional_energy_systems)
        return None

    @property
    def union_energy_system(self):
        if self.regional_district and self.regional_district.regional_energy_systems:
            union_systems = {res.union_energy_system.name for res in self.regional_district.regional_energy_systems if res.union_energy_system}
            return ", ".join(union_systems) if union_systems else None
        return None

    @property
    def federal_district(self):
        return self.regional_district.federal_district.name if self.regional_district and self.regional_district.federal_district else None

    @property
    def energy_system_type(self):
        if self.regional_district and self.regional_district.regional_energy_systems:
            types = {res.union_energy_system.energy_system_type.name for res in self.regional_district.regional_energy_systems if res.union_energy_system and res.union_energy_system.energy_system_type}
            return ", ".join(types) if types else None
        return None

    @property
    def gen_companies(self):
        if not self.machines:
            return None
        gen_companies = {machine.gen_company.name for machine in self.machines if machine.gen_company}
        return ", ".join(gen_companies) if gen_companies else None

    @property
    def station_types(self):
        if not self.machines:
            return None

        types = {
            machine.station_type.name
            for machine in self.machines
            if machine.station_type and machine.station_type.id != 0
        }

        if not types:
            return "не указано"
        if len(types) == 1:
            return next(iter(types))
        return sorted(types)

    def __repr__(self) -> str:
        return f"<Station id={self.id} name={self.name!r}>"

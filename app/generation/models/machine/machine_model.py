# -*- coding: utf-8 -*-
"""
Machine model (Агрегат электростанции).
- Сохранены все исходные связи и индексы.
- Добавлены серверные таймстемпы (UTC).
"""
from sqlalchemy.sql import func
from sqlalchemy.schema import Index
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA

class Machine(db.Model):
    __tablename__ = 'machines'
    __table_args__ = (
        Index('ix_machine_id_station', 'id_station'),
        Index('ix_machine_id_condition_type', 'id_condition_type'),
        Index('ix_machine_id_tes_machine_type', 'id_tes_machine_type'),
        Index('ix_machine_id_station_type', 'id_station_type'),
        Index('ix_machine_id_equipment_group', 'id_equipment_group'),
        Index('ix_machine_id_gen_company', 'id_gen_company'),
        Index('ix_machine_id_energy_area', 'id_energy_area'),
        Index('ix_machine_date_exploitation', 'date_exploitation'),
        Index('ix_machine_date_decompressing_expected', 'date_decompressing_expected'),
        Index('ix_machine_date_modernization_expected', 'date_modernization_expected'),
        {"schema": SCHEMA_GENERATION},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_ti = db.Column(db.Integer, nullable=True)

    # FK -> ConditionType
    id_condition_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.condition_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    condition_type = db.relationship('ConditionType', back_populates='machines')

    # FK -> GenCompany
    id_gen_company = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gen_companies.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    gen_company = db.relationship('GenCompany', back_populates='machines')

    # FK -> Station
    id_station = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_GENERATION}.stations.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    machine_station = db.relationship('Station', back_populates='machines')

    # FK -> EnergyArea
    id_energy_area = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.energy_areas.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    energy_area = db.relationship('EnergyArea', back_populates='machines')

    # Основные атрибуты
    machine_number = db.Column(db.String(80), nullable=False, index=True)
    machine_name = db.Column(db.String(255), nullable=False, index=True)
    machine_group = db.Column(db.String(255), nullable=True)
    fuel_so = db.Column(db.String(255), nullable=True)

    # FK -> StationType
    id_station_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.station_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    station_type = db.relationship('StationType', back_populates='machines')

    # FK -> MachineType
    id_machine_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.machine_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    machine_type = db.relationship('MachineType', back_populates='machines')

    # FK -> TesMachineType
    id_tes_machine_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.tes_machine_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    tes_machine_type = db.relationship('TesMachineType', back_populates='machines')

    # FK -> TechnologyAvailability  
    id_technology_availability = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.technology_availabilities.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    technology_availability = db.relationship('TechnologyAvailability', back_populates='machines')

    # FK -> TechnologyType 
    id_technology_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.technology_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    technology_type = db.relationship('TechnologyType', back_populates='machines')

    # FK -> EquipmentGroup
    id_equipment_group = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.equipment_groups.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    equipment_group = db.relationship('EquipmentGroup', back_populates='machines')

    # Children: powers / fuels / tes_types
    machine_powers = db.relationship(
        'MachinePower',
        back_populates='machine_power',
        cascade="all, delete-orphan",
        foreign_keys='MachinePower.id_machine',
    )
    machine_fuels = db.relationship(
        'MachineFuel',
        back_populates='machine_fuel',
        cascade="all, delete-orphan",
        foreign_keys='MachineFuel.id_machine',
    )
    machine_tes_types = db.relationship(
        'MachineTesType',
        back_populates='machine_tes_type',
        cascade="all, delete-orphan",
        foreign_keys='MachineTesType.id_machine',
    )

    # Даты/годы (оставлены типы как в исходнике)
    date_exploitation = db.Column(db.Integer, nullable=True)
    date_commission_fact = db.Column(db.String(10), nullable=True)
    date_joining_expected = db.Column(db.String(10), nullable=True)
    date_joining_fact = db.Column(db.String(10), nullable=True)
    date_detatchment_fact = db.Column(db.String(10), nullable=True)
    date_decompressing_expected = db.Column(db.Integer, nullable=True)
    date_decompressing_fact = db.Column(db.String(10), nullable=True)
    date_modernization_expected = db.Column(db.Integer, nullable=True)
    date_relabing_fact = db.Column(db.String(10), nullable=True)
    date_update_fact = db.Column(db.String(10), nullable=True)
    note = db.Column(db.String(512), nullable=True)
    year_modern = db.Column(db.String(10), nullable=True)
    year_demontaz = db.Column(db.String(10), nullable=True)
    resurs_coal = db.Column(db.String(10), nullable=True)
    resurs_gas = db.Column(db.String(10), nullable=True)

    # timestamps (UTC, server-side)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # ----- Runtime helpers (не маппятся в БД) -----
    @property
    def group_rowspan(self):
        return getattr(self, "_group_rowspan", None)

    @group_rowspan.setter
    def group_rowspan(self, value):
        self._group_rowspan = value

    @property
    def fuel_rowspan(self):
        return getattr(self, "_fuel_rowspan", None)

    @fuel_rowspan.setter
    def fuel_rowspan(self, value):
        self._fuel_rowspan = value

    @property
    def tes_types(self):
        tes_type_names = {
            mtt.tes_type.name
            for mtt in self.machine_tes_types
            if mtt.tes_type and mtt.tes_type.name and mtt.tes_type.name.lower() != "не указано"
        }
        return ", ".join(sorted(tes_type_names)) if tes_type_names else None

    @property
    def primary_fuel_type(self):
        fuel_names = {
            mf.fuel.fuel_type.name
            for mf in self.machine_fuels
            if mf.fuel and mf.fuel.fuel_type and mf.fuel.fuel_type.name.lower() != "не указано"
        }
        return ", ".join(sorted(fuel_names)) if fuel_names else None

    def __repr__(self) -> str:
        return f"<Machine id={self.id} name={self.machine_name!r} station_id={self.id_station}>"

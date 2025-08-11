from app.extensions import db
from sqlalchemy.schema import UniqueConstraint, Index
from sqlalchemy import Numeric
from config import SCHEMA_GENERATION, SCHEMA_REFDATA


# Модель для групп станций
class StationGroup(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'station_groups'
    __table_args__ = {"schema": SCHEMA_GENERATION}
    
    # id группы электрстанций
    id = db.Column(db.Integer, primary_key=True)

    # наименование группы электрстанций
    name = db.Column(db.String(80), unique=True, nullable=False)

    # привязка к таблице "Электростанции"
    stations = db.relationship(
        'Station', 
        back_populates='group')


# Модель электростанций
class Station(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'stations'
    __table_args__ = (
        UniqueConstraint('name', 'id_regional_district', name='uq_station_name_district'),
        Index('ix_station_id_regional_district', 'id_regional_district'),
        Index('ix_station_name', 'name'),
        {"schema": SCHEMA_GENERATION},
    )
    
    # id электростанции
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # id состояния станции (действуйщий, планируемый, ...)
    id_condition_type = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_REFDATA}.condition_types.id', ondelete='RESTRICT'), 
        nullable=True)
    condition_type = db.relationship(
        'ConditionType', 
        back_populates='stations')   

    # наименование диспетчерское (основное)
    name = db.Column(db.String(255), nullable=False)
    
    # наименование от СО ЕЭС (оперативная информация)
    name_so = db.Column(db.String(80), unique=True, nullable=True)
    
    # наименование совмещенное (Гурьева А)
    name_combined = db.Column(db.String(80), unique=True, nullable=True)
    
    # архивные наименования    
    name_archive = db.Column(db.String(80), unique=True, nullable=True)

    # id субъекта РФ
    id_regional_district = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_REFDATA}.regional_districts.id', ondelete='RESTRICT'), 
        nullable=True)
    regional_district = db.relationship(
        'RegionalDistrict', 
        back_populates='stations')
    
    # id энергоузла (связь с таблицей "Энергоузлы")
    id_energy_unit = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.energy_units.id', ondelete='RESTRICT'),
        nullable=True
    )
    energy_unit = db.relationship(
        'EnergyUnit', 
        back_populates='stations')
    
    # связь с таблицей мощностей агрегатов электростанции
    station_powers = db.relationship(
        'StationPower', 
        back_populates='station_power',
        cascade="all, delete-orphan"
    )   

    # номер КТО
    kto = db.Column(db.String(80), unique=True, nullable=True)
    
    # местоположение
    location = db.Column(db.String(255), unique=True, nullable=True)
    
    # id группы электростанций
    id_group = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_GENERATION}.station_groups.id', ondelete='RESTRICT'), 
        nullable=True)
    group = db.relationship(
        'StationGroup', 
        back_populates='stations')
    
    # связь с таблицей "Агрегаты электростанции"
    machines = db.relationship('Machine', back_populates='machine_station')
    
    # связь с таблицей "Котлогрегаты электростанции"
    boilers = db.relationship('Boiler', back_populates='boiler_station')
    
    # примечание
    note = db.Column(db.String(1000), unique=False, nullable=True)

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
            if machine.station_type and machine.station_type.id != 100
        }

        if not types:
            return "не указано"
        if len(types) == 1:
            return next(iter(types))
        return sorted(types)


# Модель мощностей агрегатов электростанции
class StationPower(db.Model):
    __tablename__ = 'station_powers'
    __table_args__ = (
        Index('ix_station_power_id_station', 'id_station'),
        Index('ix_station_power_year_number', 'year_number'),
        {"schema": SCHEMA_GENERATION},
    )
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # id года
    year_number = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_REFDATA}.years.number', ondelete='RESTRICT'),
        nullable=True
    )
    year = db.relationship(
        'Year', 
        back_populates='station_powers'
    )

    # id электростанции
    id_station = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_GENERATION}.stations.id', ondelete='RESTRICT'), nullable=True)
    station_power = db.relationship(
        'Station', 
        back_populates='station_powers')

    # Установленная мощность электростанции
    p_ust = db.Column(Numeric(25, 15))

    # Ограничения установленной мощности электростанции
    p_ogr = db.Column(Numeric(25, 15))
    
    # Располагаемая мощность электростанции
    p_rasp = db.Column(Numeric(25, 15))
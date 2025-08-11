from app.extensions import db
from sqlalchemy.schema import UniqueConstraint, Index
from sqlalchemy import Numeric
from config import SCHEMA_GENERATION, SCHEMA_REFDATA


# Модель для агрегата электростанции
class Machine(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'machines'
    __table_args__ = (
        Index('ix_machine_id_station', 'id_station'),
        Index('ix_machine_id_condition_type', 'id_condition_type'),
        Index('ix_machine_id_tes_machine_type', 'id_tes_machine_type'),
        Index('ix_machine_id_station_type', 'id_station_type'),
        Index('ix_machine_date_exploitation', 'date_exploitation'),
        Index('ix_machine_date_decompressing_expected', 'date_decompressing_expected'),
        Index('ix_machine_date_modernization_expected', 'date_modernization_expected'),
        {"schema": SCHEMA_GENERATION},
    )
    
    # id агрегата
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # id агрегата от Техинспекции
    id_ti = db.Column(db.Integer, nullable=True)

    # id группы оборудования
    id_equipment_group = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_REFDATA}.equipment_groups.id', ondelete='RESTRICT'), 
        nullable=True)
    equipment_group = db.relationship(
        'EquipmentGroup', 
        back_populates='machines')

    # id состояние агрегата
    id_condition_type = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_REFDATA}.condition_types.id', ondelete='RESTRICT'), 
        nullable=True)
    condition_type = db.relationship(
        'ConditionType', 
        back_populates='machines')

    # id генерирующей компании
    id_gen_company = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_REFDATA}.gen_companies.id', ondelete='RESTRICT'), 
        nullable=True)
    gen_company = db.relationship(
        'GenCompany', 
        back_populates='machines')
    
    # id электростанции
    id_station = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_GENERATION}.stations.id', ondelete='RESTRICT'), nullable=True)
    machine_station = db.relationship(
        'Station', 
        back_populates='machines')

    # id энергорайона (связь с таблицей "Энергорайоны")
    id_energy_area = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_REFDATA}.energy_areas.id', ondelete='RESTRICT'), 
        nullable=True)
    energy_area = db.relationship(
        'EnergyArea', 
        back_populates='machines')

    # номер агрегата
    machine_number = db.Column(db.String(80), nullable=False)

    # название агрегата
    machine_name = db.Column(db.String(255), nullable=False)

    # номер/название группы агрегата
    machine_group = db.Column(db.String(255), nullable=True)

    # название агрегата
    fuel_so = db.Column(db.String(255), nullable=True)

    # id типа электростанции (АЭС, ТЭС, ...)
    id_station_type = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_REFDATA}.station_types.id', ondelete='RESTRICT'), 
        nullable=True)
    station_type = db.relationship(
        'StationType', 
        back_populates='machines')

    # id типа агрегата
    id_machine_type = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_REFDATA}.machine_types.id', ondelete='RESTRICT'), 
        nullable=True)
    type = db.relationship(
        'MachineType', 
        back_populates='machines')    
            
    # id типа машины ТЭС
    id_tes_machine_type = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_REFDATA}.tes_machine_types.id', ondelete='RESTRICT'), 
        nullable=True
    )
    tes_machine_type = db.relationship(
        'TesMachineType', 
        back_populates='machines'
    )
    
    # связь с таблицей мощностей агрегатов электростанции
    machine_powers = db.relationship(
        'MachinePower', 
        back_populates='machine_power',
        cascade="all, delete-orphan",
        foreign_keys='MachinePower.id_machine',
    )   

    # связь с таблицей топлив агрегатов электростанции
    machine_fuels = db.relationship(
        'MachineFuel', 
        back_populates='machine_fuel',
        cascade="all, delete-orphan",
        foreign_keys='MachineFuel.id_machine',
    )  

    # связь с таблицей типов ТЭС агрегатов электростанции
    machine_tes_types = db.relationship(
        'MachineTesType', 
        back_populates='machine_tes_type',
        cascade="all, delete-orphan",
        foreign_keys='MachineTesType.id_machine',
    )  

    # год ввода в эксплуатацию
    date_exploitation = db.Column(db.Integer, nullable=True)

    # фактическая дата ввода в работу
    date_commission_fact = db.Column(db.String(10), nullable=True)

    # ожидаемая дата присоединения
    date_joining_expected = db.Column(db.String(10), nullable=True)

    # фактическая дата присоединения
    date_joining_fact = db.Column(db.String(10), nullable=True)

    # фактическая дата отсоединения
    date_detatchment_fact = db.Column(db.String(10), nullable=True)

    # ожидаемый год вывода из эксплуатации
    date_decompressing_expected = db.Column(db.Integer, nullable=True)

    # фактическая дата вывода из эксплуатации
    date_decompressing_fact = db.Column(db.String(10), nullable=True)

    # ожидаемый год модернизации
    date_modernization_expected = db.Column(db.Integer, nullable=True)

    # фактическая дата перемаркировки
    date_relabing_fact = db.Column(db.String(10), nullable=True)

    # фактическая дата уточнения
    date_update_fact = db.Column(db.String(10), nullable=True)
    
    # примечание
    note = db.Column(db.String(512), unique=False, nullable=True)

    # ожидаемый год модернизации по ТИ
    year_modern = db.Column(db.String(10), nullable=True)

    # ожидаемый год вывода из эксплуатации по ТИ
    year_demontaz = db.Column(db.String(10), nullable=True)

    # отметка о превышении двух ресурсов угольных машин по ТИ
    resurs_coal = db.Column(db.String(10), nullable=True)

    # отметка о превышении двух ресурсов газовых машин по ТИ
    resurs_gas = db.Column(db.String(10), nullable=True)


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


# Модель мощностей агрегатов электростанции
class MachinePower(db.Model):
    __tablename__ = 'machine_powers'
    __table_args__ = (
        Index('ix_machine_power_id_machine', 'id_machine'),
        Index('ix_machine_power_year_number', 'year_number'),
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
        back_populates='machine_powers'
    )

    # id агрегата электростанции
    id_machine = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_GENERATION}.machines.id', ondelete='RESTRICT'), nullable=True)
    machine_power = db.relationship(
        'Machine', 
        back_populates='machine_powers')

    # Установленная мощность агрегата
    p_ust = db.Column(Numeric(25, 15))

    # Ограничения установленной мощности агрегата
    p_ogr = db.Column(Numeric(25, 15))   
    
    # Располагаемая мощность агрегата
    p_rasp = db.Column(Numeric(25, 15))


# Модель для топлива агрегатов электростанции
class MachineFuel(db.Model):
    __tablename__ = 'machine_fuels'
    __table_args__ = (
        Index('ix_machine_fuel_id_machine', 'id_machine'),
        Index('ix_machine_fuel_id_fuel', 'id_fuel'),
        Index('ix_machine_fuel_id_year_number', 'year_number'),
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
        back_populates='machine_fuels'
    )

    # id агрегата электростанции
    id_machine = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_GENERATION}.machines.id', ondelete='RESTRICT'), nullable=True)
    machine_fuel = db.relationship(
        'Machine', 
        back_populates='machine_fuels')

    # Используемое топливо
    id_fuel = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_REFDATA}.fuels.id', ondelete='RESTRICT'),
        nullable=True)
    fuel = db.relationship(
        'Fuel', 
        back_populates='machine_fuels')


# Модель для типов ТЭС агрегатов электростанции
class MachineTesType(db.Model):
    __tablename__ = 'machine_tes_types'
    __table_args__ = (
        Index('ix_machine_tes_type_id_machine', 'id_machine'),
        Index('ix_machine_tes_type_id_tes_type', 'id_tes_type'),
        Index('ix_machine_tes_type_year_number', 'year_number'),
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
        back_populates='machine_tes_types'
    )

    # id агрегата электростанции
    id_machine = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_GENERATION}.machines.id', ondelete='RESTRICT'), nullable=True)
    machine_tes_type = db.relationship(
        'Machine', 
        back_populates='machine_tes_types')

    # Тип ТЭС
    id_tes_type = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_REFDATA}.tes_types.id', ondelete='RESTRICT'),
        nullable=True)
    tes_type = db.relationship(
        'TesType', 
        back_populates='machine_tes_types') 
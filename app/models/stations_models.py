from app import db

# Модель для типов состояний оборудования или электростанций
class ConditionType(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'condition_types'

    # id типа тип состояния
    id = db.Column(db.Integer, primary_key=True)

    # наименование типа состояния
    name = db.Column(db.String(80), unique=True, nullable=False)


    # связь с таблицей "Электростанции"
    stations = db.relationship(
        'Station', 
        back_populates='condition_type',
        primaryjoin="ConditionType.id == Station.id_condition_type"
    )

    # связь с таблицей "Агрегаты электростанции"
    machines = db.relationship(
        'Machine', 
        back_populates='condition_type',
        primaryjoin="ConditionType.id == Machine.id_condition_type"
    )
    
# Модель для типов электростанций
class StationType(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'station_types'

    # id типа электрстанции
    id = db.Column(db.Integer, primary_key=True)
    
    # наименование типа электрстанции
    name = db.Column(db.String(255), unique=True, nullable=False)
    
    # привязка к таблице "Агрегаты электростанции"
    machines = db.relationship(
        'Machine', 
        back_populates='station_type')


# Модель для типов ТЭС
class TesType(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'tes_types'

    # id типа ТЭС
    id = db.Column(db.Integer, primary_key=True)
    
    # наименование типа ТЭС
    name = db.Column(db.String(80), unique=True, nullable=False)

    # связь с таблицей "Агрегат электростанции"
    machines = db.relationship(
        'Machine', 
        back_populates='tes_type',
        cascade="all, delete-orphan"
    )

    # связь с таблицей "связь типа ТЭС и года"
    machine_tes_types = db.relationship(
        'MachineTesType', 
        back_populates='tes_type', 
        cascade="all, delete-orphan"
    )
    

# Модель для групп станций
class StationGroup(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'station_groups'
    
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
    
    # id электростанции
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # id состояния станции (действуйщий, планируемый, ...)
    id_condition_type = db.Column(
        db.Integer, 
        db.ForeignKey('condition_types.id', ondelete='RESTRICT'), 
        nullable=True)
    condition_type = db.relationship(
        'ConditionType', 
        back_populates='stations')   

    # наименование диспетчерское (основное)
    name = db.Column(db.String(255), unique=True, nullable=False, index=True)
    
    # наименование собственника
    name_owner = db.Column(db.String(80), unique=True, nullable=True)
    
    # наименование совмещенное
    name_compined = db.Column(db.String(80), unique=True, nullable=True)
    
    # наименование дополнительное    
    name_additional = db.Column(db.String(80), unique=True, nullable=True)

    # id субъекта РФ
    id_regional_district = db.Column(
        db.Integer, 
        db.ForeignKey('regional_districts.id', ondelete='RESTRICT'), 
        nullable=True)
    regional_district = db.relationship(
        'RegionalDistrict', 
        back_populates='stations')
    
    # номер КТО
    kto = db.Column(db.String(80), unique=True, nullable=True)
    
    # местоположение
    location = db.Column(db.String(255), unique=True, nullable=True)
    
    # id группы электростанций
    id_group = db.Column(
        db.Integer, 
        db.ForeignKey('station_groups.id', ondelete='RESTRICT'), 
        nullable=True)
    group = db.relationship(
        'StationGroup', 
        back_populates='stations')
    
    # связь с таблицей "Агрегаты электростанции"
    machines = db.relationship('Machine', back_populates='machine_station')
    
    # связь с таблицей "Котлогрегаты электростанции"
    boilers = db.relationship('Boiler', back_populates='boiler_station')
    
    # примечание
    note = db.Column(db.String(80), unique=False, nullable=True)

    @property
    def gen_companies(self):
        if not self.machines:
            return None
        gen_companies = {machine.gen_company.name for machine in self.machines if machine.gen_company}
        return ", ".join(gen_companies) if gen_companies else None
    
    @property
    def station_type(self):
        if not self.machines:
            return None  # Если нет агрегатов, возвращаем None
        
        station_types = {machine.station_type.name for machine in self.machines if machine.station_type}
        
        if len(station_types) == 1:
            return next(iter(station_types))
        elif len(station_types) > 1:
            return "Разные типы"
        else:
            return None


# Модель для типов агрегатов
class MachineType(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'machine_types'

    # id типа агрегата
    id = db.Column(db.Integer, primary_key=True)
    
    # наименование типа агрегата
    name = db.Column(db.String(80), unique=True, nullable=True)

    # связь с таблицей "Агрегат электростанции"
    machines = db.relationship(
        'Machine', 
        back_populates='type'
    )
    

# Модель для типов агрегатов ТЭС
class TesMachineType(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'tes_machine_types'

    # id типа агрегата
    id = db.Column(db.Integer, primary_key=True)
    
    # наименование типа агрегата
    name = db.Column(db.String(80), unique=True, nullable=False)

    machines = db.relationship(
        'Machine', 
        back_populates='tes_machine_type',
        cascade="all, delete-orphan"
    )


# Модель для агрегата электростанции
class Machine(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'machines'
    
    # id агрегата
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # id состояние агрегата
    id_condition_type = db.Column(
        db.Integer, 
        db.ForeignKey('condition_types.id', ondelete='RESTRICT'), 
        nullable=True)
    condition_type = db.relationship(
        'ConditionType', 
        back_populates='machines')

    # id генерирующей компании
    id_gen_company = db.Column(
        db.Integer, 
        db.ForeignKey('gen_companies.id', ondelete='RESTRICT'), 
        nullable=True)
    gen_company = db.relationship(
        'GenCompany', 
        back_populates='machines')
    
    # id электростанции
    id_station = db.Column(
        db.Integer, 
        db.ForeignKey('stations.id', ondelete='RESTRICT'), nullable=True)
    machine_station = db.relationship(
        'Station', 
        back_populates='machines')

    # id энергорайона (связь с таблицей "Энергорайоны")
    id_energy_area = db.Column(
        db.Integer, 
        db.ForeignKey('energy_areas.id', ondelete='RESTRICT'), 
        nullable=True)
    energy_area = db.relationship(
        'EnergyArea', 
        back_populates='energy_area_machines')

    # номер агрегата
    machine_number = db.Column(db.String(80), nullable=False)

    # название агрегата
    machine_name = db.Column(db.String(255), nullable=False)

    # номер/название группы агрегата
    machine_group = db.Column(db.String(255), nullable=False)

    # название агрегата
    fuel_so = db.Column(db.String(255), nullable=False)

    # id типа электростанции (АЭС, ТЭС, ...)
    id_station_type = db.Column(
        db.Integer, 
        db.ForeignKey('station_types.id', ondelete='RESTRICT'), 
        nullable=True)
    station_type = db.relationship(
        'StationType', 
        back_populates='machines')

    # id типа агрегата
    id_machine_type = db.Column(
        db.Integer, 
        db.ForeignKey('machine_types.id', ondelete='RESTRICT'), 
        nullable=True)
    type = db.relationship(
        'MachineType', 
        back_populates='machines')    
    
    # id типа ТЭС
    id_tes_type = db.Column(
        db.Integer, 
        db.ForeignKey('tes_types.id', ondelete='RESTRICT'), 
        nullable=True
    )
    tes_type = db.relationship(
        'TesType', 
        back_populates='machines'
    )
        
    # id типа машины ТЭС
    id_tes_machine_type = db.Column(
        db.Integer, 
        db.ForeignKey('tes_machine_types.id', ondelete='RESTRICT'), 
        nullable=True
    )
    tes_machine_type = db.relationship(  # <-- исправлено: теперь `tes_machine_type`
        'TesMachineType', 
        back_populates='machines'
    )
    
    # связь с таблицей мощностей агрегатов электростанции
    machine_powers = db.relationship(
        'MachinePower', 
        back_populates='machine_power',
        cascade="all, delete-orphan"
    )   

    # связь с таблицей топлив агрегатов электростанции
    machine_fuels = db.relationship(
        'MachineFuel', 
        back_populates='machine_fuel',
        cascade="all, delete-orphan"
    )  

    # связь с таблицей типов ТЭС агрегатов электростанции
    machine_tes_types = db.relationship(
        'MachineTesType', 
        back_populates='machine_tes_type',
        cascade="all, delete-orphan"
    )  

    # год ввода в эксплуатацию
    date_exploitation = db.Column(db.String(10), nullable=True)
    
    # ожидаемый год ввода в работу
    date_commission_expected = db.Column(db.String(10), nullable=True)

    # фактическая дата ввода в работу
    date_commission_fact = db.Column(db.String(10), nullable=True)

    # ожидаемая дата присоединения
    date_joining_expected = db.Column(db.String(10), nullable=True)

    # фактическая дата присоединения
    date_joining_fact = db.Column(db.String(10), nullable=True)

    # фактическая дата отсоединения
    date_detatchment_fact = db.Column(db.String(10), nullable=True)

    # ожидаемый год вывода из эксплуатации
    date_decompressing_expected = db.Column(db.String(10), nullable=True)

    # фактическая дата вывода из эксплуатации
    date_decompressing_fact = db.Column(db.String(10), nullable=True)

    # ожидаемый год модернизации
    date_modernization_expected = db.Column(db.String(10), nullable=True)

    # фактическая дата перемаркировки
    date_relabing_fact = db.Column(db.String(10), nullable=True)

    # фактическая дата уточнения
    date_update_fact = db.Column(db.String(10), nullable=True)
    
    # примечание
    note = db.Column(db.String(256), unique=False, nullable=True)


# Модель для котла электростанции
class Boiler(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'boilers'
    
    # id котла
    id = db.Column(db.Integer, primary_key=True)

    # наименование котла
    name = db.Column(db.String(80), unique=True, nullable=False)

    # id электростанции
    id_station = db.Column(
        db.Integer, 
        db.ForeignKey('stations.id', ondelete='RESTRICT'), nullable=True)
    boiler_station = db.relationship(
        'Station', 
        back_populates='boilers')


# Модель мощностей агрегатов электростанции
class MachinePower(db.Model):
    __tablename__ = 'machine_powers'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # id года
    year_number = db.Column(
        db.Integer, 
        db.ForeignKey('years.number', ondelete='RESTRICT'),
        nullable=True
    )
    year = db.relationship(
        'Year', 
        back_populates='machine_powers'
    )

    # id агрегата электростанции
    id_machine = db.Column(
        db.Integer, 
        db.ForeignKey('machines.id', ondelete='RESTRICT'), nullable=True)
    machine_power = db.relationship(
        'Machine', 
        back_populates='machine_powers')

    # Установленная мощность агрегата
    p_ust = db.Column(db.Float)

    # Ограничения установленной мощности агрегата
    p_ogr = db.Column(db.Float)    
    
    # Располагаемая мощность агрегата
    p_rasp = db.Column(db.Float)



# Модель для топлива агрегатов электростанции
class MachineFuel(db.Model):
    __tablename__ = 'machine_fuels'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # id года
    year_number = db.Column(
        db.Integer, 
        db.ForeignKey('years.number', ondelete='RESTRICT'),
        nullable=True
    )
    year = db.relationship(
        'Year', 
        back_populates='machine_fuels'
    )

    # id агрегата электростанции
    id_machine = db.Column(
        db.Integer, 
        db.ForeignKey('machines.id', ondelete='RESTRICT'), nullable=True)
    machine_fuel = db.relationship(
        'Machine', 
        back_populates='machine_fuels')

    # Используемое топливо
    id_fuel = db.Column(
        db.Integer, 
        db.ForeignKey('fuels.id', ondelete='RESTRICT'),
        nullable=True)
    fuel = db.relationship(
        'Fuel', 
        back_populates='machine_fuels')
    

# Модель для типов ТЭС агрегатов электростанции
class MachineTesType(db.Model):
    __tablename__ = 'machine_tes_types'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # id года
    year_number = db.Column(
        db.Integer, 
        db.ForeignKey('years.number', ondelete='RESTRICT'),
        nullable=True
    )
    year = db.relationship(
        'Year', 
        back_populates='machine_tes_types'
    )

    # id агрегата электростанции
    id_machine = db.Column(
        db.Integer, 
        db.ForeignKey('machines.id', ondelete='RESTRICT'), nullable=True)
    machine_tes_type = db.relationship(
        'Machine', 
        back_populates='machine_tes_types')

    # Тип ТЭС
    id_tes_type = db.Column(
        db.Integer, 
        db.ForeignKey('tes_types.id', ondelete='RESTRICT'),
        nullable=True)
    tes_type = db.relationship(
        'TesType', 
        back_populates='machine_tes_types') 
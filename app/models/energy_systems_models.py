from app import db
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Table, ForeignKey

Base = declarative_base()

# Промежуточная таблица для связи "многие ко многим"
regional_district_regional_energy_system = db.Table(
    'regional_district_regional_energy_system',
    db.metadata,
    db.Column('regional_district_id', db.Integer, db.ForeignKey('regional_districts.id', ondelete="CASCADE"), primary_key=True),
    db.Column('regional_energy_system_id', db.Integer, db.ForeignKey('regional_energy_systems.id', ondelete="CASCADE"), primary_key=True),
)

# Модель для типов энергосистемы
class EnergySystemType(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'energy_system_types'

    # id типа энергосистемы
    id = db.Column(db.Integer, primary_key=True)

    # наименование типа энергосистемы
    name = db.Column(db.String(80), unique=True, nullable=False)

    # связь с таблицей "Объединенная энергосистема (ОЭС)"
    union_energy_systems = db.relationship(
        'UnionEnergySystem',
        back_populates='energy_system_type'
    )


# Модель для энергорайона
class EnergyArea(db.Model):
    __tablename__ = 'energy_areas'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    # внешний ключ на субъект РФ (региональный округ)
    id_regional_district = db.Column(
        db.Integer,
        db.ForeignKey('regional_districts.id', ondelete='RESTRICT'),
        nullable=False
    )

    # связь с моделью RegionalDistrict
    regional_district = db.relationship(
        'RegionalDistrict',
        back_populates='energy_areas'
    )

    # связь с агрегатами
    machines = db.relationship(
        'Machine',
        back_populates='energy_area'
    )

    @property
    def union_energy_system(self):
        for res in self.regional_district.regional_energy_systems:
            if res.union_energy_system:
                return res.union_energy_system
        return None

    @property
    def regional_energy_system(self):
        for res in self.regional_district.regional_energy_systems:
            return res
        return None


# Модель для энергоузла
class EnergyUnit(db.Model):
    __tablename__ = 'energy_units'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    # внешний ключ на один субъект РФ (один региональный округ)
    id_regional_district = db.Column(
        db.Integer,
        db.ForeignKey('regional_districts.id', ondelete='RESTRICT'),
        nullable=False
    )

    # связь с моделью RegionalDistrict
    regional_district = db.relationship(
        'RegionalDistrict',
        back_populates='energy_units'
    )

    # связь со станциями
    stations = db.relationship(
        'Station',
        back_populates='energy_unit'
    )

    @property
    def union_energy_system(self):
        for res in self.regional_district.regional_energy_systems:
            if res.union_energy_system:
                return res.union_energy_system
        return None

    @property
    def regional_energy_system(self):
        for res in self.regional_district.regional_energy_systems:
            return res
        return None

    

# Модель для региональной энергосистемы
class RegionalEnergySystem(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'regional_energy_systems'

    # id региональной энергосистемы
    id = db.Column(db.Integer, primary_key=True)

    # наименование региональной энергосистемы
    name = db.Column(db.String(255), nullable=False)

    # полное наименование региональной энергосистемы
    name_full = db.Column(db.String(255), nullable=False)

    # id объединенной энергосистемы
    id_union_energy_system = db.Column(
        db.Integer, 
        db.ForeignKey('union_energy_systems.id', ondelete='RESTRICT'), 
        nullable=True)
    

    # cвязь с таблицей "Объединенные энергосистемы"
    union_energy_system = db.relationship(
        'UnionEnergySystem',
        back_populates='regional_energy_systems'
    )

    # связь с таблицей зависимостей "Субъект РФ - Региональная энергосистема"
    regional_districts = db.relationship(
        'RegionalDistrict',
        secondary=regional_district_regional_energy_system,
        back_populates='regional_energy_systems'
    )


# Модель для объединенной энергосистемы (ОЭС)
class UnionEnergySystem(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'union_energy_systems'

    # id объединенной энергосистемы
    id = db.Column(db.Integer, primary_key=True)

    # наименование объединенной энергосистемы (например, ОЭС Центра)
    name = db.Column(db.String(80), unique=True, nullable=False)

    # наименование полное объединенной энергосистемы (например, Объединенная энергосистема Центра")
    name_full = db.Column(db.String(80), unique=True, nullable=False, default=lambda obj: obj.name)

    # id типа энергосистемы
    id_energy_system_type = db.Column(
        db.Integer, 
        db.ForeignKey('energy_system_types.id', ondelete='RESTRICT'), 
        nullable=True)
    
    # связь с таблицей "Региональные энергосистемы"
    regional_energy_systems = db.relationship(
        'RegionalEnergySystem', 
        back_populates='union_energy_system')

    # связь с таблицей "Типы энергосистем"
    energy_system_type = db.relationship(
        'EnergySystemType',
        back_populates='union_energy_systems'
    )
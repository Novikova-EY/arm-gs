from app.extensions import db
from config import SCHEMA_REFDATA


# Модель для типов состояний оборудования или электростанций
class ConditionType(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'condition_types'
    __table_args__ = {"schema": SCHEMA_REFDATA}

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

    pgu_machines = db.relationship(
        'PGUMachine',
        back_populates='condition_type',
        primaryjoin="ConditionType.id == PGUMachine.id_condition_type"
    )

# Модель для типов групп оборудования
class EquipmentGroup(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'equipment_groups'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    # id типа тип группы оборудования
    id = db.Column(db.Integer, primary_key=True)

    # наименование группы оборудования
    name = db.Column(db.String(80), unique=True, nullable=False)

    # связь с таблицей "Агрегаты электростанции"
    machines = db.relationship(
        'Machine', 
        back_populates='equipment_group',
        primaryjoin="EquipmentGroup.id == Machine.id_equipment_group"
    )

    pgu_machines = db.relationship(
        'PGUMachine',
        back_populates='equipment_group_pgu',
        primaryjoin="EquipmentGroup.id == PGUMachine.id_equipment_group_pgu"
    )
    
# Модель для типов электростанций
class StationType(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'station_types'
    __table_args__ = {"schema": SCHEMA_REFDATA}

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
    __table_args__ = {"schema": SCHEMA_REFDATA}

    # id типа ТЭС
    id = db.Column(db.Integer, primary_key=True)
    
    # наименование типа ТЭС
    name = db.Column(db.String(80), unique=True, nullable=False)

    # связь с таблицей "связь типа ТЭС и года"
    machine_tes_types = db.relationship(
        'MachineTesType', 
        back_populates='tes_type', 
        cascade="all, delete-orphan"
    )

# Модель для типов агрегатов
class MachineType(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'machine_types'
    __table_args__ = {"schema": SCHEMA_REFDATA}

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
    __table_args__ = {"schema": SCHEMA_REFDATA}

    # id типа агрегата
    id = db.Column(db.Integer, primary_key=True)
    
    # наименование типа агрегата
    name = db.Column(db.String(80), unique=True, nullable=False)

    machines = db.relationship(
        'Machine', 
        back_populates='tes_machine_type',
        cascade="all, delete-orphan"
    )


# Модель для типов агрегатов ПГУ
class PGUTesMachineType(db.Model):
    __tablename__ = 'pgu_tes_machine_types'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    # Связь с PGUMachine (у каждой PGU может быть подтип — ГТ или ПТ)
    pgu_machines = db.relationship(
        'PGUMachine',
        back_populates='pgu_tes_machine_type',
        cascade="all, delete-orphan"
    )

from app.extensions import db
from sqlalchemy.schema import UniqueConstraint, Index
from sqlalchemy import Numeric
from config import SCHEMA_GENERATION, SCHEMA_REFDATA


# Модель для агрегата электростанции
class PGUMachine(db.Model):
    # название таблицы в базе данных
    __tablename__ = 'pgu_machines'
    __table_args__ = (
        Index('ix_pgu_machine_id_parent_machine', 'id_parent_machine'),
        Index('ix_pgu_machine_id_tes_machine_type', 'id_tes_machine_type'),
        {"schema": SCHEMA_GENERATION},
    )
    
    # id агрегата
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # id агрегата от Техинспекции
    id_ti = db.Column(db.Integer, nullable=True)

    # id группы оборудования
    id_equipment_group_pgu = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_REFDATA}.equipment_groups.id', ondelete='RESTRICT'), 
        nullable=True)
    equipment_group_pgu = db.relationship(
        'EquipmentGroup', 
        back_populates='pgu_machines')

    # id состояние агрегата
    id_condition_type = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_REFDATA}.condition_types.id', ondelete='RESTRICT'), 
        nullable=True)
    condition_type = db.relationship(
        'ConditionType',
        back_populates='pgu_machines'
    )

    # ID основной машины ПГУ
    id_parent_machine = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_GENERATION}.machines.id', ondelete='CASCADE'),
        nullable=False
    )
    parent_machine = db.relationship(
        'Machine',
        backref=db.backref('pgu_submachines', cascade='all, delete-orphan')
    )

    # номер агрегата
    machine_number = db.Column(db.String(80), nullable=True)

    # название агрегата
    machine_name = db.Column(db.String(255), nullable=False)
         
    # связь с таблицей типа агрегата  ТЭС
    id_tes_machine_type = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_REFDATA}.tes_machine_types.id', ondelete='RESTRICT'),
        nullable=True
    )
    tes_machine_type = db.relationship(
        'TesMachineType',
        backref='pgu_machines'
    )

    # ID типа агрегата ПГУ (ГТ или ПТ)
    id_pgu_tes_machine_type = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_REFDATA}.pgu_tes_machine_types.id'), 
        nullable=True)
    pgu_tes_machine_type = db.relationship(
        'PGUTesMachineType', 
        back_populates='pgu_machines')

    # связь с таблицей мощностей агрегатов электростанции
    pgu_machine_powers = db.relationship(
        'PGUMachinePower',
        back_populates='pgu_machine',
        cascade="all, delete-orphan",
        foreign_keys='PGUMachinePower.id_pgu_machine',
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

    # отметка о превышении двух ресурсов газовых машин по ТИ
    resurs_gas = db.Column(db.String(10), nullable=True)


# Модель мощностей агрегатов, входящих в состав ПГУ электростанции
class PGUMachinePower(db.Model):
    __tablename__ = 'pgu_machine_powers'
    __table_args__ = (
        Index('ix_pgu_machine_power_id_pgu_machine', 'id_pgu_machine'),
        Index('ix_pgu_machine_power_year_number', 'year_number'),
        {"schema": SCHEMA_GENERATION},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Год
    year_number = db.Column(
        db.Integer, 
        db.ForeignKey(f'{SCHEMA_REFDATA}.years.number', ondelete='RESTRICT'),
        nullable=True
    )
    year = db.relationship(
        'Year',
        backref='pgu_machine_powers'
    )

    # ID ПГУ-компонента
    id_pgu_machine = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_GENERATION}.pgu_machines.id', ondelete='CASCADE'),
        nullable=True
    )
    pgu_machine = db.relationship(
        'PGUMachine',
        back_populates='pgu_machine_powers'
    )

    # Установленная мощность (по году)
    p_ust = db.Column(Numeric(25, 15), nullable=True)
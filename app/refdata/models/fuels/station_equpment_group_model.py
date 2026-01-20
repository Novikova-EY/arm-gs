# -*- coding: utf-8 -*-
"""
StationEquipmentGroup model (Группа оборудования в привязке к станции).
"""

import uuid
from sqlalchemy import UniqueConstraint, event
from sqlalchemy.sql import text as sql_text
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.versioned_model import VersionedModelMixin

class StationEquipmentGroup(db.Model, VersionedModelMixin):
    __tablename__ = 'station_equipment_groups'
    __table_args__ = (
        UniqueConstraint(
            "id_station",
            "id_equipment_group",
            name="uq_station_equipment_groups_station_equipment_group",
        ),
        {"schema": SCHEMA_GENERATION},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # FK -> Station
    id_station = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_GENERATION}.stations.id', ondelete='RESTRICT'),
        nullable=False,
        index=True,
    )
    station = db.relationship('Station', back_populates='station_equipment_groups')

    # FK -> EquipmentGroup
    id_equipment_group = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_equipment_groups.id', ondelete='RESTRICT'),
        nullable=False,
        index=True,
    )
    equipment_group = db.relationship('EquipmentGroup')

    # Все машины этой станции в этой группе оборудования
    machines = db.relationship('Machine', back_populates='station_equipment_group')

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Название группы оборудования
    name = db.Column(db.String(255), nullable=True)

    # Признак группы оборудования
    niv = db.Column(db.String(255), nullable=True)

    # Признак станции, разбитой на группы оборудования
    comp = db.Column(db.String(255), nullable=True)

    # Код станции, в которую входит группа оборудования
    main = db.Column(db.String(255), nullable=True)

    # Признак действующей станции 
    d = db.Column(db.String(255), nullable=True)

    # Признак расширяемой станции 
    r = db.Column(db.String(255), nullable=True)

    # Признак ФОРЭМ
    form = db.Column(db.String(255), nullable=True)

    # Код группы оборудования
    type = db.Column(db.String(255), nullable=True)

    # Ведомство
    vedomstvo = db.Column(db.String(255), nullable=True)

    # Код субъекта РФ
    obl = db.Column(db.String(255), nullable=True)

    # Код департамента
    dep = db.Column(db.String(255), nullable=True)

    # Код ОЭС
    oes = db.Column(db.String(255), nullable=True)

    # Код экономического района
    er = db.Column(db.String(255), nullable=True)

    # Код федерального округа
    fo = db.Column(db.String(255), nullable=True)

    # Код станции
    numb = db.Column(db.String(255), nullable=True)

    # Название типов турбин, которое соответствует коду (необязательное)
    tm = db.Column(db.String(255), nullable=True)

    # Мощность блока в группе оборудования_вариант 1
    n1 = db.Column(db.String(255), nullable=True)

    # Мощность блока в группе оборудования_вариант 2
    n2 = db.Column(db.String(255), nullable=True)

    # Давление пара перед турбиной_вариант 1
    p1 = db.Column(db.String(255), nullable=True)

    # Давление пара перед турбиной_вариант 2
    p2 = db.Column(db.String(255), nullable=True)

    # Порядковый номер станции
    ordnumb = db.Column(db.String(255), nullable=True)

    # Адрес
    addr = db.Column(db.String(255), nullable=True)

    # Примечание
    note = db.Column(db.String(1000), nullable=True)

    # Код города
    codegor = db.Column(db.String(255), nullable=True)

    # Тип генерирующей компании
    be = db.Column(db.String(255), nullable=True)

    # Код генерирующей компании
    gk = db.Column(db.String(255), nullable=True)

    # Код филиала генерирующей компании/Код субъекта электроэнергетики
    gkf = db.Column(db.String(255), nullable=True)

    # Универсальный внешний код для интеграции с другими системами
    # Генерируется детерминированно на основе external_code станции и группы оборудования
    external_code = db.Column(db.String(36), nullable=False, index=True)

@event.listens_for(StationEquipmentGroup, 'before_insert')
def generate_external_code_before_insert(mapper, connection, target):
    """Генерирует external_code перед вставкой записи на основе external_code станции и ID группы оборудования."""
    # Если код уже есть, не меняем его
    if target.external_code:
        return
    
    # Получаем external_code станции через SQL
    station_code = None
    equipment_group_id = target.id_equipment_group
    
    # Пытаемся получить через связи, если они загружены
    if target.station and hasattr(target.station, 'external_code'):
        station_code = target.station.external_code
    # equipment_group.external_code намеренно НЕ используем
    
    # Если связи не загружены, загружаем через SQL-запрос
    if not station_code and target.id_station:
        result = connection.execute(
            sql_text(f"SELECT external_code FROM {SCHEMA_GENERATION}.stations WHERE id = :id"),
            {"id": target.id_station}
        )
        row = result.fetchone()
        if row:
            station_code = row[0]
    
    # Если external_code ещё не заполнены, используем ID как fallback
    station_code = station_code or f"station_id_{target.id_station}"
    equipment_group_id = equipment_group_id or 0
    
    # Генерируем детерминированный UUID5
    key = f"station_equipment_group|station|{station_code}|equipment_group_id|{equipment_group_id}"
    target.external_code = str(uuid.uuid5(uuid.NAMESPACE_URL, key))







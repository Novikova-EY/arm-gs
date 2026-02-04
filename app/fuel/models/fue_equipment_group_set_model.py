# -*- coding: utf-8 -*-
"""
EquipmentGroupSet model (общая сущность группы оборудования).
"""
import uuid
from sqlalchemy import event
from sqlalchemy.sql import text as sql_text
from app.extensions import db
from config import SCHEMA_FUEL, SCHEMA_REFDATA
from app.common.models.versioned_model import VersionedModelMixin
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation


class EquipmentGroupSet(db.Model, VersionedModelMixin):
    __tablename__ = "gs_fue_equipment_group_sets"
    __table_args__ = ({"schema": SCHEMA_FUEL},)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # FK -> EquipmentGroup
    id_equipment_group = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_equipment_groups.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    equipment_group = db.relationship("EquipmentGroup", back_populates="equipment_group_sets")

    # Пользовательский идентификатор/название группы
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
    external_code = db.Column(db.String(36), nullable=True, index=True)

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Связи
    station_links = db.relationship(
        "EquipmentGroupSetStation",
        back_populates="equipment_group_set",
        cascade="all, delete-orphan",
    )
    stations = db.relationship(
        "Station",
        secondary=EquipmentGroupSetStation.__table__,
        back_populates="equipment_group_sets",
        overlaps="equipment_group_set,station_links,station",
    )

    machines = db.relationship(
        "Machine",
        back_populates="equipment_group_set",
    )

    def __repr__(self) -> str:
        return f"<EquipmentGroupSet id={self.id} equipment_group_id={self.id_equipment_group}>"


@event.listens_for(EquipmentGroupSet, 'before_insert')
def generate_external_code_before_insert(mapper, connection, target):
    """Генерирует external_code перед вставкой записи."""
    if target.external_code:
        return

    name = target.name
    equipment_group_id = target.id_equipment_group
    version_id = target.database_version_id

    if not name and target.id:
        result = connection.execute(
            sql_text(
                f"SELECT name FROM {SCHEMA_FUEL}.gs_fue_equipment_group_sets WHERE id = :id"
            ),
            {"id": target.id}
        )
        row = result.fetchone()
        if row:
            name = row[0]

    name = name or f"equipment_group_set_id_{target.id or 0}"
    equipment_group_id = equipment_group_id or 0
    version_token = version_id if version_id is not None else "null"

    key = f"equipment_group_set|name|{name}|equipment_group_id|{equipment_group_id}|db_version|{version_token}"
    target.external_code = str(uuid.uuid5(uuid.NAMESPACE_URL, key))

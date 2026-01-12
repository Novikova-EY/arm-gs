# -*- coding: utf-8 -*-
"""
StationEquipmentGroup model (Группа оборудования в привязке к станции).
"""

from sqlalchemy import and_
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.versioned_model import VersionedModelMixin

class StationEquipmentGroup(db.Model, VersionedModelMixin):
    __tablename__ = 'station_equipment_groups'
    __table_args__ = {"schema": SCHEMA_GENERATION}

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
    # Используем строковое выражение с foreign() для указания внешних ключей
    machines = db.relationship(
        'Machine',
        primaryjoin="and_(StationEquipmentGroup.id_station == foreign(Machine.id_station), "
                    "StationEquipmentGroup.id_equipment_group == foreign(Machine.id_equipment_group))",
        viewonly=True,
    )

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )







# -*- coding: utf-8 -*-
"""
MachineFuelParam model — привязка топливных данных агрегата к Machine.
Схема gs_fue, связь один-к-одному с машиной (Machine).
"""
from sqlalchemy import UniqueConstraint, cast, Integer
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_FUEL, SCHEMA_GENERATION, SCHEMA_REFDATA


class MachineFuelParam(db.Model):
    """
    Привязка топливных полей агрегата к Machine.
    Одна запись на одну машину.
    """
    __tablename__ = "gs_fue_machine_fuel_param"
    __table_args__ = (
        UniqueConstraint("machine_id", name="uq_machine_fuel_param_machine_id"),
        {"schema": SCHEMA_FUEL},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # FK -> Machine
    machine_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.machines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    machine = db.relationship("Machine", back_populates="machine_fuel_param", uselist=False)

    # Порядковый номер
    numb = db.Column(db.Integer, nullable=True)

    # Номер агрегата
    stnumb = db.Column(db.Integer, nullable=True)

    # Год ввода в эксплуатацию
    yearin = db.Column(db.Integer, nullable=True)

    # Год демонтажа
    dem = db.Column(db.Integer, nullable=True)

    # Тепловая мощность отборов
    nt = db.Column(db.Integer, nullable=True)

    # Код станции
    numb1120 = db.Column(db.Integer, nullable=True)

    # Код группы оборудования → связь с EquipmentGroupSet.numb (без FK в БД, т.к. numb не уникален)
    grcode = db.Column(db.Integer, nullable=True, index=True)
    equipment_group_sets = db.relationship(
        "EquipmentGroupSet",
        primaryjoin="MachineFuelParam.grcode == cast(EquipmentGroupSet.numb, Integer)",
        foreign_keys="[MachineFuelParam.grcode]",
        viewonly=True,
        uselist=True,
        lazy="select",
    )

    @property
    def equipment_group_set(self):
        """Первый EquipmentGroupSet с совпадающим numb для отображения."""
        return self.equipment_group_sets[0] if self.equipment_group_sets else None

    # Название станции
    stname = db.Column(db.String(80), nullable=True)

    # Тип (марка) оборудования
    opesname = db.Column(db.String(80), nullable=True)

    # Примечание
    note = db.Column(db.String(255), nullable=True)

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # timestamps (UTC, server-side)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<MachineFuelParam id={self.id} machine_id={self.machine_id}>"

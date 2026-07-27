# -*- coding: utf-8 -*-
"""
EquipmentGroupHeatAndTariffs — тепло и тарифы из схем теплоснабжения (СТ).
Источник Access: «Тепло из схем теплоснабжения» (+ нормализованные Q/TARIF).
"""
from sqlalchemy import UniqueConstraint
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_FUEL, SCHEMA_REFDATA


class EquipmentGroupHeatAndTariffs(db.Model):
    """
    Тепло (Q) и тариф (TARIF) из схем теплоснабжения.
    Связь с EquipmentGroup через equipment_group_id (NUMB1120 = EquipmentGroup.numb),
    если NUMB1120 задан; иначе запись без привязки к группе оборудования.
    """

    __tablename__ = "gs_fue_equipment_group_heat_and_tariffs"
    __table_args__ = (
        UniqueConstraint(
            "kod_goroda",
            "name_eto",
            "numb1120",
            "var_razv",
            "year_number",
            "database_version_id",
            name="uq_equipment_group_heat_and_tariffs_key",
        ),
        {"schema": SCHEMA_FUEL},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    equipment_group_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_FUEL}.gs_fue_equipment_groups.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    equipment_group = db.relationship(
        "EquipmentGroup",
        backref="heat_and_tariffs",
        foreign_keys=[equipment_group_id],
        uselist=False,
        lazy="select",
    )

    kod_goroda = db.Column(db.Integer, nullable=True, index=True)
    name_goroda = db.Column(db.String(255), nullable=True)
    var_razv = db.Column(db.Integer, nullable=True)
    name_eto = db.Column(db.Text, nullable=True)
    numb1120 = db.Column(db.Integer, nullable=True, index=True)
    ndv_st = db.Column(db.Integer, nullable=True)

    year_number = db.Column(db.Integer, nullable=True, index=True)
    q = db.Column(db.Numeric(36, 16), nullable=True)
    tarif = db.Column(db.Numeric(36, 16), nullable=True)

    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<EquipmentGroupHeatAndTariffs id={self.id} "
            f"equipment_group_id={self.equipment_group_id} year={self.year_number} "
            f"kod_goroda={self.kod_goroda}>"
        )

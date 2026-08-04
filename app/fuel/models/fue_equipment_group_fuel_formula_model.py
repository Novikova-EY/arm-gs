# -*- coding: utf-8 -*-
"""
EquipmentGroupFuelFormula — формулы топлива для группы оборудования.
Аналог источника «Формулы_топлива(Схема)» из Access (toplname: name, year, formtxt, numb1120, numb1, v).
"""

from sqlalchemy import UniqueConstraint
from sqlalchemy.sql import func

from app.extensions import db
from config import SCHEMA_FUEL, SCHEMA_REFDATA


class EquipmentGroupFuelFormula(db.Model):
    __tablename__ = "gs_fue_equipment_group_fuel_formula"
    __table_args__ = (
        UniqueConstraint(
            "equipment_group_id",
            "year_number",
            "variant_number",
            "database_version_id",
            name="uq_eq_group_fuel_formula_group_year_variant_version",
        ),
        {"schema": SCHEMA_FUEL},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # FK -> EquipmentGroup (итоговая группа оборудования)
    equipment_group_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_FUEL}.gs_fue_equipment_groups.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    equipment_group = db.relationship(
        "EquipmentGroup",
        backref="fuel_formulas",
        foreign_keys=[equipment_group_id],
        uselist=False,
        lazy="select",
    )

    name = db.Column(db.String(512), nullable=True)
    year_number = db.Column(db.Integer, nullable=False, index=True)

    # Аналог поля v из Access
    variant_number = db.Column(db.Integer, nullable=False, default=0, index=True)

    # Код группы оборудования
    numb1120 = db.Column(db.Integer, nullable=True, index=True)
    numb1 = db.Column(db.Numeric(36, 16), nullable=True, index=True)

    formtxt = db.Column(db.Text, nullable=True)

    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<EquipmentGroupFuelFormula id={self.id} "
            f"equipment_group_id={self.equipment_group_id} "
            f"year_number={self.year_number} variant_number={self.variant_number}>"
        )

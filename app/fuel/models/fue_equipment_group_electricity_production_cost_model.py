# -*- coding: utf-8 -*-
"""
EquipmentGroupElectricityProductionCost — затраты ТЭС на производство ЭЭ и ТЭ.
Поля из Excel: NAME, NUMB1120, Year, code_zatr, ZATRATY_SUM, Zatr_E, Zatr_P, Zatr_Q.
"""
from sqlalchemy import UniqueConstraint
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_FUEL, SCHEMA_REFDATA


class EquipmentGroupElectricityProductionCost(db.Model):
    """
    Затраты ТЭС на производство электрической и тепловой энергии для группы оборудования.
    Связь с EquipmentGroup через equipment_group_id (NUMB1120 = EquipmentGroup.numb).
    code_zatr хранится в cost_code; наименование подгружается из ElectricityProductionCostType.
    """
    __tablename__ = "gs_fue_equipment_group_electricity_production_cost"
    __table_args__ = (
        UniqueConstraint(
            "equipment_group_id",
            "year_number",
            "cost_code",
            name="uq_equipment_group_electricity_production_cost_group_year_code",
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
        backref="electricity_production_costs",
        foreign_keys=[equipment_group_id],
        uselist=False,
        lazy="select",
    )

    name = db.Column(db.String(512), nullable=True)  # NAME из Excel
    year_number = db.Column(db.Integer, nullable=True, index=True)  # Year
    cost_code = db.Column(db.Integer, nullable=True, index=True)  # code_zatr

    zatraty_sum = db.Column(db.Numeric(36, 16), nullable=True)
    zatr_e = db.Column(db.Numeric(36, 16), nullable=True)
    zatr_p = db.Column(db.Numeric(36, 16), nullable=True)
    zatr_q = db.Column(db.Numeric(36, 16), nullable=True)

    # Код группы оборудования
    numb1120 = db.Column(db.Integer, nullable=True, index=True)

    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<EquipmentGroupElectricityProductionCost id={self.id} "
            f"equipment_group_id={self.equipment_group_id} year={self.year_number} "
            f"cost_code={self.cost_code}>"
        )

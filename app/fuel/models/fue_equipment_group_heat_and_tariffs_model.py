# -*- coding: utf-8 -*-
"""
EquipmentGroupHeatAndTariffs — тепло и тарифы из схем теплоснабжения (СТ).
Источник Access: «Тепло из схем теплоснабжения» (+ нормализованные Q/TARIF).
"""
from sqlalchemy import ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_FUEL, SCHEMA_REFDATA


class EquipmentGroupHeatAndTariffs(db.Model):
    """
    Тепло (Q) и тариф (TARIF) из схем теплоснабжения.
    Связь с EquipmentGroup через equipment_group_id и numb1120 = EquipmentGroup.numb
    (без FK на numb — поле не уникально).
    year_number + database_version_id → Year.number + Year.database_version_id.
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
        ForeignKeyConstraint(
            ["year_number", "database_version_id"],
            [
                f"{SCHEMA_REFDATA}.gs_sys_years.number",
                f"{SCHEMA_REFDATA}.gs_sys_years.database_version_id",
            ],
            ondelete="RESTRICT",
            name="fk_equipment_group_heat_and_tariffs_year_ver",
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

    # Код группы оборудования: numb1120 = EquipmentGroup.numb (без FK — numb не уникален)
    numb1120 = db.Column(db.Integer, nullable=True, index=True)
    equipment_group_by_numb = db.relationship(
        "EquipmentGroup",
        primaryjoin=(
            "and_("
            "EquipmentGroupHeatAndTariffs.numb1120==foreign(EquipmentGroup.numb), "
            "EquipmentGroupHeatAndTariffs.database_version_id==EquipmentGroup.database_version_id"
            ")"
        ),
        viewonly=True,
        uselist=False,
        lazy="select",
    )

    ndv_st = db.Column(db.Integer, nullable=True)

    # Ссылка на год: Year.number + database_version_id (composite FK).
    year_number = db.Column(db.Integer, nullable=True, index=True)
    year = db.relationship(
        "Year",
        lazy="noload",
        primaryjoin=(
            "and_(Year.number==EquipmentGroupHeatAndTariffs.year_number, "
            "Year.database_version_id==EquipmentGroupHeatAndTariffs.database_version_id)"
        ),
        foreign_keys=(
            "[EquipmentGroupHeatAndTariffs.year_number, "
            "EquipmentGroupHeatAndTariffs.database_version_id]"
        ),
        viewonly=True,
    )

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

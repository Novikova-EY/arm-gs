# -*- coding: utf-8 -*-
"""
EquipmentGroupSpecificFuelConsumption model — удельные показатели групп оборудования.
Поля: NAME, Year, Y, BTP, SNTP, BK, NUMB1120, SNK.
"""
from sqlalchemy import UniqueConstraint
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_FUEL, SCHEMA_REFDATA


class EquipmentGroupSpecificFuelConsumption(db.Model):
    """
    Удельные показатели группы оборудования.
    Связь с EquipmentGroup через equipment_group_id.
    Поля из Excel: NAME, Year, Y, BTP, SNTP, BK, NUMB1120, SNK.
    """
    __tablename__ = "gs_fue_equipment_group_specific_fuel_consumption"
    __table_args__ = (
        UniqueConstraint(
            "equipment_group_id",
            "year_number",
            name="uq_equipment_group_specific_fuel_consumption_group_year",
        ),
        {"schema": SCHEMA_FUEL},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # FK -> EquipmentGroup (итоговая группа оборудования)
    equipment_group_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_FUEL}.gs_fue_equipment_groups.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    equipment_group = db.relationship(
        "EquipmentGroup",
        backref="specific_fuel_consumptions",
        foreign_keys=[equipment_group_id],
        uselist=False,
        lazy="select",
    )

    name = db.Column(db.String(512), nullable=True)
    year_number = db.Column(db.Integer, nullable=True, index=True)

    # Удельная выработка эл.эн. на тепловом потреблении
    y = db.Column(db.Numeric(36, 16), nullable=True)

    # Удельный расход усл.топлива на отпуск эл.эн. в теплофик.режиме
    btp = db.Column(db.Numeric(36, 16), nullable=True)

    # Эл.энергия на собственные нужды  в теплофик.режиме
    sntp = db.Column(db.Numeric(36, 16), nullable=True)

    # Удельный расход усл.топлива на отпуск эл.эн. в конд.режиме
    bk = db.Column(db.Numeric(36, 16), nullable=True)

    # Собственные нужды на выработку электроэнергии
    snk = db.Column(db.Numeric(36, 16), nullable=True)

    # Коэффициент экономии от теплофикации (привязан к году). Numeric для дробных (1.5, 0.7)
    k = db.Column(db.Numeric(10, 4), nullable=True)

    # --- Расчетные величины (_calc) ---
    # Удельная выработка эл.эн. на тепловом потреблении
    y_calc = db.Column(db.Numeric(36, 16), nullable=True)

    # Удельный расход усл.топлива на отпуск эл.эн. в теплофик.режиме
    btp_calc = db.Column(db.Numeric(36, 16), nullable=True)

    # Эл.энергия на собственные нужды  в теплофик.режиме
    sntp_calc = db.Column(db.Numeric(36, 16), nullable=True)

    # Удельный расход усл.топлива на отпуск эл.эн. в конд.режиме
    bk_calc = db.Column(db.Numeric(36, 16), nullable=True)

    # Собственные нужды на выработку электроэнергии
    snk_calc = db.Column(db.Numeric(36, 16), nullable=True)

    numb1120 = db.Column(db.Integer, nullable=True, index=True)

    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Наименования для шапки таблицы:
    COLUMN_LABELS = {
        "name": "NAME",
        "year_number": "Year",
        "k": "Коэффициент экономии от теплофикации",
        "y": "Удельная выработка эл.эн. на тепловом потреблении",
        "btp": "Удельный расход усл.топлива на отпуск эл.эн. в теплофик.режиме",
        "sntp": "Эл.энергия на собственные нужды в теплофик.режиме",
        "bk": "Удельный расход усл.топлива на отпуск эл.эн. в конд.режиме",
        "snk": "Собственные нужды на выработку электроэнергии",
        "y_calc": "Удельная выработка эл.эн. на тепловом потреблении",
        "btp_calc": "Удельный расход усл.топлива на отпуск эл.эн. в теплофик.режиме",
        "sntp_calc": "Эл.энергия на собственные нужды в теплофик.режиме",
        "bk_calc": "Удельный расход усл.топлива на отпуск эл.эн. в конд.режиме",
        "snk_calc": "Собственные нужды на выработку электроэнергии",
        "numb1120": "NUMB1120",
    }

    def __repr__(self) -> str:
        return (
            f"<EquipmentGroupSpecificFuelConsumption id={self.id} "
            f"equipment_group_id={self.equipment_group_id} year={self.year_number}>"
        )

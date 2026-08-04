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

    # Удельная выработка ЭЭ на тепловом потреблении, кВтч/⁠Гкал
    y = db.Column(db.Numeric(36, 16), nullable=True)

    # УРУТ на отпуск ЭЭ в теплофикационном режиме, г у.т./кВтч
    btp = db.Column(db.Numeric(36, 16), nullable=True)

    # Коэффициент отпуска ЭЭ в теплофикационном режиме
    sntp = db.Column(db.Numeric(36, 16), nullable=True)

    # УРУТ на отпуск ЭЭ в конденсационном режиме, г у.т./кВтч
    bk = db.Column(db.Numeric(36, 16), nullable=True)

    # СН на выработку ЭЭ, %
    snk = db.Column(db.Numeric(36, 16), nullable=True)

    # Ветвь Access для VED∈{1,4}: базовые СН/расход и наклоны по часам
    # snbas, Ksn — для ekotp; bbas, Kh — для EUST
    snbas = db.Column(db.Numeric(36, 16), nullable=True)
    ksn = db.Column(db.Numeric(36, 16), nullable=True)
    bbas = db.Column(db.Numeric(36, 16), nullable=True)
    kh = db.Column(db.Numeric(36, 16), nullable=True)

    # Коэффициент экономии от теплофикации (привязан к году). Numeric для дробных (1.5, 0.7)
    k = db.Column(db.Numeric(10, 4), nullable=True)

    # --- Расчетные величины (_calc) ---
    # Удельная выработка ЭЭ на тепловом потреблении, кВтч/⁠Гкал
    y_calc = db.Column(db.Numeric(36, 16), nullable=True)

    # УРУТ на отпуск ЭЭ в теплофикационном режиме, г у.т./кВтч
    btp_calc = db.Column(db.Numeric(36, 16), nullable=True)

    # Коэффициент отпуска ЭЭ в теплофикационном режиме
    sntp_calc = db.Column(db.Numeric(36, 16), nullable=True)

    # УРУТ на отпуск ЭЭ в конденсационном режиме, г у.т./кВтч
    bk_calc = db.Column(db.Numeric(36, 16), nullable=True)

    # СН на выработку ЭЭ, %
    snk_calc = db.Column(db.Numeric(36, 16), nullable=True)

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

    # Подпись y / y_calc для шапок (неразрывный пробел между «выработка» и «ЭЭ»).
    Y_COLUMN_LABEL = "Удельная выработка ЭЭ на тепловом потреблении, кВтч/⁠Гкал"
    # Подпись btp / btp_calc для шапок.
    BTP_COLUMN_LABEL = "УРУТ на отпуск ЭЭ в теплофикационном режиме, г у.т./кВтч"
    # Подпись bk / bk_calc для шапок (неразрывный пробел между «отпуск» и «ЭЭ»,
    # между «г» и «у.т.»).
    BK_COLUMN_LABEL = "УРУТ на отпуск ЭЭ в конденсационном режиме, г у.т./кВтч"
    # Подпись snk / snk_calc для шапок (неразрывный пробел между «выработку» и «ЭЭ»).
    SNK_COLUMN_LABEL = "СН на выработку ЭЭ, %"
    # Подпись sntp / sntp_calc для шапок (неразрывный пробел между «отпуска» и «ЭЭ»).
    SNTP_COLUMN_LABEL = "Коэффициент отпуска ЭЭ в теплофикационном режиме"

    # Наименования для шапки таблицы:
    COLUMN_LABELS = {
        "name": "NAME",
        "year_number": "Year",
        "k": "Коэффициент экономии от теплофикации",
        "y": Y_COLUMN_LABEL,
        "btp": BTP_COLUMN_LABEL,
        "sntp": SNTP_COLUMN_LABEL,
        "bk": BK_COLUMN_LABEL,
        "snk": SNK_COLUMN_LABEL,
        "snbas": "Базовый СН (VED 1/4), %",
        "ksn": "Наклон СН по часам (Ksn, VED 1/4)",
        "bbas": "Базовый удельный расход (bbas, VED 1/4)",
        "kh": "Наклон удельного расхода по часам (Kh, VED 1/4)",
        "y_calc": Y_COLUMN_LABEL,
        "btp_calc": BTP_COLUMN_LABEL,
        "sntp_calc": SNTP_COLUMN_LABEL,
        "bk_calc": BK_COLUMN_LABEL,
        "snk_calc": SNK_COLUMN_LABEL,
        "numb1120": "Код группы оборудования",
    }

    def __repr__(self) -> str:
        return (
            f"<EquipmentGroupSpecificFuelConsumption id={self.id} "
            f"equipment_group_id={self.equipment_group_id} year={self.year_number}>"
        )

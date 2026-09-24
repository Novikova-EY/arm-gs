# -*- coding: utf-8 -*-
"""Отчетные данные ГИС ТЭК: загрязняющие вещества (ЗВ)."""
from sqlalchemy import ForeignKeyConstraint, Numeric, UniqueConstraint
from sqlalchemy.sql import func

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_ECOLOGY, SCHEMA_FUEL, SCHEMA_REFDATA


class ZVReportGisTek(db.Model, AuditMixin):
    """Строка листа «СБОРКА ЗВ»: выбросы загрязняющих веществ по году.

    Связь с EquipmentGroup через equipment_group_id и station_numb = EquipmentGroup.numb
    (без FK на numb — поле не уникально).
    year_number + database_version_id → Year.number + Year.database_version_id.
    """

    __tablename__ = "gs_eco_gis_tek_pollutant_params"
    __table_args__ = (
        UniqueConstraint(
            "station_numb",
            "year_number",
            "database_version_id",
            name="uq_eco_gis_tek_zv_numb_year_ver",
        ),
        ForeignKeyConstraint(
            ["year_number", "database_version_id"],
            [
                f"{SCHEMA_REFDATA}.gs_sys_years.number",
                f"{SCHEMA_REFDATA}.gs_sys_years.database_version_id",
            ],
            ondelete="RESTRICT",
            name="fk_eco_gis_tek_zv_year_ver",
        ),
        {"schema": SCHEMA_ECOLOGY},
    )

    # Уникальный идентификатор записи
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Код группы оборудования: station_numb (numb1120) = EquipmentGroup.numb (без FK — numb не уникален)
    station_numb = db.Column(db.Integer, nullable=False, index=True)
    equipment_group_by_numb = db.relationship(
        "EquipmentGroup",
        primaryjoin=(
            "and_("
            "ZVReportGisTek.station_numb==foreign(EquipmentGroup.numb), "
            "ZVReportGisTek.database_version_id==EquipmentGroup.database_version_id"
            ")"
        ),
        viewonly=True,
        uselist=False,
        lazy="select",
    )

    # Электростанция (ГИС ТЭК), наименование из файла
    gis_tek_station_name = db.Column(db.Text, nullable=True)

    # Тип станции (КЭС, ТЭЦ и т.п.)
    station_type = db.Column(db.String(80), nullable=True)

    # Группа оборудования (Топливо), FK -> gs_fue.gs_fue_equipment_groups
    equipment_group_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_FUEL}.gs_fue_equipment_groups.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    equipment_group = db.relationship(
        "EquipmentGroup",
        foreign_keys=[equipment_group_id],
        uselist=False,
        lazy="select",
    )

    # Год: Year.number + database_version_id (composite FK)
    year_number = db.Column(db.Integer, nullable=False, index=True)
    year = db.relationship(
        "Year",
        lazy="noload",
        primaryjoin=(
            "and_(Year.number==ZVReportGisTek.year_number, "
            "Year.database_version_id==ZVReportGisTek.database_version_id)"
        ),
        foreign_keys="[ZVReportGisTek.year_number, ZVReportGisTek.database_version_id]",
        viewonly=True,
    )

    # Твердые вещества, т
    solid_substances = db.Column(Numeric(36, 16), nullable=True)

    # Газообразные и жидкие вещества, т (расчётное: SO2 + CO + NOx + углеводороды + ЛОС + прочие)
    gaseous_and_liquid = db.Column(Numeric(36, 16), nullable=True)

    # Диоксид серы, т
    sulfur_dioxide = db.Column(Numeric(36, 16), nullable=True)

    # Оксид углерода [CO], т
    carbon_monoxide = db.Column(Numeric(36, 16), nullable=True)

    # Оксиды азота [в пересчете на NO2], т
    nitrogen_oxides = db.Column(Numeric(36, 16), nullable=True)

    # Углеводороды [без летучих органических соединений], т
    hydrocarbons = db.Column(Numeric(36, 16), nullable=True)

    # Летучие органические соединения [ЛОС], т
    voc = db.Column(Numeric(36, 16), nullable=True)
    
    # В т.ч. прочие газообразные и жидкие, т
    other_gaseous_and_liquid = db.Column(Numeric(36, 16), nullable=True)

    # Примечание
    note = db.Column(db.Text, nullable=True)

    # Дата и время создания записи
    created_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Дата и время последнего изменения записи
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    # Версия базы данных, FK -> gs_sys.gs_database_versions
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<ZVReportGisTek id={self.id} numb={self.station_numb} "
            f"year={self.year_number}>"
        )

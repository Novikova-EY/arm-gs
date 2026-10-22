# -*- coding: utf-8 -*-
"""Отчетные данные ГИС ТЭК: парниковые газы (ПГ)."""
from sqlalchemy import ForeignKeyConstraint, Numeric, UniqueConstraint
from sqlalchemy.sql import func

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_ECOLOGY, SCHEMA_FUEL, SCHEMA_REFDATA


class PGReportGisTek(db.Model, AuditMixin):
    """Строка листа «СБОРКА ПГ»: выбросы СО2 по видам топлива и году.

    Связь с EquipmentGroup через equipment_group_id и station_numb = EquipmentGroup.numb
    (без FK на numb – поле не уникально).
    year_number + database_version_id → Year.number + Year.database_version_id.
    """

    __tablename__ = "gs_eco_gis_tek_greenhouse_gas_params"
    __table_args__ = (
        UniqueConstraint(
            "station_numb",
            "year_number",
            "database_version_id",
            name="uq_eco_gis_tek_pg_numb_year_ver",
        ),
        ForeignKeyConstraint(
            ["year_number", "database_version_id"],
            [
                f"{SCHEMA_REFDATA}.gs_sys_years.number",
                f"{SCHEMA_REFDATA}.gs_sys_years.database_version_id",
            ],
            ondelete="RESTRICT",
            name="fk_eco_gis_tek_pg_year_ver",
        ),
        {"schema": SCHEMA_ECOLOGY},
    )

    # Уникальный идентификатор записи
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Код группы оборудования: station_numb (numb1120) = EquipmentGroup.numb (без FK – numb не уникален)
    station_numb = db.Column(db.Integer, nullable=False, index=True)
    equipment_group_by_numb = db.relationship(
        "EquipmentGroup",
        primaryjoin=(
            "and_("
            "PGReportGisTek.station_numb==foreign(EquipmentGroup.numb), "
            "PGReportGisTek.database_version_id==EquipmentGroup.database_version_id"
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
            "and_(Year.number==PGReportGisTek.year_number, "
            "Year.database_version_id==PGReportGisTek.database_version_id)"
        ),
        foreign_keys="[PGReportGisTek.year_number, PGReportGisTek.database_version_id]",
        viewonly=True,
    )

    # Расход газа, т у.т.
    gas_consumption_tce = db.Column(Numeric(36, 16), nullable=True)

    # Выбросы СО2 от сжигания газа, т
    co2_from_gas_t = db.Column(Numeric(36, 16), nullable=True)

    # Расход мазута, т у.т.
    oil_fuel_consumption_tce = db.Column(Numeric(36, 16), nullable=True)

    # Выбросы СО2 от сжигания мазута, т
    co2_from_oil_fuel_t = db.Column(Numeric(36, 16), nullable=True)

    # Расход твердого топлива, т у.т.
    solid_fuel_consumption_tce = db.Column(Numeric(36, 16), nullable=True)
    
    # Выбросы СО2 от сжигания твердого топлива, т
    co2_from_solid_fuel_t = db.Column(Numeric(36, 16), nullable=True)

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
            f"<PGReportGisTek id={self.id} numb={self.station_numb} "
            f"year={self.year_number}>"
        )

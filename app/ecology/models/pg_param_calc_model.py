# -*- coding: utf-8 -*-
"""Параметры анализа ПГ (выверенная копия отчетных данных ГИС ТЭК)."""
from sqlalchemy import ForeignKeyConstraint, Numeric, UniqueConstraint
from sqlalchemy.sql import func

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_ECOLOGY, SCHEMA_REFDATA


class PGParamCalc(db.Model, AuditMixin):
    """Строка параметров страниц /ecology/analysis/pg-vse/ и pg-bez-kot/.

    Первоначально копируется из PGReportGisTek; далее может
    редактироваться отдельно от отчетных данных.
    Связь с EquipmentGroup: station_numb (numb1120) = EquipmentGroup.numb
    (без FK на numb – поле не уникально).
    year_number + database_version_id → Year.number + Year.database_version_id.
    """

    __tablename__ = "gs_eco_analysis_pg_params"
    __table_args__ = (
        UniqueConstraint(
            "sheet_slug",
            "station_numb",
            "year_number",
            "database_version_id",
            name="uq_eco_analysis_pg_sheet_numb_year_ver",
        ),
        ForeignKeyConstraint(
            ["year_number", "database_version_id"],
            [
                f"{SCHEMA_REFDATA}.gs_sys_years.number",
                f"{SCHEMA_REFDATA}.gs_sys_years.database_version_id",
            ],
            ondelete="RESTRICT",
            name="fk_eco_analysis_pg_year_ver",
        ),
        {"schema": SCHEMA_ECOLOGY},
    )

    # Уникальный идентификатор записи
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Страница анализа: pg-vse или pg-bez-kot
    sheet_slug = db.Column(db.String(40), nullable=False, index=True)

    # Код группы оборудования: station_numb (numb1120) = EquipmentGroup.numb (без FK – numb не уникален)
    station_numb = db.Column(db.Integer, nullable=False, index=True)
    equipment_group_by_numb = db.relationship(
        "EquipmentGroup",
        primaryjoin=(
            "and_("
            "PGParamCalc.station_numb==foreign(EquipmentGroup.numb), "
            "PGParamCalc.database_version_id==EquipmentGroup.database_version_id"
            ")"
        ),
        viewonly=True,
        uselist=False,
        lazy="select",
    )

    # Год: Year.number + database_version_id (composite FK)
    year_number = db.Column(db.Integer, nullable=False, index=True)
    year = db.relationship(
        "Year",
        lazy="noload",
        primaryjoin=(
            "and_(Year.number==PGParamCalc.year_number, "
            "Year.database_version_id==PGParamCalc.database_version_id)"
        ),
        foreign_keys="[PGParamCalc.year_number, PGParamCalc.database_version_id]",
        viewonly=True,
    )

    # Расход газа, т у.т. (GAZ_ek)
    gas_consumption_tce = db.Column(Numeric(36, 16), nullable=True)

    # Выбросы СО2 от сжигания газа, т (CO2_gaz)
    co2_from_gas_t = db.Column(Numeric(36, 16), nullable=True)

    # Расход мазута, т у.т. (MAZUT_ek)
    oil_fuel_consumption_tce = db.Column(Numeric(36, 16), nullable=True)

    # Выбросы СО2 от сжигания мазута, т (CO2_mazut)
    co2_from_oil_fuel_t = db.Column(Numeric(36, 16), nullable=True)

    # Расход твердого топлива, т у.т. (TvTopl_ek)
    solid_fuel_consumption_tce = db.Column(Numeric(36, 16), nullable=True)
    
    # Выбросы СО2 от сжигания твердого топлива, т (CO2_ugol)
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
            f"<PGParamCalc id={self.id} sheet={self.sheet_slug} "
            f"numb={self.station_numb} year={self.year_number}>"
        )

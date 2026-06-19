# -*- coding: utf-8 -*-
"""
Параметры нагрузки (demand) для региональной энергосистемы.
"""
from sqlalchemy import CheckConstraint, Numeric, text
from sqlalchemy.sql import func

from app.extensions import db
from app.common.models.audit_mixin import AuditMixin
from config import SCHEMA_POWER_DEMAND, SCHEMA_REFDATA


class RegionalEnergySystemDemandParameter(db.Model, AuditMixin):
    """
    - is_historical_maximum=True: одна строка на (РЭС, версия БД); year_number NULL.
    - is_historical_maximum=False: строки по календарным годам.
    """

    __tablename__ = "gs_pd_regional_energy_system_demand_params"
    __table_args__ = (
        CheckConstraint(
            "(is_historical_maximum = true AND year_number IS NULL) OR "
            "(is_historical_maximum = false AND year_number IS NOT NULL)",
            name="ck_gs_res_demand_params_year_vs_hist",
        ),
        {"schema": SCHEMA_POWER_DEMAND},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    id_regional_energy_system = db.Column(
        db.Integer,
        db.ForeignKey(
            f"{SCHEMA_REFDATA}.gs_sys_regional_energy_systems.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )
    regional_energy_system = db.relationship(
        "RegionalEnergySystem",
        back_populates="demand_parameters",
    )

    is_historical_maximum = db.Column(
        db.Boolean, nullable=False, server_default=text("false")
    )

    # Год
    year_number = db.Column(db.Integer, nullable=True, index=True)

    # Максимальное потребление мощности, МВт
    max_power_consumption_mw = db.Column(Numeric(25, 3), nullable=True)

    # Дата и время максимума потребления мощности, МВт
    peak_datetime_msk = db.Column(db.DateTime(timezone=True), nullable=True)

    # Средняя дневная температура воздуха, °C
    avg_daily_air_temp_c = db.Column(Numeric(10, 2), nullable=True)

    # Совмещенный максимум на ОЭС, МВт
    combined_on_oes = db.Column(Numeric(25, 3), nullable=True)

    # Совмещенный максимум на ЕЭС, МВт
    combined_on_ees = db.Column(Numeric(25, 3), nullable=True)

    # Совмещенный максимум на энергозону, МВт
    combined_on_ez = db.Column(Numeric(25, 3), nullable=True)

    # Совмещенный максимум на ФО, МВт
    combined_on_fo = db.Column(Numeric(25, 3), nullable=True)

    # Совмещенный максимум на ЦЗ России, МВт
    combined_on_cz = db.Column(Numeric(25, 3), nullable=True)

    # Коэффициент k для показателя «Совмещённый на ОЭС, МВт»
    coeff_k_combined_on_oes = db.Column(Numeric(25, 6), nullable=True)

    # Коэффициент k для показателя «Совмещённый на ЕЭС, МВт»
    coeff_k_combined_on_ees = db.Column(Numeric(25, 6), nullable=True)

    # Примечание
    note = db.Column(db.Text, nullable=True)


    created_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<RegionalEnergySystemDemandParameter id={self.id} "
            f"res_id={self.id_regional_energy_system} "
            f"hist={self.is_historical_maximum} year={self.year_number}>"
        )

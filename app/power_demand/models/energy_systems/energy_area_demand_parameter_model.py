# -*- coding: utf-8 -*-
"""Параметры нагрузки (demand) для энергоузла (EnergyArea)."""
from sqlalchemy import CheckConstraint, Numeric, text
from sqlalchemy.sql import func

from app.extensions import db
from app.common.models.audit_mixin import AuditMixin
from config import SCHEMA_POWER_DEMAND, SCHEMA_REFDATA


class EnergyAreaDemandParameter(db.Model, AuditMixin):
    __tablename__ = "gs_pd_energy_area_demand_params"
    __table_args__ = (
        CheckConstraint(
            "(is_historical_maximum = true AND year_number IS NULL) OR "
            "(is_historical_maximum = false AND year_number IS NOT NULL)",
            name="ck_gs_energy_area_demand_params_year_vs_hist",
        ),
        {"schema": SCHEMA_POWER_DEMAND},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    id_energy_area = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_energy_areas.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    energy_area = db.relationship("EnergyArea", back_populates="demand_parameters")

    is_historical_maximum = db.Column(
        db.Boolean, nullable=False, server_default=text("false")
    )

    # Год
    year_number = db.Column(db.Integer, nullable=True, index=True)

    # Максимальное потребление мощности, МВт
    max_power_consumption_mw = db.Column(Numeric(25, 16), nullable=True)

    # Дата и время максимального потребления мощности, МВт
    peak_datetime_msk = db.Column(db.DateTime(timezone=True), nullable=True)

    # Средняя дневная температура воздуха, °C
    avg_daily_air_temp_c = db.Column(Numeric(10, 2), nullable=True)

    # Совмещенный максимум на ОЭС, МВт
    combined_on_oes = db.Column(Numeric(25, 16), nullable=True)

    # Совмещенный максимум на ЕЭС, МВт
    combined_on_ees = db.Column(Numeric(25, 16), nullable=True)

    # Совмещенный максимум на РЭС, МВт
    combined_on_es = db.Column(Numeric(25, 16), nullable=True)

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
            f"<EnergyAreaDemandParameter id={self.id} energy_area_id={self.id_energy_area} "
            f"hist={self.is_historical_maximum} year={self.year_number}>"
        )

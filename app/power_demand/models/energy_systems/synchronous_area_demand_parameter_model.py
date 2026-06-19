# -*- coding: utf-8 -*-
"""Параметры нагрузки (demand) для синхронной зоны (SynchronousArea)."""
from sqlalchemy import CheckConstraint, Numeric, text
from sqlalchemy.sql import func

from app.extensions import db
from app.common.models.audit_mixin import AuditMixin
from app.common.models.perimeter_variant_mixin import PerimeterVariantColumnMixin
from config import SCHEMA_POWER_DEMAND, SCHEMA_REFDATA


class SynchronousAreaDemandParameter(db.Model, AuditMixin, PerimeterVariantColumnMixin):
    __tablename__ = "gs_pd_synchronous_area_demand_params"
    __table_args__ = (
        CheckConstraint(
            "(is_historical_maximum = true AND year_number IS NULL) OR "
            "(is_historical_maximum = false AND year_number IS NOT NULL)",
            name="ck_gs_synchronous_area_demand_params_year_vs_hist",
        ),
        {"schema": SCHEMA_POWER_DEMAND},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    id_synchronous_area = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_synchronous_areas.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    synchronous_area = db.relationship(
        "SynchronousArea", back_populates="demand_parameters"
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

    # Совмещенный максимум на ЕЭС, МВт
    combined_on_ees = db.Column(Numeric(25, 3), nullable=True)

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
            f"<SynchronousAreaDemandParameter id={self.id} "
            f"synchronous_area_id={self.id_synchronous_area} "
            f"hist={self.is_historical_maximum} year={self.year_number}>"
        )

# -*- coding: utf-8 -*-
"""
Параметры нагрузки (demand) для Российской Федерации в целом.

Отдельной строки в справочнике refdata нет: в таблице только срезы «исторический максимум» и по годам,
без FK на gs_* (уникальность — по версии БД и году, см. миграцию).
"""
from sqlalchemy import CheckConstraint, Numeric, text
from sqlalchemy.sql import func

from app.extensions import db
from app.common.models.audit_mixin import AuditMixin
from app.common.models.perimeter_variant_mixin import PerimeterVariantColumnMixin
from config import SCHEMA_POWER_DEMAND, SCHEMA_REFDATA


class RussiaFederationDemandParameter(db.Model, AuditMixin, PerimeterVariantColumnMixin):
    __tablename__ = "gs_pd_russia_federation_demand_params"
    __table_args__ = (
        CheckConstraint(
            "(is_historical_maximum = true AND year_number IS NULL) OR "
            "(is_historical_maximum = false AND year_number IS NOT NULL)",
            name="ck_gs_russia_federation_demand_params_year_vs_hist",
        ),
        # Частичные уникальные индексы без id сущности — в миграции
        {"schema": SCHEMA_POWER_DEMAND},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    is_historical_maximum = db.Column(
        db.Boolean, nullable=False, server_default=text("false")
    )

    # Год
    year_number = db.Column(db.Integer, nullable=True, index=True)

    # Максимальное потребление мощности, МВт
    max_power_consumption_mw = db.Column(Numeric(25, 3), nullable=True)

    # Дата и время максимума потребления мощности, МВт
    peak_datetime = db.Column(db.DateTime(timezone=True), nullable=True)

    # Средняя дневная температура воздуха, °C
    avg_daily_air_temp_c = db.Column(Numeric(10, 2), nullable=True)

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
            f"<RussiaFederationDemandParameter id={self.id} "
            f"perimeter_variant={self.perimeter_variant_code} "
            f"hist={self.is_historical_maximum} year={self.year_number}>"
        )

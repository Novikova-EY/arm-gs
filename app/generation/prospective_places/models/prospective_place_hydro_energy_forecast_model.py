# -*- coding: utf-8 -*-
"""
Помесячный прогноз выработки ЭЭ для перспективных площадок ГЭС/ГАЭС
и карточки станции тех же типов (календарный год январь-декабрь;
сценарии маловодья 95% / средневодья 50%).
"""
from sqlalchemy.sql import func, text
from sqlalchemy import Numeric, CheckConstraint, Index
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin

HYDRO_MONTH_ORDER = tuple(range(1, 13))
HYDRO_MONTH_NAMES = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}

SCENARIO_LOW_95 = "low_95"
SCENARIO_MEDIUM_50 = "medium_50"
HYDRO_SCENARIOS = (
    (SCENARIO_LOW_95, "Маловодные условия. Обеспеченность 95%"),
    (SCENARIO_MEDIUM_50, "Средневодные условия. Обеспеченность 50%"),
)

PLACE_KIND_GES = "ges"
PLACE_KIND_GAES = "gaes"
PLACE_KIND_STATION = "station"


class ProspectivePlaceHydroEnergyForecast(db.Model, AuditMixin):
    __tablename__ = "gs_gen_prospective_place_hydro_energy_forecasts"
    __table_args__ = (
        Index("ix_pp_hydro_forecast_place", "place_kind", "place_id"),
        Index("ix_pp_hydro_forecast_scenario", "scenario"),
        Index("ix_pp_hydro_forecast_month", "month_number"),
        Index(
            "uq_pp_hydro_forecast_place_scenario_month_ver",
            "place_kind",
            "place_id",
            "scenario",
            "month_number",
            text("COALESCE(database_version_id, -1)"),
            unique=True,
        ),
        CheckConstraint(
            "place_kind IN ('ges', 'gaes', 'station')",
            name="ck_pp_hydro_forecast_place_kind",
        ),
        CheckConstraint(
            "scenario IN ('low_95', 'medium_50')",
            name="ck_pp_hydro_forecast_scenario",
        ),
        CheckConstraint(
            "month_number BETWEEN 1 AND 12",
            name="ck_pp_hydro_forecast_month",
        ),
        {"schema": SCHEMA_GENERATION},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    place_kind = db.Column(db.String(8), nullable=False, index=True)
    place_id = db.Column(db.Integer, nullable=False, index=True)
    scenario = db.Column(db.String(16), nullable=False, index=True)
    month_number = db.Column(db.Integer, nullable=False, index=True)

    electricity_generation = db.Column(Numeric(25, 16), nullable=True)

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
            f"<ProspectivePlaceHydroEnergyForecast "
            f"{self.place_kind}:{self.place_id} {self.scenario} m{self.month_number} "
            f"gen={self.electricity_generation}>"
        )

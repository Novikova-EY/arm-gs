# -*- coding: utf-8 -*-
"""Электроёмкость по годам для РФ в целом (долгосрочный прогноз)."""
from sqlalchemy import Numeric, String
from sqlalchemy.sql import func

from app.extensions import db
from app.common.models.audit_mixin import AuditMixin
from config import SCHEMA_ELECTRICAL_INTENSITY, SCHEMA_REFDATA


class RussiaFederationElectricalIntensityYearParameter(db.Model, AuditMixin):
    __tablename__ = "gs_ei_russia_federation_electrical_intensity_year_params"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["year_number", "database_version_id"],
            [
                f"{SCHEMA_REFDATA}.gs_sys_years.number",
                f"{SCHEMA_REFDATA}.gs_sys_years.database_version_id",
            ],
            ondelete="RESTRICT",
            name="fk_ei_rf_ei_y_year_ver",
        ),
        {"schema": SCHEMA_ELECTRICAL_INTENSITY},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Тип строки показателя (intensity, graph_point, calculated, delta)
    row_kind = db.Column(String(32), nullable=False, index=True)
    year_number = db.Column(db.Integer, nullable=True, index=True)
    year = db.relationship(
        "Year",
        back_populates="rf_electrical_intensity_year_parameters",
        lazy="noload",
    )
    # Значение показателя за год (кВтч/тыс. руб., зависит от row_kind)
    parameter_value = db.Column(Numeric(25, 10), nullable=True)
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
            f"<RussiaFederationElectricalIntensityYearParameter id={self.id} "
            f"kind={self.row_kind} year={self.year_number}>"
        )

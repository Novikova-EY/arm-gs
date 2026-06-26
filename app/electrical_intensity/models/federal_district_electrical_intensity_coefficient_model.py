# -*- coding: utf-8 -*-
"""Коэффициенты A и X электроёмкости для федерального округа."""
from sqlalchemy import Numeric
from sqlalchemy.sql import func

from app.extensions import db
from app.common.models.audit_mixin import AuditMixin
from config import SCHEMA_ELECTRICAL_INTENSITY, SCHEMA_REFDATA


class FederalDistrictElectricalIntensityCoefficient(db.Model, AuditMixin):
    __tablename__ = "gs_ei_federal_district_electrical_intensity_coefficients"
    __table_args__ = {"schema": SCHEMA_ELECTRICAL_INTENSITY}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    id_federal_district = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_federal_districts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    federal_district = db.relationship(
        "FederalDistrict",
        foreign_keys=[id_federal_district],
    )

    id_economic_activity_type = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_economic_activity_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    economic_activity_type = db.relationship(
        "EconomicActivityType",
        foreign_keys=[id_economic_activity_type],
    )

    coefficient_a = db.Column(Numeric(25, 16), nullable=True)
    coefficient_x = db.Column(Numeric(25, 16), nullable=True)
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
            f"<FederalDistrictElectricalIntensityCoefficient id={self.id} "
            f"fd={self.id_federal_district} ved={self.id_economic_activity_type}>"
        )

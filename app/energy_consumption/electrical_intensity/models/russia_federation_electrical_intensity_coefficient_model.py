# -*- coding: utf-8 -*-
"""Коэффициенты A и X электроёмкости для РФ в целом."""
from sqlalchemy import Numeric
from sqlalchemy.sql import func

from app.extensions import db
from app.common.models.audit_mixin import AuditMixin
from config import SCHEMA_ENERGY_CONSUMPTION, SCHEMA_REFDATA


class RussiaFederationElectricalIntensityCoefficient(db.Model, AuditMixin):
    __tablename__ = "gs_ec_russia_federation_electrical_intensity_coefficients"
    __table_args__ = {"schema": SCHEMA_ENERGY_CONSUMPTION}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

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
        return f"<RussiaFederationElectricalIntensityCoefficient id={self.id}>"

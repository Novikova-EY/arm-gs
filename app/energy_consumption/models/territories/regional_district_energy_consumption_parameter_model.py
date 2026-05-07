# -*- coding: utf-8 -*-
"""Параметры потребления для субъекта РФ."""
from sqlalchemy import Numeric
from sqlalchemy.sql import func

from app.extensions import db
from app.common.models.audit_mixin import AuditMixin
from config import SCHEMA_ENERGY_CONSUMPTION, SCHEMA_REFDATA


class RegionalDistrictEnergyConsumptionParameter(db.Model, AuditMixin):
    __tablename__ = "gs_ec_regional_district_consumption_params"
    __table_args__ = {"schema": SCHEMA_ENERGY_CONSUMPTION}


    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    id_regional_district = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_regional_districts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    regional_district = db.relationship(
        "RegionalDistrict",
        foreign_keys=[id_regional_district],
    )


    year_number = db.Column(db.Integer, nullable=True, index=True)

    energy_consumption_mln_kvt_ch = db.Column(Numeric(25, 16), nullable=True)

    energy_consumption_sipr_mln_kvt_ch = db.Column(Numeric(25, 16), nullable=True)

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
            f"<RegionalDistrictEnergyConsumptionParameter(ec) id={self.id} "
            f"regional_district_id={self.id_regional_district} "
            f"year={self.year_number}>"
        )

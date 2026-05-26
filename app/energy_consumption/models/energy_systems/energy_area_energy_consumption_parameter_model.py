# -*- coding: utf-8 -*-
"""Параметры потребления для энергорайона (EnergyArea)."""
from sqlalchemy import Numeric
from sqlalchemy.sql import func

from app.extensions import db
from app.common.models.audit_mixin import AuditMixin
from app.common.models.perimeter_variant_mixin import PerimeterVariantColumnMixin
from config import SCHEMA_ENERGY_CONSUMPTION, SCHEMA_REFDATA


class EnergyAreaEnergyConsumptionParameter(db.Model, AuditMixin, PerimeterVariantColumnMixin):
    __tablename__ = "gs_ec_energy_area_consumption_params"
    __table_args__ = {"schema": SCHEMA_ENERGY_CONSUMPTION}


    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    id_energy_area = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_energy_areas.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    energy_area = db.relationship(
        "EnergyArea",
        foreign_keys=[id_energy_area],
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
            f"<EnergyAreaEnergyConsumptionParameter(ec) id={self.id} "
            f"energy_area_id={self.id_energy_area} "
            f"year={self.year_number}>"
        )

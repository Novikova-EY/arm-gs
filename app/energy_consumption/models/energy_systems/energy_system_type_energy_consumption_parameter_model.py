# -*- coding: utf-8 -*-
"""Параметры потребления для типа энергосистемы."""
from sqlalchemy import Numeric
from sqlalchemy.sql import func

from app.extensions import db
from app.common.models.audit_mixin import AuditMixin
from config import SCHEMA_ENERGY_CONSUMPTION, SCHEMA_REFDATA


class EnergySystemTypeEnergyConsumptionParameter(db.Model, AuditMixin):
    __tablename__ = "gs_ec_energy_system_type_consumption_params"
    __table_args__ = {"schema": SCHEMA_ENERGY_CONSUMPTION}


    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    id_energy_system_type = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_energy_system_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    energy_system_type = db.relationship(
        "EnergySystemType",
        foreign_keys=[id_energy_system_type],
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
            f"<EnergySystemTypeEnergyConsumptionParameter(ec) id={self.id} "
            f"energy_system_type_id={self.id_energy_system_type} "
            f"year={self.year_number}>"
        )

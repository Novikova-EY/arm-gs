# -*- coding: utf-8 -*-
"""Параметры потребления электроэнергии для централизованной зоны (агрегат без FK)."""
from sqlalchemy import Numeric
from sqlalchemy.sql import func

from app.extensions import db
from app.common.models.audit_mixin import AuditMixin
from config import SCHEMA_ENERGY_CONSUMPTION, SCHEMA_REFDATA


class CentralizedZoneEnergyConsumptionParameter(db.Model, AuditMixin):
    __tablename__ = "gs_ec_centralized_zone_consumption_params"
    __table_args__ = {"schema": SCHEMA_ENERGY_CONSUMPTION}


    id = db.Column(db.Integer, primary_key=True, autoincrement=True)


    # Год
    year_number = db.Column(db.Integer, nullable=True, index=True)

    # Потребление электрической энергии, млн кВт·ч
    energy_consumption_mln_kvt_ch = db.Column(Numeric(25, 16), nullable=True)

    # Потребление электрической энергии (СиПР), млн кВт·ч
    energy_consumption_sipr_mln_kvt_ch = db.Column(Numeric(25, 16), nullable=True)

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
            f"<CentralizedZoneEnergyConsumptionParameter(ec) id={self.id} "
            f"year={self.year_number}>"
        )

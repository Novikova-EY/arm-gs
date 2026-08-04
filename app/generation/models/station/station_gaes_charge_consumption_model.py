# -*- coding: utf-8 -*-
"""
StationGaesChargeConsumption — потребление электрической энергии ГАЭС на заряд по годам (млн кВтч).
year_number без FK: у справочника годов составной ключ (number, database_version_id).
"""
from sqlalchemy.sql import func
from sqlalchemy import Numeric
from sqlalchemy.schema import Index
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin
from app.generation.models.common.version_year_unique_index import version_year_unique_index


class StationGaesChargeConsumption(db.Model, AuditMixin):
    __tablename__ = "gs_gen_station_gaes_charge_consumptions"
    __table_args__ = (
        Index("ix_station_gaes_charge_id_station", "id_station"),
        Index("ix_station_gaes_charge_year_number", "year_number"),
        Index("ix_station_gaes_charge_station_year", "id_station", "year_number"),
        version_year_unique_index("uq_station_gaes_charge_station_year_ver", "id_station"),
        {"schema": SCHEMA_GENERATION},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    year_number = db.Column(db.Integer, nullable=True, index=True)

    id_station = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.gs_gen_stations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    station = db.relationship("Station", back_populates="station_gaes_charge_consumptions")

    # Потребление на заряд, млн кВтч
    charge_consumption = db.Column(Numeric(25, 16))

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<StationGaesChargeConsumption id={self.id} station_id={self.id_station} "
            f"year={self.year_number} charge={self.charge_consumption}>"
        )

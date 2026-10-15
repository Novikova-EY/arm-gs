# -*- coding: utf-8 -*-
"""Потребление электроэнергии электростанциями типа СНЭЭ по годам, млн кВтч."""
from sqlalchemy.sql import func
from sqlalchemy import Numeric
from sqlalchemy.schema import Index
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin
from app.generation.models.common.version_year_unique_index import version_year_unique_index


class StationSneeEnergyConsumption(db.Model, AuditMixin):
    __tablename__ = "gs_gen_station_snee_energy_consumptions"
    __table_args__ = (
        Index("ix_station_snee_energy_consumption_id_station", "id_station"),
        Index("ix_station_snee_energy_consumption_year_number", "year_number"),
        Index("ix_station_snee_energy_consumption_station_year", "id_station", "year_number"),
        version_year_unique_index(
            "uq_station_snee_energy_consumption_station_year_ver", "id_station"
        ),
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
    station = db.relationship("Station", back_populates="station_snee_energy_consumptions")
    electricity_consumption = db.Column(Numeric(25, 16))
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
            f"<StationSneeEnergyConsumption id={self.id} station_id={self.id_station} "
            f"year={self.year_number} consumption={self.electricity_consumption}>"
        )

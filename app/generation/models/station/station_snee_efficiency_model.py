# -*- coding: utf-8 -*-
"""КПД электростанции СНЭЭ, заданный для версии базы данных."""
from sqlalchemy import Index, Numeric, text
from sqlalchemy.sql import func

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA


class StationSneeEfficiency(db.Model, AuditMixin):
    __tablename__ = "gs_gen_station_snee_efficiencies"
    __table_args__ = (
        Index(
            "uq_station_snee_efficiency_station_ver",
            "id_station",
            text("COALESCE(database_version_id, -1)"),
            unique=True,
        ),
        {"schema": SCHEMA_GENERATION},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_station = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.gs_gen_stations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    efficiency_percent = db.Column(Numeric(25, 16), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

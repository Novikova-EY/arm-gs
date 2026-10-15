# -*- coding: utf-8 -*-
"""Коэффициенты собственных нужд станций ГЭС и ГАЭС для баланса ЭЭ."""
from sqlalchemy import Index, Numeric, text
from sqlalchemy.sql import func

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_ENERGY_BALANCE, SCHEMA_GENERATION, SCHEMA_REFDATA


class EeBalanceStationOwnNeedsCoefficient(db.Model, AuditMixin):
    __tablename__ = "gs_bem_ee_balance_station_own_needs_coefficients"
    __table_args__ = (
        Index("ix_ee_bal_own_needs_station", "id_station"),
        Index("ix_ee_bal_own_needs_type", "station_type_key"),
        Index("ix_ee_bal_own_needs_dbver", "database_version_id"),
        Index(
            "uq_ee_bal_own_needs_station_type_ver",
            "id_station",
            "station_type_key",
            text("COALESCE(database_version_id, -1)"),
            unique=True,
        ),
        {"schema": SCHEMA_ENERGY_BALANCE},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_station = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.gs_gen_stations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    station_type_key = db.Column(db.String(8), nullable=False)
    coefficient = db.Column(Numeric(25, 16), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
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

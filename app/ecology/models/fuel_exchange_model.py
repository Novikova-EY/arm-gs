"""Принятые показатели и пакеты передачи из модуля «Топливо»."""
from sqlalchemy.sql import func

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_ECOLOGY, SCHEMA_REFDATA


class EcologyFuelSnapshot(db.Model, AuditMixin):
    __tablename__ = "gs_eco_fuel_snapshots"
    __table_args__ = (
        db.UniqueConstraint("database_version_id", "year_number", "scope", name="uq_eco_fuel_snapshot_version_year_scope"),
        {"schema": SCHEMA_ECOLOGY},
    )

    id = db.Column(db.Integer, primary_key=True)
    database_version_id = db.Column(db.Integer, db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="CASCADE"), nullable=False)
    year_number = db.Column(db.Integer, nullable=False)
    scope = db.Column(db.String(20), nullable=False, default="operating", server_default="operating")
    payload = db.Column(db.JSON, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class EcologyFuelSubmission(db.Model, AuditMixin):
    __tablename__ = "gs_eco_fuel_submissions"
    __table_args__ = (
        db.Index("ix_eco_fuel_submission_version_year_scope_status", "database_version_id", "year_number", "scope", "status"),
        {"schema": SCHEMA_ECOLOGY},
    )

    id = db.Column(db.Integer, primary_key=True)
    database_version_id = db.Column(db.Integer, db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="CASCADE"), nullable=False)
    year_number = db.Column(db.Integer, nullable=False)
    scope = db.Column(db.String(20), nullable=False, default="operating", server_default="operating")
    payload = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)

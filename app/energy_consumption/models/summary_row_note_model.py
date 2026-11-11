from sqlalchemy.sql import func

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_ENERGY_CONSUMPTION


class EnergyConsumptionSummaryRowNote(db.Model, AuditMixin):
    __tablename__ = "gs_ec_summary_row_notes"
    __table_args__ = (
        db.UniqueConstraint("database_version_id", "row_key", name="uq_ec_summary_row_note_version_key"),
        {"schema": SCHEMA_ENERGY_CONSUMPTION},
    )

    id = db.Column(db.Integer, primary_key=True)
    # Legacy installations expose database versions through a compatibility view.
    database_version_id = db.Column(db.Integer, nullable=False)
    row_key = db.Column(db.String(64), nullable=False)
    note = db.Column(db.Text, nullable=False, default="", server_default="")
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )

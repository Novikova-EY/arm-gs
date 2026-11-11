from sqlalchemy import Index, UniqueConstraint

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_RATIONAL_STRUCTURE, SCHEMA_REFDATA


class TechnicalInspectionCode(db.Model, AuditMixin):
    __tablename__ = "gs_rs_technical_inspection_codes"
    __table_args__ = (
        UniqueConstraint("database_version_id", "equipment_code", name="uq_rs_inspection_code_version"),
        Index("ix_rs_inspection_codes_machine_id", "machine_id"),
        Index("ix_rs_inspection_codes_pgu_machine_id", "pgu_machine_id"),
        {"schema": SCHEMA_RATIONAL_STRUCTURE},
    )

    id = db.Column(db.Integer, primary_key=True)
    database_version_id = db.Column(db.Integer, db.ForeignKey(
        f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="CASCADE"), nullable=False)
    equipment_code = db.Column(db.String(100), nullable=False)
    machine_id = db.Column(db.Integer, db.ForeignKey(
        f"{SCHEMA_GENERATION}.gs_gen_machines.id", ondelete="CASCADE"), nullable=False)
    pgu_machine_id = db.Column(db.Integer, db.ForeignKey(
        f"{SCHEMA_GENERATION}.gs_gen_pgu_machines.id", ondelete="CASCADE"))

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_RATIONAL_STRUCTURE, SCHEMA_REFDATA


class TerritoryInput(db.Model, AuditMixin):
    __tablename__ = "gs_rs_territory_inputs"
    __table_args__ = (
        db.UniqueConstraint("database_version_id", "energy_zone_id", name="uq_rs_territory_input_version_zone"),
        {"schema": SCHEMA_RATIONAL_STRUCTURE},
    )

    id = db.Column(db.Integer, primary_key=True)
    database_version_id = db.Column(db.Integer, db.ForeignKey(
        f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="CASCADE"), nullable=False)
    energy_zone_id = db.Column(db.Integer, db.ForeignKey(
        f"{SCHEMA_REFDATA}.gs_sys_energy_zones.id", ondelete="CASCADE"), nullable=False)
    years = db.Column(db.JSON, nullable=False)
    rows = db.Column(db.JSON, nullable=False)
    source_filename = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           server_default=db.func.now(), onupdate=db.func.now())

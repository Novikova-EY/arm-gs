from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_RATIONAL_STRUCTURE, SCHEMA_REFDATA


class TerritoryDiscountRate(db.Model, AuditMixin):
    __tablename__ = "gs_rs_territory_discount_rates"
    __table_args__ = {"schema": SCHEMA_RATIONAL_STRUCTURE}

    database_version_id = db.Column(db.Integer, db.ForeignKey(
        f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="CASCADE"), primary_key=True)
    year_values = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           server_default=db.func.now(), onupdate=db.func.now())

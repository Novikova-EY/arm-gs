from sqlalchemy import func

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_RATIONAL_STRUCTURE, SCHEMA_REFDATA


class CalculationWorkbook(db.Model, AuditMixin):
    """Сохраненные результаты расчетной книги в конкретной версии ГС."""

    __tablename__ = "gs_rs_calculation_workbooks"
    __table_args__ = (
        db.UniqueConstraint("database_version_id", "kind", name="uq_rs_calculation_workbook_version_kind"),
        db.CheckConstraint("kind IN ('equipment_runtime', 'marginal_price')", name="ck_rs_calculation_workbook_kind"),
        {"schema": SCHEMA_RATIONAL_STRUCTURE},
    )

    id = db.Column(db.Integer, primary_key=True)
    database_version_id = db.Column(db.Integer, db.ForeignKey(
        f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = db.Column(db.String(30), nullable=False)
    source_filename = db.Column(db.Text, nullable=False)
    source_sha256 = db.Column(db.String(64), nullable=False)
    data = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

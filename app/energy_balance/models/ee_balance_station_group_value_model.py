"""Параметры групп станций только для технологических страниц баланса ЭЭ."""
from sqlalchemy import Index, text

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_ENERGY_BALANCE, SCHEMA_GENERATION


class EeBalanceStationGroupValue(db.Model, AuditMixin):
    __tablename__ = "gs_bem_ee_balance_station_group_values"
    __table_args__ = (
        Index("ix_ee_balance_group_version", "database_version_id"),
        Index("uq_ee_balance_group_page_year_version", "id_station_group", "page_key",
              "year_number", text("COALESCE(database_version_id, -1)"), unique=True),
        db.CheckConstraint("page_key IN ('aes', 'ges', 'ses-ves')", name="ck_ee_balance_group_page"),
        {"schema": SCHEMA_ENERGY_BALANCE},
    )

    id = db.Column(db.Integer, primary_key=True)
    id_station_group = db.Column(db.Integer, db.ForeignKey(
        f"{SCHEMA_GENERATION}.gs_gen_station_groups.id", ondelete="CASCADE"), nullable=False)
    page_key = db.Column(db.String(16), nullable=False)
    year_number = db.Column(db.Integer, nullable=False)
    energy = db.Column(db.Numeric(25, 16))
    own_needs = db.Column(db.Numeric(25, 16))
    own_needs_percent = db.Column(db.Numeric(25, 16))
    database_version_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(),
                           onupdate=db.func.now(), nullable=False)

# -*- coding: utf-8 -*-
"""Помесячный ввод расчёта прогнозной выработки ТЭС (Магадан)."""
from sqlalchemy.sql import func
from sqlalchemy import Index, Numeric, text

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_ENERGY_BALANCE


class EeBalanceTesMonthlyValue(db.Model, AuditMixin):
    __tablename__ = "gs_bem_ee_balance_tes_monthly_values"
    __table_args__ = (
        Index("ix_gs_bem_eb_tes_m_sheet", "sheet_slug"),
        Index("ix_gs_bem_eb_tes_m_row", "row_key"),
        Index("ix_gs_bem_eb_tes_m_year", "year_number"),
        Index("ix_gs_bem_eb_tes_m_month", "month_number"),
        Index("ix_gs_bem_eb_tes_m_dbver", "database_version_id"),
        Index(
            "uq_gs_bem_eb_tes_m_sheet_row_year_month_ver",
            "sheet_slug",
            "row_key",
            "year_number",
            "month_number",
            text("COALESCE(database_version_id, -1)"),
            unique=True,
        ),
        {"schema": SCHEMA_ENERGY_BALANCE},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sheet_slug = db.Column(db.String(128), nullable=False, index=True)
    row_key = db.Column(db.String(80), nullable=False, index=True)
    year_number = db.Column(db.Integer, nullable=False, index=True)
    month_number = db.Column(db.Integer, nullable=False, index=True)
    value_mln_kvtch = db.Column(Numeric(25, 16), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    database_version_id = db.Column(db.Integer, nullable=True, index=True)

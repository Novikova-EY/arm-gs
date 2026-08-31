# -*- coding: utf-8 -*-
"""Ручное примечание строки листа баланса мощности или электрической энергии."""
from sqlalchemy.sql import func
from sqlalchemy import Index, text

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_ENERGY_BALANCE

BALANCE_KIND_POWER = "power"
BALANCE_KIND_EE = "ee"
NOTE_MAX_LENGTH = 4000
ROW_KEY_MAX_LENGTH = 256


class BalanceSheetNote(db.Model, AuditMixin):
    __tablename__ = "gs_bem_balance_row_notes"
    __table_args__ = (
        Index("ix_gs_bem_bal_row_note_sheet", "sheet_slug"),
        Index("ix_gs_bem_bal_row_note_kind", "balance_kind"),
        Index("ix_gs_bem_bal_row_note_dbver", "database_version_id"),
        Index(
            "uq_gs_bem_bal_row_note_sheet_kind_key_ver",
            "sheet_slug",
            "balance_kind",
            "row_key",
            text("COALESCE(database_version_id, -1)"),
            unique=True,
        ),
        {"schema": SCHEMA_ENERGY_BALANCE},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sheet_slug = db.Column(db.String(128), nullable=False, index=True)
    balance_kind = db.Column(db.String(16), nullable=False, index=True)
    row_key = db.Column(db.String(ROW_KEY_MAX_LENGTH), nullable=False, index=True)
    note_text = db.Column(db.Text, nullable=False, default="", server_default="")

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    database_version_id = db.Column(db.Integer, nullable=True, index=True)

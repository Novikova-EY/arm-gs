# -*- coding: utf-8 -*-
"""Переопределения текстов формул для накопленных инвестиций в основной капитал."""

from sqlalchemy.sql import func

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_ECONOMICS


class AccumFixedCapitalFormulaText(db.Model, AuditMixin):
    __tablename__ = "gs_ekp_accum_fixed_capital_formula_texts"
    __table_args__ = (
        db.UniqueConstraint("formula_key", name="uq_gs_ekp_afci_formula_texts_key"),
        {"schema": SCHEMA_ECONOMICS},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    formula_key = db.Column(db.String(128), nullable=False, index=True)
    formula_text = db.Column(db.Text, nullable=False)

    created_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<AccumFixedCapitalFormulaText {self.formula_key!r}>"

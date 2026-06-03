# -*- coding: utf-8 -*-
"""Переопределения текстов формул (подсказки «i») для сводок потребления ЭЭ."""

from sqlalchemy.sql import func

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_ENERGY_CONSUMPTION


class EnergyConsumptionSummaryFormulaText(db.Model, AuditMixin):
    """Только текст формулы; расчёт значений ячеек не меняется."""

    __tablename__ = "gs_ec_summary_formula_texts"
    __table_args__ = (
        db.UniqueConstraint("formula_key", name="uq_gs_ec_summary_formula_texts_key"),
        {"schema": SCHEMA_ENERGY_CONSUMPTION},
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
        return f"<EnergyConsumptionSummaryFormulaText {self.formula_key!r}>"

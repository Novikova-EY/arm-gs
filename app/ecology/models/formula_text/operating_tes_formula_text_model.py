# -*- coding: utf-8 -*-
"""Переопределения текстов формул (подсказки «i») расчёта по действующим ТЭС."""

from sqlalchemy.sql import func

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_ECOLOGY


class OperatingTesFormulaText(db.Model, AuditMixin):
    """Только текст формулы; расчёт значений ячеек не меняется."""

    __tablename__ = "gs_eco_operating_tes_formula_texts"
    __table_args__ = (
        db.UniqueConstraint("formula_key", name="uq_gs_eco_operating_tes_formula_texts_key"),
        {"schema": SCHEMA_ECOLOGY},
    )

    # Уникальный идентификатор записи
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # Ключ формулы (иконка «i» на страницах расчёта)
    formula_key = db.Column(db.String(128), nullable=False, index=True)
    # Текст формулы (подсказка; на расчёт ячеек не влияет)
    formula_text = db.Column(db.Text, nullable=False)

    # Дата и время создания записи
    created_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Дата и время последнего изменения записи
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<OperatingTesFormulaText {self.formula_key!r}>"

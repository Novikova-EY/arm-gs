# -*- coding: utf-8 -*-
"""Тексты формул долгосрочного прогноза по ВЭД."""

from __future__ import annotations

from typing import Any

from flask import g

from app.economics.models.formula_text.consumption_formula_text_model import (
    ConsumptionFormulaText,
)
from app.extensions import db
from app.economics.services.ved_consumption_formula_registry import (
    VedConsumptionFormulaDef,
    get_formula_def,
    iter_formula_defs,
)

_OVERRIDE_CACHE_KEY = "lt_ved_formula_text_overrides"


def _load_overrides_from_db() -> dict[str, str]:
    rows = ConsumptionFormulaText.query.all()
    return {str(r.formula_key): str(r.formula_text or "") for r in rows}


def clear_formula_text_override_cache() -> None:
    if hasattr(g, _OVERRIDE_CACHE_KEY):
        delattr(g, _OVERRIDE_CACHE_KEY)


def get_formula_text_overrides() -> dict[str, str]:
    cached = getattr(g, _OVERRIDE_CACHE_KEY, None)
    if cached is not None:
        return cached
    try:
        overrides = _load_overrides_from_db()
    except Exception:
        overrides = {}
    setattr(g, _OVERRIDE_CACHE_KEY, overrides)
    return overrides


def ved_formula_text(formula_key: str, default: str | None = None) -> str:
    overrides = get_formula_text_overrides()
    if formula_key in overrides and overrides[formula_key].strip():
        return overrides[formula_key]
    if default is not None:
        return default
    item = get_formula_def(formula_key)
    return item.default_text if item else ""


def list_formulas_for_admin() -> list[dict[str, Any]]:
    overrides = get_formula_text_overrides()
    rows: list[dict[str, Any]] = []
    for item in iter_formula_defs():
        rows.append(
            {
                "formula_key": item.key,
                "page": item.page,
                "row_label": item.row_label,
                "default_text": item.default_text,
                "formula_text": overrides.get(item.key, item.default_text),
                "is_overridden": item.key in overrides,
            }
        )
    return rows


def save_formula_text_override(*, formula_key: str, formula_text: str) -> None:
    key = str(formula_key or "").strip()
    if not get_formula_def(key):
        raise ValueError(f"Неизвестный ключ формулы: {key}")
    text = str(formula_text or "").strip()
    if not text:
        raise ValueError("Текст формулы не может быть пустым.")
    row = ConsumptionFormulaText.query.filter_by(formula_key=key).first()
    if row is None:
        row = ConsumptionFormulaText(formula_key=key, formula_text=text)
        db.session.add(row)
    else:
        row.formula_text = text
    clear_formula_text_override_cache()


def reset_formula_text_override(formula_key: str) -> None:
    key = str(formula_key or "").strip()
    row = ConsumptionFormulaText.query.filter_by(formula_key=key).first()
    if row is not None:
        db.session.delete(row)
    clear_formula_text_override_cache()

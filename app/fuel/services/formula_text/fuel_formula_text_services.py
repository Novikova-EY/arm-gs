# -*- coding: utf-8 -*-
"""Тексты формул модуля «Топливо»: чтение переопределений и администрирование."""

from __future__ import annotations

from typing import Any

from flask import g

from app.extensions import db
from app.fuel.models.formula_text.fuel_formula_text_model import FuelFormulaText
from app.fuel.services.formula_text.fuel_formula_text_registry import (
    FUEL_FORMULA_REGISTRY,
    FuelFormulaDef,
    get_formula_def,
    iter_formula_defs,
)

_OVERRIDE_CACHE_KEY = "fue_formula_text_overrides"


def _load_overrides_from_db() -> dict[str, str]:
    rows = FuelFormulaText.query.all()
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


def fuel_formula_text(formula_key: str, default: str | None = None) -> str:
    key = str(formula_key or "").strip()
    overrides = get_formula_text_overrides()
    if key in overrides:
        return overrides[key]
    item = get_formula_def(key)
    if item is not None:
        return item.default_text
    return "" if default is None else str(default)


def _map_for(map_name: str) -> dict[str, str]:
    return {
        item.map_key: fuel_formula_text(item.key)
        for item in iter_formula_defs(map_name=map_name)
    }


def get_consumption_formulas() -> dict[str, str]:
    """Эффективные тексты для consumption_formulas в шаблонах."""
    return _map_for("consumption")


def get_restriction_column_formulas() -> dict[str, str]:
    return _map_for("restriction")


def get_coeff_cell_tooltips() -> dict[str, str]:
    return _map_for("coeff")


def list_formulas_for_admin() -> list[dict[str, Any]]:
    overrides = get_formula_text_overrides()
    rows: list[dict[str, Any]] = []
    for item in FUEL_FORMULA_REGISTRY:
        effective = fuel_formula_text(item.key)
        is_customized = item.key in overrides
        rows.append(
            {
                "key": item.key,
                "page_labels": item.page,
                "page_lines": [item.page],
                "aggregation_level": item.aggregation_level,
                "cell_name": item.cell_name,
                "default_text": item.default_text,
                "formula_text": effective,
                "is_customized": is_customized,
            }
        )
    return rows


def save_formula_text_override(*, formula_key: str, formula_text: str) -> FuelFormulaDef:
    key = str(formula_key or "").strip()
    item = get_formula_def(key)
    if item is None:
        raise ValueError(f"Неизвестный ключ формулы: {key!r}")
    text = str(formula_text or "").strip()
    if not text:
        raise ValueError("Текст формулы не может быть пустым.")
    row = FuelFormulaText.query.filter_by(formula_key=key).first()
    if row is None:
        row = FuelFormulaText(formula_key=key, formula_text=text)
        db.session.add(row)
    else:
        row.formula_text = text
    clear_formula_text_override_cache()
    return item


def reset_formula_text_override(formula_key: str) -> None:
    key = str(formula_key or "").strip()
    if not key:
        return
    FuelFormulaText.query.filter_by(formula_key=key).delete(synchronize_session=False)
    clear_formula_text_override_cache()

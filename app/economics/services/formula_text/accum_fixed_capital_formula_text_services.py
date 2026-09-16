# -*- coding: utf-8 -*-
"""Тексты формул долгосрочного прогноза по накопленному основному капиталу."""

from __future__ import annotations

from typing import Any

from app.common.services.formula_text_override_services import FormulaTextOverrideStore
from app.economics.models.formula_text.accum_fixed_capital_formula_text_model import (
    AccumFixedCapitalFormulaText,
)
from app.economics.services.accum_fixed_capital_formula_registry import (
    AccumFixedCapitalFormulaDef,
    get_formula_def,
    iter_formula_defs,
)

_OVERRIDE_STORE = FormulaTextOverrideStore(
    AccumFixedCapitalFormulaText,
    "lt_afci_formula_text_overrides",
)


def clear_formula_text_override_cache() -> None:
    _OVERRIDE_STORE.clear_cache()


def get_formula_text_overrides() -> dict[str, str]:
    return _OVERRIDE_STORE.get_overrides()


def afci_formula_text(formula_key: str, default: str | None = None) -> str:
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
    _OVERRIDE_STORE.save_override(formula_key=key, formula_text=formula_text)


def reset_formula_text_override(formula_key: str) -> None:
    key = str(formula_key or "").strip()
    _OVERRIDE_STORE.reset_override(key)

# -*- coding: utf-8 -*-
"""Сводное редактирование текстов формул модуля «Экономика»."""

from __future__ import annotations

from typing import Any

from app.economics.services.formula_text import (
    accum_fixed_capital_formula_text_services as afts,
    product_output_formula_text_services as pofts,
    ved_consumption_formula_text_services as vfts,
)

_FORMULA_MODULES: tuple[Any, ...] = (vfts, afts, pofts)

_AGGREGATION_LEVEL = "Строка таблицы (ВЭД)"


def _module_for_key(formula_key: str):
    key = str(formula_key or "").strip()
    if key.startswith("ved_"):
        return vfts
    if key.startswith("afci_"):
        return afts
    if key.startswith("po_"):
        return pofts
    raise ValueError(f"Неизвестный ключ формулы: {key}")


def _row_for_admin(raw: dict[str, Any]) -> dict[str, Any]:
    page = str(raw.get("page") or "").strip()
    page_lines = [page] if page else []
    return {
        "key": raw["formula_key"],
        "page_labels": page,
        "page_lines": page_lines,
        "aggregation_level": _AGGREGATION_LEVEL,
        "cell_name": raw["row_label"],
        "default_text": raw["default_text"],
        "formula_text": raw["formula_text"],
        "is_customized": raw["is_overridden"],
    }


def list_formulas_for_admin() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for module in _FORMULA_MODULES:
        for raw in module.list_formulas_for_admin():
            rows.append(_row_for_admin(raw))
    return rows


def save_formula_text_override(*, formula_key: str, formula_text: str) -> None:
    _module_for_key(formula_key).save_formula_text_override(
        formula_key=formula_key,
        formula_text=formula_text,
    )


def reset_formula_text_override(formula_key: str) -> None:
    _module_for_key(formula_key).reset_formula_text_override(formula_key)

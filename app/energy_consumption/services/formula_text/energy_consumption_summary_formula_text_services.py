# -*- coding: utf-8 -*-
"""Тексты формул сводок: чтение переопределений и администрирование."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from flask import g, has_request_context

from app.energy_consumption.models.formula_text.energy_consumption_summary_formula_text_model import (
    EnergyConsumptionSummaryFormulaText,
)
from app.energy_consumption.services.energy_consumption_summary_formula_registry import (
    EC_SUMMARY_FORMULA_REGISTRY,
    EcSummaryFormulaDef,
    default_text_to_formula_key,
    get_formula_def,
    iter_formula_defs,
)
from app.extensions import db

_OVERRIDE_CACHE_KEY = "ec_summary_formula_text_overrides"
_LEGACY_EI_MIGRATED_KEY = "ec_legacy_ei_formula_texts_migrated"
_LEGACY_EI_MIGRATED_DONE = False


def migrate_legacy_electrical_intensity_formula_texts() -> None:
    """Перенос переопределений из gs_ei_electrical_intensity_formula_texts."""
    global _LEGACY_EI_MIGRATED_DONE
    if has_request_context():
        if getattr(g, _LEGACY_EI_MIGRATED_KEY, False):
            return
        setattr(g, _LEGACY_EI_MIGRATED_KEY, True)
    elif _LEGACY_EI_MIGRATED_DONE:
        return
    try:
        from app.electrical_intensity.models.formula_text.electrical_intensity_formula_text_model import (
            ElectricalIntensityFormulaText,
        )

        legacy_rows = ElectricalIntensityFormulaText.query.all()
        if not legacy_rows:
            return
        keys = [str(r.formula_key) for r in legacy_rows if get_formula_def(str(r.formula_key))]
        if not keys:
            return
        existing = {
            str(r.formula_key)
            for r in EnergyConsumptionSummaryFormulaText.query.filter(
                EnergyConsumptionSummaryFormulaText.formula_key.in_(keys)
            ).all()
        }
        for legacy in legacy_rows:
            key = str(legacy.formula_key)
            if key in existing or not get_formula_def(key):
                continue
            text = str(legacy.formula_text or "").strip()
            if not text:
                continue
            db.session.add(
                EnergyConsumptionSummaryFormulaText(formula_key=key, formula_text=text)
            )
        db.session.commit()
        clear_formula_text_override_cache()
        _LEGACY_EI_MIGRATED_DONE = True
    except Exception:
        db.session.rollback()


def _load_overrides_from_db() -> dict[str, str]:
    rows = EnergyConsumptionSummaryFormulaText.query.all()
    return {str(r.formula_key): str(r.formula_text or "") for r in rows}


def clear_formula_text_override_cache() -> None:
    if hasattr(g, _OVERRIDE_CACHE_KEY):
        delattr(g, _OVERRIDE_CACHE_KEY)


def get_formula_text_overrides() -> dict[str, str]:
    migrate_legacy_electrical_intensity_formula_texts()
    cached = getattr(g, _OVERRIDE_CACHE_KEY, None)
    if cached is not None:
        return cached
    try:
        overrides = _load_overrides_from_db()
    except Exception:
        overrides = {}
    setattr(g, _OVERRIDE_CACHE_KEY, overrides)
    return overrides


def _normalize_formula_text(text: str) -> str:
    return " ".join(str(text or "").split())


@lru_cache(maxsize=1)
def get_default_text_to_formula_key() -> dict[str, str]:
    exact = default_text_to_formula_key()
    normalized: dict[str, str] = {}
    for item in EC_SUMMARY_FORMULA_REGISTRY:
        for candidate in (item.default_text, _normalize_formula_text(item.default_text)):
            if candidate:
                normalized.setdefault(candidate, item.key)
    for raw_text, key in exact.items():
        normalized.setdefault(_normalize_formula_text(raw_text), key)
    return {**exact, **normalized}


def resolve_formula_text_key(
    text: str,
    *,
    preferred_key: str | None = None,
) -> str | None:
    if preferred_key and get_formula_def(str(preferred_key)):
        return str(preferred_key)
    raw = str(text or "").strip()
    if not raw:
        return None
    mapping = get_default_text_to_formula_key()
    return mapping.get(raw) or mapping.get(_normalize_formula_text(raw))


def ec_formula_text(formula_key: str, default: str | None = None) -> str:
    """Эффективный текст формулы: переопределение из БД или значение по умолчанию."""
    definition = get_formula_def(formula_key)
    fallback = default if default is not None else (definition.default_text if definition else "")
    override = get_formula_text_overrides().get(formula_key)
    if override is not None and str(override).strip() != "":
        return str(override).strip()
    return str(fallback).strip()


def build_ec_formula_texts_map() -> dict[str, str]:
    return {item.key: ec_formula_text(item.key) for item in EC_SUMMARY_FORMULA_REGISTRY}


def apply_row_formula_text_overrides(summary_rows: list[dict[str, Any]] | None) -> None:
    if not summary_rows:
        return
    for row in summary_rows:
        for field in ("pd_ec_summary_row_formula_tooltip", "pd_ec_verification_formula_tooltip"):
            raw = row.get(field)
            if not raw:
                continue
            text = str(raw).strip()
            key = resolve_formula_text_key(
                text,
                preferred_key=row.get("pd_ec_formula_text_key"),
            )
            if key:
                row["pd_ec_formula_text_key"] = str(key)
                row[field] = ec_formula_text(str(key), text)


def list_formulas_for_admin(
    *,
    page: str | None = None,
    exclude_page: str | None = None,
) -> list[dict[str, Any]]:
    overrides = get_formula_text_overrides()
    out: list[dict[str, Any]] = []
    for item in iter_formula_defs(page=page, exclude_page=exclude_page):
        effective = ec_formula_text(item.key)
        page_lines = list(item.page_label_lines())
        out.append(
            {
                "key": item.key,
                "page_labels": item.page_labels(),
                "page_lines": page_lines,
                "aggregation_level": item.aggregation_level,
                "cell_name": item.cell_name,
                "default_text": item.default_text,
                "formula_text": effective,
                "is_customized": item.key in overrides,
            }
        )
    return out


def save_formula_text_override(*, formula_key: str, formula_text: str) -> EcSummaryFormulaDef:
    key = str(formula_key or "").strip()
    if not get_formula_def(key):
        raise ValueError(f"Неизвестный ключ формулы: {key}")
    text = str(formula_text or "").strip()
    if not text:
        raise ValueError("Текст формулы не может быть пустым.")
    row = EnergyConsumptionSummaryFormulaText.query.filter_by(formula_key=key).first()
    if row is None:
        row = EnergyConsumptionSummaryFormulaText(formula_key=key, formula_text=text)
        db.session.add(row)
    else:
        row.formula_text = text
    clear_formula_text_override_cache()
    return get_formula_def(key)  # type: ignore[return-value]


def reset_formula_text_override(formula_key: str) -> None:
    key = str(formula_key or "").strip()
    row = EnergyConsumptionSummaryFormulaText.query.filter_by(formula_key=key).first()
    if row is not None:
        db.session.delete(row)
    clear_formula_text_override_cache()

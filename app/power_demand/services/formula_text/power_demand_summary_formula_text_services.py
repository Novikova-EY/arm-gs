# -*- coding: utf-8 -*-
"""Тексты формул сводок нагрузок: чтение переопределений и администрирование."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from flask import g

from app.extensions import db
from app.power_demand.models.formula_text.power_demand_summary_formula_text_model import (
    PowerDemandSummaryFormulaText,
)
from app.power_demand.services.formula_text.pd_summary_formula_row_resolver import (
    resolve_pd_summary_coeff_k_formula_base_key,
    resolve_pd_summary_parameter_formula_base_key,
    resolve_pd_summary_row_formula_key,
)
from app.power_demand.services.power_demand_summary_formula_registry import (
    PD_SUMMARY_FORMULA_REGISTRY,
    PdSummaryFormulaDef,
    default_text_to_formula_key,
    get_formula_def,
    iter_formula_defs,
)

_OVERRIDE_CACHE_KEY = "pd_summary_formula_text_overrides"

# Переименованные ключи формул (сохранённые переопределения в БД).
# Значение — старый ключ в БД, откуда читать переопределение для нового ключа.
_LEGACY_FORMULA_KEY_FALLBACKS: dict[str, str] = {
    "sa_first_calc_max_power_mw_without_nt": "sa_first_calc_max_power_mw",
    "sa_second_calc_max_power_mw": "sa_second_calc_max_power_mw_oes",
    "sa_first_verify_max_power_without_nt": "sa_verify_max_power",
    "sa_first_calc_max_sa_mw_without_nt": "sa_calc_max_mw",
    "sa_first_verify_combined_ees_without_nt": "sa_verify_combined_ees",
    "sa_second_verify_max_power": "sa_verify_max_power",
    "sa_second_calc_max_sa_mw": "sa_calc_max_mw",
    "sa_second_verify_combined_ees": "sa_verify_combined_ees",
    "sa_kaliningrad_verify_max_power": "sa_verify_max_power",
    "sa_kaliningrad_calc_max_sa_mw": "sa_calc_max_mw",
    "sa_kaliningrad_verify_combined_ees": "sa_verify_combined_ees",
    "oes_ues_calc_max_oes_mw_without_nt": "oes_ues_calc_max_oes_mw",
    "oes_ues_calc_combined_ees_mw_without_nt": "oes_ues_calc_combined_ees_mw",
    "oes_ees_russia_calc_max_via_oes_without_nt": "oes_ees_russia_calc_max_via_oes",
    "oes_ees_russia_calc_max_via_es_without_nt": "oes_ees_russia_calc_max_via_es",
    "oes_ees_russia_calc_max_without_nt": "oes_ees_russia_calc_max",
    "ees_russia_verify_calc_max_without_nt": "ees_russia_verify_calc_max",
    "ees_russia_verify_calc_max_via_oes_without_nt": "ees_russia_verify_calc_max_via_oes",
    "ees_russia_verify_calc_max_via_es_without_nt": "ees_russia_verify_calc_max_via_es",
    "oes_ees_calc_max_power_consumption_without_nt": "oes_ees_calc_max_power_consumption",
    "sa_first_verify_max_power_without_nt": "sa_first_verify_max_power",
    "sa_first_calc_max_sa_mw_without_nt": "sa_first_calc_max_sa_mw",
    "sa_first_verify_combined_ees_without_nt": "sa_first_verify_combined_ees",
    "oes_verify_calc_max_mw_without_nt": "oes_verify_calc_max_mw",
    "oes_verify_combined_ees_mw_without_nt": "oes_verify_combined_ees_mw",
    "fo_verify_calc_max_mw_without_nt": "fo_verify_calc_max_mw",
    "fo_verify_combined_on_cz_mw_without_nt": "fo_verify_combined_on_cz_mw",
    "fo_verify_combined_ees_mw_without_nt": "fo_verify_combined_ees_mw",
    "coeff_k_ues_calc_max_oes_without_nt": "coeff_k_ues_calc_max_oes",
    "coeff_k_ues_combined_ees_without_nt": "coeff_k_ues_combined_ees",
    "coeff_k_ues_calc_combined_ees_without_nt": "coeff_k_ues_calc_combined_ees",
    "coeff_k_calculated_max_ees_via_oes_without_nt": "coeff_k_calculated_max_ees_via_oes",
    "coeff_k_calculated_max_ees_via_es_without_nt": "coeff_k_calculated_max_ees_via_es",
}


def _load_overrides_from_db() -> dict[str, str]:
    rows = PowerDemandSummaryFormulaText.query.all()
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


def _normalize_formula_text(text: str) -> str:
    return " ".join(str(text or "").split())


@lru_cache(maxsize=1)
def get_default_text_to_formula_key() -> dict[str, str]:
    exact = default_text_to_formula_key()
    normalized: dict[str, str] = {}
    for item in PD_SUMMARY_FORMULA_REGISTRY:
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


def pd_formula_text(formula_key: str, default: str | None = None) -> str:
    """Эффективный текст формулы: переопределение из БД или значение по умолчанию."""
    definition = get_formula_def(formula_key)
    fallback = default if default is not None else (definition.default_text if definition else "")
    overrides = get_formula_text_overrides()
    override = overrides.get(formula_key)
    if override is None or str(override).strip() == "":
        legacy_key = _LEGACY_FORMULA_KEY_FALLBACKS.get(formula_key)
        if legacy_key:
            override = overrides.get(legacy_key)
    if override is not None and str(override).strip() != "":
        return str(override).strip()
    return str(fallback).strip()


def build_pd_formula_texts_map() -> dict[str, str]:
    return {item.key: pd_formula_text(item.key) for item in PD_SUMMARY_FORMULA_REGISTRY}


def apply_row_formula_text_overrides(summary_rows: list[dict[str, Any]] | None) -> None:
    if not summary_rows:
        return
    for row in summary_rows:
        for field in ("pd_fo_cz_calc_max_tooltip", "pd_fo_coeff_cz_total_tooltip"):
            raw = row.get(field)
            if not raw:
                continue
            text = str(raw).strip()
            key = resolve_formula_text_key(
                text,
                preferred_key=row.get("pd_formula_text_key"),
            )
            if key:
                row["pd_formula_text_key"] = str(key)
                row[field] = pd_formula_text(str(key), text)

        param_base = resolve_pd_summary_parameter_formula_base_key(row)
        param_key = resolve_pd_summary_row_formula_key(row, base_key=param_base)
        if param_key:
            row["pd_formula_text_key"] = param_key
            row["pd_parameter_formula_tooltip"] = pd_formula_text(param_key)

        coeff_base = resolve_pd_summary_coeff_k_formula_base_key(row)
        coeff_key = resolve_pd_summary_row_formula_key(row, base_key=coeff_base)
        if coeff_key:
            row["pd_coeff_k_formula_tooltip"] = pd_formula_text(coeff_key)


def list_formulas_for_admin(*, page: str | None = None) -> list[dict[str, Any]]:
    overrides = get_formula_text_overrides()
    out: list[dict[str, Any]] = []
    for item in iter_formula_defs(page=page):
        effective = pd_formula_text(item.key)
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


def save_formula_text_override(*, formula_key: str, formula_text: str) -> PdSummaryFormulaDef:
    key = str(formula_key or "").strip()
    if not get_formula_def(key):
        raise ValueError(f"Неизвестный ключ формулы: {key}")
    text = str(formula_text or "").strip()
    if not text:
        raise ValueError("Текст формулы не может быть пустым.")
    row = PowerDemandSummaryFormulaText.query.filter_by(formula_key=key).first()
    if row is None:
        row = PowerDemandSummaryFormulaText(formula_key=key, formula_text=text)
        db.session.add(row)
    else:
        row.formula_text = text
    clear_formula_text_override_cache()
    return get_formula_def(key)  # type: ignore[return-value]


def reset_formula_text_override(formula_key: str) -> None:
    key = str(formula_key or "").strip()
    row = PowerDemandSummaryFormulaText.query.filter_by(formula_key=key).first()
    if row is not None:
        db.session.delete(row)
    clear_formula_text_override_cache()

# -*- coding: utf-8 -*-
"""JSON API и подготовка данных для клиентского рендера сводок нагрузок."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from flask import jsonify

from app.power_demand.services.pd_summary_data_segments import build_client_segment_config

PD_READONLY_PARAMETER_KEYS_MAX: frozenset[str] = frozenset(
    {
        "calculated_max_power_mw",
        "calculated_max_fo_mw",
        "calculated_max_ez_mw",
        "calculated_max_sa_mw",
        "calculated_combined_on_cz_mw",
        "calculated_combined_on_ees_mw",
        "calculated_max_ees_russia_mw",
        "calculated_max_ees_via_oes_mw",
        "calculated_max_ees_via_es_mw",
        "calculated_max_power_consumption_mw",
        "peak_max_power_usage_hours",
    }
)

_SECOND_SA_LABEL_CF = "вторая синхронная"


def _label_cf(text: object) -> str:
    return str(text or "").strip().casefold()


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, frozenset):
        return sorted(_json_safe(v) for v in value)
    return str(value)


def enrich_row_formula_tooltip_gaps(
    row: dict[str, Any],
    formula_texts: dict[str, str],
) -> None:
    """Дополняет pd_parameter_formula_tooltip для случаев, которые в шаблоне заданы явно."""
    if row.get("pd_parameter_formula_tooltip"):
        return
    pk = str(row.get("parameter_key") or "")
    dm = str(row.get("demand_model_name") or "")
    ek = str(row.get("entity_kind") or "")
    lbl = _label_cf(row.get("entity_label"))

    if dm == "SynchronousAreaDemandParameter":
        if pk == "calculated_max_power_mw":
            if lbl.startswith(_SECOND_SA_LABEL_CF):
                row["pd_parameter_formula_tooltip"] = formula_texts.get(
                    "sa_second_calc_max_power_mw", ""
                )
            elif "калининград" in lbl:
                row["pd_parameter_formula_tooltip"] = formula_texts.get(
                    "sa_kaliningrad_calc_max_power_mw", ""
                )
            else:
                row["pd_parameter_formula_tooltip"] = formula_texts.get(
                    "sa_first_calc_max_power_mw_without_nt", ""
                )
        elif pk == "calculated_max_sa_mw":
            if lbl.startswith(_SECOND_SA_LABEL_CF):
                row["pd_parameter_formula_tooltip"] = formula_texts.get(
                    "sa_second_calc_max_sa_mw", ""
                )
            elif "калининград" in lbl:
                row["pd_parameter_formula_tooltip"] = formula_texts.get(
                    "sa_kaliningrad_calc_max_sa_mw", ""
                )
            else:
                row["pd_parameter_formula_tooltip"] = formula_texts.get(
                    "sa_first_calc_max_sa_mw_without_nt", ""
                )
    elif ek == "synchronous_area" and pk == "verify_for_calculated_max_power_mw":
        if lbl.startswith(_SECOND_SA_LABEL_CF):
            row["pd_parameter_formula_tooltip"] = formula_texts.get(
                "sa_second_verify_max_power", ""
            )
        elif "калининград" in lbl:
            row["pd_parameter_formula_tooltip"] = formula_texts.get(
                "sa_kaliningrad_verify_max_power", ""
            )
        else:
            row["pd_parameter_formula_tooltip"] = formula_texts.get(
                "sa_first_verify_max_power_without_nt", ""
            )
    elif pk == "verify_for_calculated_max_sa_mw":
        if ek == "synchronous_area":
            if lbl.startswith(_SECOND_SA_LABEL_CF):
                row["pd_parameter_formula_tooltip"] = formula_texts.get(
                    "sa_second_verify_combined_ees", ""
                )
            elif "калининград" in lbl:
                row["pd_parameter_formula_tooltip"] = formula_texts.get(
                    "sa_kaliningrad_verify_combined_ees", ""
                )
            else:
                row["pd_parameter_formula_tooltip"] = formula_texts.get(
                    "sa_first_verify_combined_ees_without_nt", ""
                )
        else:
            row["pd_parameter_formula_tooltip"] = formula_texts.get(
                "sa_first_verify_combined_ees_without_nt", ""
            )
    elif (
        pk == "calculated_max_power_mw"
        and row.get("pd_formula_text_key") == "chukotka_rd_calc_max_mw"
    ):
        row["pd_parameter_formula_tooltip"] = formula_texts.get(
            "chukotka_rd_calc_max_mw", ""
        )
    elif (
        pk == "calculated_max_power_mw"
        and row.get("pd_formula_text_key") == "chukotka_rd_territorial_calc_max_mw"
    ):
        row["pd_parameter_formula_tooltip"] = formula_texts.get(
            "chukotka_rd_territorial_calc_max_mw", ""
        )
    elif dm == "FederalDistrictDemandParameter":
        if pk == "calculated_max_fo_mw":
            row["pd_parameter_formula_tooltip"] = formula_texts.get("fo_calc_max_mw", "")
        elif pk == "calculated_max_power_mw":
            row["pd_parameter_formula_tooltip"] = formula_texts.get(
                "fo_calc_max_power_mw", ""
            )
        elif pk == "calculated_combined_on_cz_mw":
            row["pd_parameter_formula_tooltip"] = formula_texts.get(
                "fo_calc_combined_on_cz_mw", ""
            )
        elif pk == "calculated_combined_on_ees_mw":
            row["pd_parameter_formula_tooltip"] = formula_texts.get(
                "fo_calc_combined_on_ees_mw", ""
            )
        elif pk == "verify_for_calculated_max_power_mw":
            row["pd_parameter_formula_tooltip"] = formula_texts.get(
                "fo_verify_calc_max_mw_without_nt", ""
            )
        elif pk == "verify_for_calculated_combined_on_ees_mw":
            row["pd_parameter_formula_tooltip"] = formula_texts.get(
                "fo_verify_combined_ees_mw_without_nt", ""
            )
        elif pk == "peak_max_power_usage_hours":
            row["pd_parameter_formula_tooltip"] = formula_texts.get(
                "fo_chi_federal_district", ""
            )
    elif dm == "EnergyZoneDemandParameter" and pk == "calculated_max_ez_mw":
        row["pd_parameter_formula_tooltip"] = formula_texts.get("ez_calc_max_mw", "")
    elif ek == "centralized_zone" and pk == "cz_calculated_max_cz_russia_mw":
        row["pd_parameter_formula_tooltip"] = str(
            row.get("pd_fo_cz_calc_max_tooltip") or ""
        )


def prepare_summary_rows_for_client(
    summary_rows: list[dict[str, Any]] | None,
    *,
    formula_texts: dict[str, str],
) -> list[dict[str, Any]]:
    if not summary_rows:
        return []
    out: list[dict[str, Any]] = []
    for row in summary_rows:
        item = dict(row)
        enrich_row_formula_tooltip_gaps(item, formula_texts)
        out.append(_json_safe(item))
    return out


def build_client_render_config(
    *,
    scope: str,
    data_path: str,
) -> dict[str, Any]:
    return {
        "scope": scope,
        "data_path": data_path,
        "pd_readonly_parameter_keys": sorted(PD_READONLY_PARAMETER_KEYS_MAX),
        "segments": build_client_segment_config(scope),
    }


def build_summary_data_json_response(context: dict[str, Any]) -> Any:
    """Flask Response с данными таблицы для клиентского рендера."""
    formula_texts = context.get("pd_formula_texts") or {}
    years = list(context.get("years") or [])
    year_is_plan = {
        str(y): bool(v) for y, v in (context.get("year_is_plan") or {}).items()
    }
    payload = {
        "ok": True,
        "summary_rows": prepare_summary_rows_for_client(
            context.get("summary_rows"),
            formula_texts=formula_texts,
        ),
        "years": years,
        "year_is_plan": year_is_plan,
        "config": _json_safe(
            {
                "active_summary": context.get("active_summary"),
                "summary_route_variant": context.get("summary_route_variant", "max"),
                "show_hist_col": context.get("summary_route_variant") != "coeff",
                "show_perimeter_variant_column": bool(
                    context.get("can_edit_summary_cells")
                ),
                "can_edit_summary_cells": bool(
                    context.get("can_edit_summary_cells")
                ),
                "pd_readonly_parameter_keys": sorted(PD_READONLY_PARAMETER_KEYS_MAX),
                "coeff_base_year": context.get("coeff_base_year"),
                "pd_pd_max_year_segments": bool(
                    context.get("summary_route_variant") != "coeff"
                    and context.get("coeff_base_year") is not None
                    and context.get("active_summary") in ("oes", "fo", "ez")
                ),
            }
        ),
    }
    live_calc = context.get("pd_oes_live_calc_js")
    if live_calc is not None:
        payload["pd_oes_live_calc_js"] = _json_safe(live_calc)
    filters = context.get("pd_oes_filters_cascade")
    if filters is not None:
        payload["pd_oes_filters_cascade"] = _json_safe(filters)
    fo_filters = context.get("pd_fo_filters_cascade")
    if fo_filters is not None:
        payload["pd_fo_filters_cascade"] = _json_safe(fo_filters)
    ez_filters = context.get("pd_ez_filters_cascade")
    if ez_filters is not None:
        payload["pd_ez_filters_cascade"] = _json_safe(ez_filters)
    return jsonify(payload)

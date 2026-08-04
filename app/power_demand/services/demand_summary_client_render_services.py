# -*- coding: utf-8 -*-
"""JSON API и подготовка данных для клиентского рендера сводок нагрузок."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from flask import jsonify

from app.power_demand.services.formula_text.power_demand_summary_formula_text_services import (
    apply_row_formula_text_overrides,
)
from app.power_demand.services.pd_peak_usage_hours_services import (
    combined_on_key_from_peak_combined_usage_hours,
    is_peak_combined_usage_hours_key,
    peak_combined_usage_hours_keys,
)
from app.power_demand.services.pd_summary_data_segments import build_client_segment_config
from app.power_demand.services.pd_summary_entity_pagination import (
    PAGINATION_SCOPES,
    client_entity_pagination_config,
    filter_segment_rows_to_pagination_page,
    paginate_summary_rows_for_scope,
)

PD_READONLY_PARAMETER_KEYS_MAX: frozenset[str] = frozenset(
    {
        "calculated_max_power_mw",
        "calculated_max_fo_mw",
        "calculated_max_sa_mw",
        "calculated_combined_on_cz_mw",
        "calculated_combined_on_ees_mw",
        "calculated_max_ees_russia_mw",
        "calculated_max_ees_via_oes_mw",
        "calculated_max_ees_via_es_mw",
        "calculated_max_ees_via_ez_mw",
        "calculated_max_power_consumption_mw",
        "peak_max_power_usage_hours",
        *peak_combined_usage_hours_keys(),
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
    *,
    summary_route_variant: str = "max",
) -> None:
    """Дополняет pd_parameter_formula_tooltip для случаев, которые в шаблоне заданы явно."""
    if row.get("pd_parameter_formula_tooltip"):
        return

    from app.power_demand.services.formula_text.pd_summary_formula_row_resolver import (
        resolve_pd_summary_parameter_formula_base_key,
        resolve_pd_summary_row_formula_key,
    )

    resolved_key = resolve_pd_summary_row_formula_key(
        row,
        base_key=resolve_pd_summary_parameter_formula_base_key(row),
    )
    if resolved_key and formula_texts.get(resolved_key):
        row["pd_formula_text_key"] = resolved_key
        row["pd_parameter_formula_tooltip"] = formula_texts[resolved_key]
        return

    pk = str(row.get("parameter_key") or "")
    dm = str(row.get("demand_model_name") or "")
    ek = str(row.get("entity_kind") or "")
    lbl = _label_cf(row.get("entity_label"))

    def _text_for_nt_base(base_key: str) -> str:
        key = resolve_pd_summary_row_formula_key(row, base_key=base_key)
        return formula_texts.get(key or base_key, "")

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
                row["pd_parameter_formula_tooltip"] = _text_for_nt_base(
                    "sa_first_calc_max_power_mw"
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
                row["pd_parameter_formula_tooltip"] = _text_for_nt_base(
                    "sa_first_calc_max_sa_mw"
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
            row["pd_parameter_formula_tooltip"] = _text_for_nt_base(
                "sa_first_verify_max_power"
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
                row["pd_parameter_formula_tooltip"] = _text_for_nt_base(
                    "sa_first_verify_combined_ees"
                )
        else:
            row["pd_parameter_formula_tooltip"] = _text_for_nt_base(
                "sa_first_verify_combined_ees"
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
            row["pd_parameter_formula_tooltip"] = _text_for_nt_base("fo_calc_max_mw")
        elif pk == "calculated_max_power_mw":
            row["pd_parameter_formula_tooltip"] = _text_for_nt_base(
                "fo_calc_max_power_mw"
            )
        elif pk == "calculated_combined_on_cz_mw":
            # Coeff ФО использует тот же набор строк, что /summary/federal_districts/.
            row["pd_parameter_formula_tooltip"] = formula_texts.get(
                "fo_calc_combined_on_cz_mw", ""
            )
        elif pk == "calculated_combined_on_ees_mw":
            row["pd_parameter_formula_tooltip"] = formula_texts.get(
                "fo_calc_combined_on_ees_mw", ""
            )
        elif pk == "verify_for_calculated_max_power_mw":
            row["pd_parameter_formula_tooltip"] = _text_for_nt_base(
                "fo_verify_calc_max_mw"
            )
        elif pk == "verify_for_calculated_combined_on_cz_mw":
            row["pd_parameter_formula_tooltip"] = _text_for_nt_base(
                "fo_verify_combined_on_cz_mw"
            )
        elif pk == "verify_for_calculated_combined_on_ees_mw":
            row["pd_parameter_formula_tooltip"] = _text_for_nt_base(
                "fo_verify_combined_ees_mw"
            )
        elif pk == "peak_max_power_usage_hours":
            row["pd_parameter_formula_tooltip"] = formula_texts.get(
                "fo_chi_federal_district", ""
            )
    elif dm == "CentralizedZoneDemandParameter" and pk == "peak_max_power_usage_hours":
        row["pd_parameter_formula_tooltip"] = formula_texts.get(
            "fo_chi_centralized_zone", ""
        )
    elif dm == "EnergyZoneDemandParameter":
        if pk == "calculated_max_power_mw":
            row["pd_parameter_formula_tooltip"] = formula_texts.get(
                "ez_calc_max_power_mw", ""
            )
        elif pk == "calculated_combined_on_ees_mw":
            row["pd_parameter_formula_tooltip"] = formula_texts.get(
                "ez_calc_combined_on_ees_mw", ""
            )
        elif pk == "verify_for_calculated_max_power_mw":
            row["pd_parameter_formula_tooltip"] = _text_for_nt_base(
                "ez_verify_calc_max_mw"
            )
        elif pk == "verify_for_calculated_combined_on_ees_mw":
            row["pd_parameter_formula_tooltip"] = _text_for_nt_base(
                "ez_verify_combined_ees_mw"
            )
        elif pk == "peak_max_power_usage_hours":
            row["pd_parameter_formula_tooltip"] = formula_texts.get(
                "ez_chi_energy_zone", ""
            )
    elif ek == "centralized_zone" and pk == "cz_calculated_max_cz_russia_mw":
        row["pd_parameter_formula_tooltip"] = str(
            row.get("pd_fo_cz_calc_max_tooltip") or ""
        )
    elif dm == "CentralizedZoneDemandParameter":
        if pk == "calculated_max_power_mw":
            row["pd_parameter_formula_tooltip"] = _text_for_nt_base(
                "cz_russia_calc_max_mw"
            )
        elif pk == "verify_for_calculated_max_power_mw":
            row["pd_parameter_formula_tooltip"] = _text_for_nt_base(
                "cz_russia_verify_calc_max_mw"
            )
    elif is_peak_combined_usage_hours_key(pk):
        combined_on_key = combined_on_key_from_peak_combined_usage_hours(pk)
        if combined_on_key:
            row["pd_parameter_formula_tooltip"] = formula_texts.get(
                f"pd_peak_{combined_on_key}_usage_hours",
                "",
            )


def prepare_summary_rows_for_client(
    summary_rows: list[dict[str, Any]] | None,
    *,
    formula_texts: dict[str, str],
    summary_route_variant: str = "max",
) -> list[dict[str, Any]]:
    if not summary_rows:
        return []
    out: list[dict[str, Any]] = []
    for row in summary_rows:
        item = dict(row)
        enrich_row_formula_tooltip_gaps(
            item, formula_texts, summary_route_variant=summary_route_variant
        )
        out.append(_json_safe(item))
    return out


def build_client_render_config(
    *,
    scope: str,
    data_path: str,
) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "scope": scope,
        "data_path": data_path,
        "pd_readonly_parameter_keys": sorted(PD_READONLY_PARAMETER_KEYS_MAX),
        "segments": build_client_segment_config(scope),
    }
    if scope in PAGINATION_SCOPES:
        cfg["entity_pagination"] = client_entity_pagination_config(scope)
    return cfg


def build_summary_data_json_response(
    context: dict[str, Any],
    *,
    entity_pagination: tuple[int, int] | None = None,
    pagination_boundary_rows: list[dict[str, Any]] | None = None,
) -> Any:
    """Flask Response с данными таблицы для клиентского рендера."""
    formula_texts = context.get("pd_formula_texts") or {}
    years = list(context.get("years") or [])
    year_is_plan = {
        str(y): bool(v) for y, v in (context.get("year_is_plan") or {}).items()
    }
    summary_rows = context.get("summary_rows")
    pagination_meta: dict[str, Any] | None = None
    if entity_pagination is not None and context.get("active_summary") in PAGINATION_SCOPES:
        page, page_size = entity_pagination
        scope = str(context.get("active_summary"))
        if pagination_boundary_rows is not None:
            _, pagination_meta = paginate_summary_rows_for_scope(
                pagination_boundary_rows,
                scope,
                page=page,
                page_size=page_size,
            )
            summary_rows = filter_segment_rows_to_pagination_page(
                summary_rows,
                pagination_boundary_rows,
                scope,
                page=page,
                page_size=page_size,
            )
        else:
            summary_rows, pagination_meta = paginate_summary_rows_for_scope(
                summary_rows,
                scope,
                page=page,
                page_size=page_size,
            )
    if summary_rows:
        apply_row_formula_text_overrides(summary_rows)
    payload = {
        "ok": True,
        "summary_rows": prepare_summary_rows_for_client(
            summary_rows,
            formula_texts=formula_texts,
            summary_route_variant=str(
                context.get("summary_route_variant") or "max"
            ),
        ),
        "years": years,
        "year_is_plan": year_is_plan,
        "config": _json_safe(
            {
                "active_summary": context.get("active_summary"),
                "summary_route_variant": context.get("summary_route_variant", "max"),
                "show_hist_col": context.get("summary_route_variant") != "coeff",
                "show_perimeter_variant_column": bool(
                    context.get("active_summary") in ("oes", "fo", "ez")
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
    if pagination_meta is not None:
        payload["entity_pagination"] = _json_safe(pagination_meta)
    return jsonify(payload)

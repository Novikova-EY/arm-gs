# -*- coding: utf-8 -*-
"""JSON API и подготовка данных для клиентского рендера сводок потребления."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from flask import has_request_context, jsonify, request, url_for

from app.energy_consumption.services.ec_summary_entity_pagination import (
    PAGINATION_SCOPES,
    client_entity_pagination_config,
    paginate_summary_rows_for_scope,
)

EC_READONLY_PARAMETER_KEYS: frozenset[str] = frozenset(
    {
        "energy_consumption_yoy_growth_pct",
        "energy_consumption_sipr_abs_growth_mln",
        "energy_consumption_sipr_yoy_growth_pct",
    }
)

EC_SIPR_ROW_KEYS: frozenset[str] = frozenset(
    {
        "energy_consumption_sipr_mln_kvt_ch",
        "energy_consumption_sipr_abs_growth_mln",
        "energy_consumption_sipr_yoy_growth_pct",
    }
)

EC_NORMAL_ROW_KEYS: frozenset[str] = frozenset(
    {
        "energy_consumption_mln_kvt_ch",
        "energy_consumption_yoy_growth_pct",
    }
)

EC_CLIENT_ROW_FLAG_QUERY_KEYS: frozenset[str] = frozenset(
    {
        "pd_ec_sipr",
        "pd_ec_gaes",
        "pd_ec_nt",
        "pd_ec_verify",
        "pd_ec_o1",
        "pd_ec_compact",
    }
)

_CLIENT_ROW_KEYS: frozenset[str] = frozenset(
    {
        "demand_model_name",
        "entity_depth",
        "entity_kind",
        "entity_label",
        "entity_note_row_id",
        "entity_note_text",
        "entity_rowspan",
        "gaes_charge_display_year_max",
        "gaes_charge_display_year_min",
        "gaes_charge_row_station_name",
        "gaes_station_id",
        "id_union_energy_system",
        "parameter_key",
        "parameter_label",
        "parent_fk_column",
        "parent_id",
        "pd_parameter_formula_tooltip",
        "perimeter_variant_code",
        "perimeter_variant_from_year",
        "perimeter_variant_label",
        "perimeter_variant_options",
        "perimeter_variant_to_year",
        "sakha_membership_through_year",
        "show_entity_cell",
        "show_entity_note_cell",
        "show_perimeter_variant_select",
        "year_numeric_tooltips",
        "year_row_ids",
        "year_values",
    }
)

_KEEP_FALSE_KEYS: frozenset[str] = frozenset(
    {
        "show_entity_cell",
        "show_entity_note_cell",
        "show_perimeter_variant_select",
    }
)

_VERIFY_ENTITY_KINDS: frozenset[str] = frozenset(
    {
        "oes_ees_model_verification",
        "oes_ees_sync_table_verification",
    }
)


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


def _parameter_tooltip_for_row(row: dict[str, Any]) -> str:
    for field in (
        "pd_ec_summary_row_formula_tooltip",
        "pd_ec_verification_formula_tooltip",
        "pd_parameter_formula_tooltip",
    ):
        raw = row.get(field)
        if raw:
            return str(raw)
    return ""


def _request_flag(name: str) -> bool:
    if not has_request_context():
        return False
    return str(request.args.get(name) or "").strip() in ("1", "true", "True")


def parse_ec_client_row_flags() -> dict[str, bool]:
    """Флаги видимости строк из GET — по умолчанию всё выключено (как на странице)."""
    return {
        "sipr": _request_flag("pd_ec_sipr"),
        "gaes": _request_flag("pd_ec_gaes"),
        "nt": _request_flag("pd_ec_nt"),
        "verify": _request_flag("pd_ec_verify"),
        "o1": _request_flag("pd_ec_o1"),
        "compact": _request_flag("pd_ec_compact"),
    }


def _is_verification_row(row: dict[str, Any]) -> bool:
    label = str(row.get("entity_label") or "")
    kind = str(row.get("entity_kind") or "")
    return (
        label.startswith("Проверка ")
        or kind in _VERIFY_ENTITY_KINDS
    )


def _row_hidden_for_client_flags(row: dict[str, Any], flags: dict[str, bool]) -> bool:
    pk = str(row.get("parameter_key") or "")
    sipr_on = bool(flags.get("sipr"))
    gaes_on = bool(flags.get("gaes"))
    nt_on = bool(flags.get("nt"))
    verify_on = bool(flags.get("verify"))
    o1_on = bool(flags.get("o1"))
    compact = bool(flags.get("compact"))
    collapsed_nt_gaes = not gaes_on and not nt_on
    expanded_nt_gaes = gaes_on and nt_on
    nt_on_gaes_off = nt_on and not gaes_on

    if sipr_on:
        if pk in EC_NORMAL_ROW_KEYS:
            return True
    elif pk in EC_SIPR_ROW_KEYS:
        return True
    if row.get("pd_ec_hide_when_isolated_eu_on") and o1_on:
        return True
    if row.get("pd_ec_o1_form_row") and not o1_on:
        return True
    if row.get("pd_ec_gaes_extra_row") and not gaes_on:
        visible_exception = (
            (collapsed_nt_gaes and row.get("pd_ec_collapsed_nt_gaes_visible_row"))
            or (nt_on_gaes_off and row.get("pd_ec_nt_on_gaes_off_visible_row"))
        )
        if not visible_exception:
            return True
    if row.get("pd_ec_nt_extra_row") and not nt_on:
        return True
    if collapsed_nt_gaes and row.get("pd_ec_collapsed_nt_gaes_redundant_row"):
        return True
    if nt_on_gaes_off and row.get("pd_ec_nt_on_gaes_off_redundant_row"):
        return True
    if expanded_nt_gaes and row.get("pd_ec_expanded_nt_gaes_redundant_row"):
        return True
    if row.get("pd_ec_summary_table_only_row") and not compact:
        return True
    if compact and (
        row.get("pd_ec_territory_detail_row")
        or row.get("pd_ec_territory_compact_hide_row")
    ):
        return True
    if compact and row.get("pd_ec_first_sa_gaes_compact_variant") == "detail":
        return True
    if compact and pk == "gaes_charge_consumption_mln_kvt_ch":
        return True
    if _is_verification_row(row) and not verify_on:
        return True
    return False


def filter_ec_summary_rows_for_client_flags(
    summary_rows: list[dict[str, Any]] | None,
    flags: dict[str, bool] | None = None,
) -> list[dict[str, Any]]:
    """Оставляет строки, видимые при текущих переключателях (как нагрузки: core JSON)."""
    if not summary_rows:
        return []
    flags = flags if flags is not None else parse_ec_client_row_flags()
    out: list[dict[str, Any]] = []
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if not row.get("show_entity_cell"):
            if not _row_hidden_for_client_flags(row, flags):
                out.append(dict(row))
            i += 1
            continue
        block_size = max(int(row.get("entity_rowspan") or 1), 1)
        block = summary_rows[i : i + block_size]
        kept = [r for r in block if not _row_hidden_for_client_flags(r, flags)]
        note_source = next((r for r in block if r.get("show_entity_note_cell")), None)
        if kept:
            for j, r in enumerate(kept):
                rc = dict(r)
                rc["show_entity_cell"] = j == 0
                rc["entity_rowspan"] = len(kept)
                if j == 0 and note_source is not None:
                    rc["show_entity_note_cell"] = True
                    if "entity_note_text" in note_source:
                        rc["entity_note_text"] = note_source.get("entity_note_text")
                    if "entity_note_row_id" in note_source:
                        rc["entity_note_row_id"] = note_source.get("entity_note_row_id")
                else:
                    rc["show_entity_note_cell"] = False
                out.append(rc)
        i += block_size
    return out


def _slim_row_for_client(row: dict[str, Any]) -> dict[str, Any]:
    item: dict[str, Any] = {}
    for key, value in row.items():
        if value is None:
            continue
        if key not in _CLIENT_ROW_KEYS and not str(key).startswith("pd_ec_"):
            continue
        if value is False and key not in _KEEP_FALSE_KEYS:
            continue
        item[key] = _json_safe(value)
    tip = _parameter_tooltip_for_row(row)
    if tip:
        item["pd_parameter_formula_tooltip"] = tip
    return item


def prepare_summary_rows_for_client(
    summary_rows: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if not summary_rows:
        return []
    return [_slim_row_for_client(row) for row in summary_rows]


def build_client_render_config(
    *,
    scope: str,
    data_path: str,
) -> dict[str, Any]:
    station_details_template = ""
    try:
        raw_station_url = url_for("station_bp.station_details", station_id=0)
        if raw_station_url.endswith("/0"):
            station_details_template = raw_station_url[:-2] + "/{station_id}"
        else:
            station_details_template = raw_station_url.replace("0", "{station_id}", 1)
    except Exception:
        station_details_template = "/generation/station_details/{station_id}"
    cfg: dict[str, Any] = {
        "scope": scope,
        "data_path": data_path,
        "pd_readonly_parameter_keys": sorted(EC_READONLY_PARAMETER_KEYS),
        "pd_ec_sipr_row_keys": sorted(EC_SIPR_ROW_KEYS),
        "station_details_path_template": station_details_template,
        "summary_variant_toggle_default_off": True,
    }
    if scope in PAGINATION_SCOPES:
        cfg["entity_pagination"] = client_entity_pagination_config(scope)
    return cfg


def build_summary_data_json_response(
    context: dict[str, Any],
    *,
    entity_pagination: tuple[int, int] | None = None,
    pagination_meta: dict[str, Any] | None = None,
) -> Any:
    """Flask Response с данными таблицы для клиентского рендера."""
    years = list(context.get("years") or [])
    year_is_plan = {
        str(y): bool(v) for y, v in (context.get("year_is_plan") or {}).items()
    }
    summary_rows = context.get("summary_rows")
    if (
        pagination_meta is None
        and entity_pagination is not None
        and context.get("active_summary") in PAGINATION_SCOPES
    ):
        page, page_size = entity_pagination
        scope = str(context.get("active_summary"))
        summary_rows, pagination_meta = paginate_summary_rows_for_scope(
            summary_rows,
            scope,
            page=page,
            page_size=page_size,
        )
    summary_rows = filter_ec_summary_rows_for_client_flags(summary_rows)
    payload = {
        "ok": True,
        "summary_rows": prepare_summary_rows_for_client(summary_rows),
        "years": years,
        "year_is_plan": year_is_plan,
        "config": _json_safe(
            {
                "active_summary": context.get("active_summary"),
                "summary_route_variant": context.get("summary_route_variant", "max"),
                "show_hist_col": False,
                "show_perimeter_variant_column": bool(
                    context.get("active_summary") in ("oes", "fo", "ez")
                ),
                "show_summary_note_col": bool(
                    context.get("active_summary") in ("oes", "fo", "ez")
                ),
                "can_edit_summary_cells": bool(
                    context.get("can_edit_summary_cells")
                ),
                "pd_readonly_parameter_keys": sorted(EC_READONLY_PARAMETER_KEYS),
                "pd_ec_sipr_row_keys": sorted(EC_SIPR_ROW_KEYS),
                "coeff_base_year": context.get("coeff_base_year"),
                "pd_ec_max_year_segments": bool(
                    context.get("coeff_base_year") is not None
                    and context.get("active_summary") in ("oes", "fo", "ez")
                ),
                "start_year": context.get("start_year"),
                "end_year": context.get("end_year"),
                "rounding_digits": context.get("rounding_digits"),
            }
        ),
    }
    if pagination_meta is not None:
        payload["entity_pagination"] = _json_safe(pagination_meta)
    return jsonify(payload)

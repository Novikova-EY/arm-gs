# -*- coding: utf-8 -*-
"""Сегменты ленивой подгрузки JSON для сводок «Максимумы» (ОЭС / ФО / ЭЗ)."""

from __future__ import annotations

from typing import Any

from flask import request

PD_SUMMARY_SEGMENT_CORE = "core"
PD_SUMMARY_SEGMENT_CALC_MAX = "calc_max"
PD_SUMMARY_SEGMENT_CHI = "chi"
PD_SUMMARY_SEGMENT_VERIFY = "verify"
PD_SUMMARY_SEGMENT_NT_EXTRA = "nt_extra"

ALL_PD_SUMMARY_DATA_SEGMENTS: frozenset[str] = frozenset(
    {
        PD_SUMMARY_SEGMENT_CORE,
        PD_SUMMARY_SEGMENT_CALC_MAX,
        PD_SUMMARY_SEGMENT_CHI,
        PD_SUMMARY_SEGMENT_VERIFY,
        PD_SUMMARY_SEGMENT_NT_EXTRA,
    }
)

DEFAULT_PD_SUMMARY_DATA_SEGMENTS: frozenset[str] = frozenset({PD_SUMMARY_SEGMENT_CORE})

_OES_CORE_PARAMETER_KEYS: frozenset[str] = frozenset(
    {
        "max_power",
        "peak_datetime",
        "avg_temp",
        "combined_on_oes",
        "combined_on_ees",
        "combined_on_es",
    }
)

_FO_CORE_PARAMETER_KEYS: frozenset[str] = frozenset(
    {
        "max_power",
        "peak_datetime",
        "avg_temp",
        "combined_on_cz",
        "combined_on_fo",
        "combined_on_ees",
    }
)

_EZ_CORE_PARAMETER_KEYS: frozenset[str] = frozenset(
    {
        "max_power",
        "peak_datetime",
        "avg_temp",
        "combined_on_ez",
        "combined_on_ees",
    }
)

_SCOPE_CORE_PARAMETER_KEYS: dict[str, frozenset[str]] = {
    "oes": _OES_CORE_PARAMETER_KEYS,
    "fo": _FO_CORE_PARAMETER_KEYS,
    "ez": _EZ_CORE_PARAMETER_KEYS,
}

_CHI_PARAMETER_KEY = "peak_max_power_usage_hours"

_SCOPE_OPTIONAL_SEGMENTS: dict[str, frozenset[str]] = {
    "oes": frozenset(
        {
            PD_SUMMARY_SEGMENT_CALC_MAX,
            PD_SUMMARY_SEGMENT_CHI,
            PD_SUMMARY_SEGMENT_VERIFY,
            PD_SUMMARY_SEGMENT_NT_EXTRA,
        }
    ),
    "fo": frozenset(
        {
            PD_SUMMARY_SEGMENT_CALC_MAX,
            PD_SUMMARY_SEGMENT_CHI,
            PD_SUMMARY_SEGMENT_VERIFY,
            PD_SUMMARY_SEGMENT_NT_EXTRA,
        }
    ),
    "ez": frozenset(
        {PD_SUMMARY_SEGMENT_CALC_MAX, PD_SUMMARY_SEGMENT_CHI, PD_SUMMARY_SEGMENT_NT_EXTRA}
    ),
}


def core_parameter_keys_for_scope(scope: str) -> frozenset[str]:
    return _SCOPE_CORE_PARAMETER_KEYS.get(scope, frozenset())


def calc_max_parameter_keys_for_scope(scope: str) -> frozenset[str]:
    from app.power_demand.services.demand_summary_client_render_services import (
        PD_READONLY_PARAMETER_KEYS_MAX,
    )

    core = core_parameter_keys_for_scope(scope)
    return frozenset(pk for pk in PD_READONLY_PARAMETER_KEYS_MAX if pk not in core)


def optional_segments_for_scope(scope: str) -> frozenset[str]:
    return _SCOPE_OPTIONAL_SEGMENTS.get(scope, frozenset())


def segment_for_parameter_key(parameter_key: str, *, scope: str) -> str | None:
    pk = str(parameter_key or "").strip()
    if not pk:
        return None
    if pk == _CHI_PARAMETER_KEY:
        return PD_SUMMARY_SEGMENT_CHI
    if pk.startswith("verify_for_"):
        return PD_SUMMARY_SEGMENT_VERIFY
    if pk in calc_max_parameter_keys_for_scope(scope):
        return PD_SUMMARY_SEGMENT_CALC_MAX
    if pk in core_parameter_keys_for_scope(scope):
        return PD_SUMMARY_SEGMENT_CORE
    return None


def segments_for_parameter_keys(keys: set[str] | frozenset[str], *, scope: str) -> frozenset[str]:
    out: set[str] = set()
    for pk in keys:
        seg = segment_for_parameter_key(pk, scope=scope)
        if seg:
            out.add(seg)
    return frozenset(out)


def parse_pd_data_segments(scope: str) -> frozenset[str]:
    """GET pd_data_segments=core,calc_max — по умолчанию только core."""
    raw = request.args.get("pd_data_segments")
    if raw is None or str(raw).strip() == "":
        return DEFAULT_PD_SUMMARY_DATA_SEGMENTS
    allowed = ALL_PD_SUMMARY_DATA_SEGMENTS & (
        frozenset({PD_SUMMARY_SEGMENT_CORE}) | optional_segments_for_scope(scope)
    )
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    picked = frozenset(p for p in parts if p in allowed)
    if not picked:
        return DEFAULT_PD_SUMMARY_DATA_SEGMENTS
    return picked


def needs_full_summary_build(data_segments: frozenset[str] | None) -> bool:
    return data_segments is None or data_segments >= ALL_PD_SUMMARY_DATA_SEGMENTS


def _row_in_data_segments(
    row: dict[str, Any],
    segments: frozenset[str],
    *,
    scope: str,
    core_keys: frozenset[str],
    calc_keys: frozenset[str],
) -> bool:
    if row.get("pd_pd_chi_row"):
        return PD_SUMMARY_SEGMENT_CHI in segments
    # Заголовок «Новые территории» помечен pd_pd_nt_extra_row, но всегда в core (позиция в дереве ОЭС Юга).
    if row.get("pd_pd_aggregation_level_row"):
        return PD_SUMMARY_SEGMENT_CORE in segments
    # «Проверка …» у «с НТ» (в т.ч. ОЭС Юга с НТ) — сегмент verify, не nt_extra.
    if row.get("pd_pd_verify_for_row"):
        return PD_SUMMARY_SEGMENT_VERIFY in segments

    pk = str(row.get("parameter_key") or "")
    if pk in calc_keys:
        return PD_SUMMARY_SEGMENT_CALC_MAX in segments
    if pk.startswith("verify_for_"):
        return PD_SUMMARY_SEGMENT_VERIFY in segments
    # Варианты периметра: редактируемые показатели в core (в т.ч. «с НТ» из /perimeter_variants/).
    if row.get("pd_pd_summary_perimeter_variant_row"):
        return PD_SUMMARY_SEGMENT_CORE in segments
    if row.get("pd_pd_nt_extra_row"):
        return PD_SUMMARY_SEGMENT_NT_EXTRA in segments
    if pk in core_keys:
        return PD_SUMMARY_SEGMENT_CORE in segments
    return PD_SUMMARY_SEGMENT_CORE in segments


def filter_summary_rows_for_data_segments(
    summary_rows: list[dict[str, Any]] | None,
    segments: frozenset[str],
    *,
    scope: str,
) -> list[dict[str, Any]]:
    if not summary_rows:
        return []
    if needs_full_summary_build(segments):
        return list(summary_rows)

    core_keys = core_parameter_keys_for_scope(scope)
    calc_keys = calc_max_parameter_keys_for_scope(scope)
    out: list[dict[str, Any]] = []
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if row.get("pd_pd_aggregation_level_row"):
            if _row_in_data_segments(
                row, segments, scope=scope, core_keys=core_keys, calc_keys=calc_keys
            ):
                out.append(dict(row))
            i += 1
            continue

        if not row.get("show_entity_cell"):
            i += 1
            continue

        block_size = int(row.get("entity_rowspan") or 1)
        if block_size < 1:
            block_size = 1
        block = summary_rows[i : i + block_size]
        filtered_block = [
            r
            for r in block
            if _row_in_data_segments(
                r, segments, scope=scope, core_keys=core_keys, calc_keys=calc_keys
            )
        ]
        for j, r in enumerate(filtered_block):
            rc = dict(r)
            rc["show_entity_cell"] = j == 0
            rc["entity_rowspan"] = len(filtered_block)
            out.append(rc)
        i += block_size
    return out


def build_client_segment_config(scope: str) -> dict[str, Any]:
    calc_keys = sorted(calc_max_parameter_keys_for_scope(scope))
    return {
        "default_segments": sorted(DEFAULT_PD_SUMMARY_DATA_SEGMENTS),
        "optional_segments": sorted(optional_segments_for_scope(scope)),
        "core_parameter_keys": sorted(core_parameter_keys_for_scope(scope)),
        "calc_max_parameter_keys": calc_keys,
        "chi_parameter_key": _CHI_PARAMETER_KEY,
        "parameter_key_segments": {
            pk: PD_SUMMARY_SEGMENT_CORE
            for pk in core_parameter_keys_for_scope(scope)
        }
        | {pk: PD_SUMMARY_SEGMENT_CALC_MAX for pk in calc_keys}
        | {_CHI_PARAMETER_KEY: PD_SUMMARY_SEGMENT_CHI},
    }

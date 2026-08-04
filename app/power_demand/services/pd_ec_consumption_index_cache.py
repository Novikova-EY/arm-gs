# -*- coding: utf-8 -*-
"""Кэш индекса потребления ЭЭ для расчёта ЧЧИ на сводке /power_demand/summary/oes/."""

from __future__ import annotations

import math
from typing import Any

from flask import g, has_request_context

from app.common.services.database_version_services import get_current_version
from app.extensions import cache

CACHE_PREFIX = "pd_ec_consumption_index"
CACHE_TIMEOUT = 86400
# v2: _load_full_ec_consumption_index учитывает переданный version_id при фильтрации строк.
_CACHE_SCHEMA_VERSION = 2

EcIndex = dict[tuple[str, int, str | None, Any], float]
SerializedEcIndex = dict[str, float]


def _version_token(version_id: int | None) -> str:
    return str(version_id) if version_id is not None else "none"


def _cache_key(version_id: int | None) -> str:
    return f"{CACHE_PREFIX}:s{_CACHE_SCHEMA_VERSION}:v{_version_token(version_id)}"


def _request_store() -> dict[int | None, EcIndex]:
    if has_request_context():
        return g.setdefault("_pd_ec_consumption_index_req", {})
    return {}


def _serialize_index(index: EcIndex) -> SerializedEcIndex:
    out: SerializedEcIndex = {}
    for (model_name, parent_id, pvc, slice_key), value in index.items():
        sk = "hist" if slice_key == "hist" else str(slice_key)
        pvc_s = "" if pvc in (None, "") else str(pvc)
        out[f"{model_name}|{parent_id}|{pvc_s}|{sk}"] = float(value)
    return out


def _deserialize_index(data: SerializedEcIndex) -> EcIndex:
    out: EcIndex = {}
    for key, value in data.items():
        model_name, parent_s, pvc_s, sk = key.split("|", 3)
        slice_key: Any = "hist" if sk == "hist" else int(sk)
        pvc_key = pvc_s if pvc_s else None
        out[(model_name, int(parent_s), pvc_key, slice_key)] = float(value)
    return out


def _load_full_ec_consumption_index(version_id: int | None) -> EcIndex:
    from app.common.services.database_version_services import get_current_version
    from app.power_demand.services.pd_peak_usage_hours_services import (
        _AGGREGATE_EC_PARENT_ID,
        _PD_TO_EC,
        _slice_key_from_ec_row,
    )

    vid = version_id if version_id is not None else get_current_version()
    index: EcIndex = {}
    for ec_model, fk_column in _PD_TO_EC.values():
        q = ec_model.query
        if vid is not None and hasattr(ec_model, "database_version_id"):
            q = q.filter(ec_model.database_version_id == vid)
        for row in q.all():
            if fk_column is None:
                parent_id = _AGGREGATE_EC_PARENT_ID
            else:
                parent_id = getattr(row, fk_column, None)
                if parent_id is None:
                    continue
                parent_id = int(parent_id)
            slice_key = _slice_key_from_ec_row(row)
            raw = getattr(row, "energy_consumption_mln_kvt_ch", None)
            if raw in (None, ""):
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(value):
                continue
            pvc = getattr(row, "perimeter_variant_code", None)
            pvc_key = str(pvc) if pvc not in (None, "") else None
            index[(ec_model.__name__, int(parent_id), pvc_key, slice_key)] = value
    return index


def get_full_ec_consumption_index(
    *,
    version_id: int | None = None,
) -> EcIndex:
    vid = get_current_version() if version_id is None else version_id
    req_store = _request_store()
    if vid in req_store:
        return req_store[vid]

    key = _cache_key(vid)
    serialized = cache.get(key)
    if serialized is None:
        index = _load_full_ec_consumption_index(vid)
        cache.set(key, _serialize_index(index), timeout=CACHE_TIMEOUT)
    else:
        index = _deserialize_index(serialized)

    req_store[vid] = index
    return index


def get_ec_consumption_index_for_years(years: list[int]) -> EcIndex:
    year_set = {int(y) for y in years}
    full = get_full_ec_consumption_index()
    return {
        key: value
        for key, value in full.items()
        if key[3] == "hist" or key[3] in year_set
    }


def invalidate_pd_ec_consumption_index_cache(version_id: int | None = None) -> None:
    """Сброс кэша после изменения данных потребления ЭЭ."""
    vid = get_current_version() if version_id is None else version_id
    cache.delete(_cache_key(vid))
    _request_store().pop(vid, None)
    # ЧЧИ / «Потребление ЭЭ» на сводках «Нагрузки» читаются из этого индекса,
    # но отдаются через pd_summary_page_cache — его тоже нужно сбросить.
    from app.power_demand.services.pd_summary_page_cache import clear_pd_summary_page_cache

    clear_pd_summary_page_cache()

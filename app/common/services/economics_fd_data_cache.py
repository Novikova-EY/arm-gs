# -*- coding: utf-8 -*-
"""Кэш данных economics/energy_consumption по федеральным округам (на уровне версии БД)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable

from flask import g, has_request_context

from app.extensions import cache

CACHE_PREFIX = "econ_fd_data"
CACHE_TIMEOUT = 86400

_DATASET_PRODUCT_OUTPUT = "product_output"
_DATASET_VED_CONSUMPTION = "ved_consumption"
_DATASET_ACCUM_FIXED_CAPITAL = "accum_fixed_capital"
_DATASET_POPULATION = "population"
_DATASET_ACCUM_MONETARY_INCOME = "accum_monetary_income"
_DATASET_EI_YEAR = "ei_year"
_DATASET_EI_COEF = "ei_coef"
_DATASET_POP_EI_YEAR = "pop_ei_year"
_DATASET_POP_EI_COEF = "pop_ei_coef"

ALL_DATASETS = (
    _DATASET_PRODUCT_OUTPUT,
    _DATASET_VED_CONSUMPTION,
    _DATASET_ACCUM_FIXED_CAPITAL,
    _DATASET_POPULATION,
    _DATASET_ACCUM_MONETARY_INCOME,
    _DATASET_EI_YEAR,
    _DATASET_EI_COEF,
    _DATASET_POP_EI_YEAR,
    _DATASET_POP_EI_COEF,
)


def _version_token(version_id: int | None) -> str:
    return str(version_id) if version_id is not None else "none"


def _cache_key(dataset: str, version_id: int | None) -> str:
    return f"{CACHE_PREFIX}:{dataset}:v{_version_token(version_id)}"


def _request_store() -> dict[tuple[str, int | None], Any]:
    if has_request_context():
        return g.setdefault("_econ_fd_data_req", {})
    return {}


def _get_bulk(dataset: str, version_id: int | None, loader: Callable[[], Any]) -> Any:
    req_key = (dataset, version_id)
    store = _request_store()
    if req_key in store:
        return store[req_key]

    key = _cache_key(dataset, version_id)
    data = cache.get(key)
    if data is None:
        data = loader()
        cache.set(key, data, timeout=CACHE_TIMEOUT)

    store[req_key] = data
    return data


def invalidate_economics_fd_data_cache(
    version_id: int | None,
    *datasets: str,
) -> None:
    """Сброс кэша после сохранения/импорта данных."""
    targets = datasets or ALL_DATASETS
    store = _request_store()
    for dataset in targets:
        cache.delete(_cache_key(dataset, version_id))
        store.pop((dataset, version_id), None)


def invalidate_all_economics_fd_data_cache(version_id: int | None) -> None:
    invalidate_economics_fd_data_cache(version_id)


def _extract_fd_id_from_territory_filter(territory_filter: Any | None) -> int | None:
    if territory_filter is None:
        return None
    try:
        right = getattr(territory_filter, "right", None)
        if right is None:
            return None
        val = getattr(right, "value", right)
        return int(val)
    except (TypeError, ValueError):
        return None


def _bulk_load_fd_ved_year(
    *,
    version_id: int | None,
    model: type,
    value_attr: str,
) -> dict[int, dict[tuple[int, int], Decimal | None]]:
    q = model.query
    if version_id is not None:
        q = q.filter(model.database_version_id == version_id)
    result: dict[int, dict[tuple[int, int], Decimal | None]] = {}
    for row in q.all():
        if row.year_number is None or row.id_economic_activity_type is None:
            continue
        fd_id = int(row.id_federal_district)
        key = (int(row.id_economic_activity_type), int(row.year_number))
        result.setdefault(fd_id, {})[key] = getattr(row, value_attr)
    return result


def get_fd_ved_year_values(
    dataset: str,
    *,
    version_id: int | None,
    model: type,
    value_attr: str,
    territory_filter: Any | None = None,
    fd_id: int | None = None,
) -> dict[tuple[int, int], Decimal | None]:
    resolved_fd_id = fd_id if fd_id is not None else _extract_fd_id_from_territory_filter(
        territory_filter
    )
    bulk = _get_bulk(
        dataset,
        version_id,
        lambda: _bulk_load_fd_ved_year(
            version_id=version_id,
            model=model,
            value_attr=value_attr,
        ),
    )
    if resolved_fd_id is not None:
        return bulk.get(resolved_fd_id, {})
    merged: dict[tuple[int, int], Decimal | None] = {}
    for fd_values in bulk.values():
        for key, val in fd_values.items():
            if val is None:
                continue
            prev = merged.get(key)
            merged[key] = val if prev is None else prev + val
    return merged


def _bulk_load_fd_year_values(
    *,
    version_id: int | None,
    model: type,
    value_attr: str,
) -> dict[int, dict[int, Decimal | None]]:
    q = model.query
    if version_id is not None:
        q = q.filter(model.database_version_id == version_id)
    result: dict[int, dict[int, Decimal | None]] = {}
    for row in q.all():
        if row.year_number is None:
            continue
        fd_id = int(row.id_federal_district)
        result.setdefault(fd_id, {})[int(row.year_number)] = getattr(row, value_attr)
    return result


def get_fd_year_values(
    dataset: str,
    *,
    version_id: int | None,
    model: type,
    value_attr: str,
    fd_id: int,
) -> dict[int, Decimal | None]:
    bulk = _get_bulk(
        dataset,
        version_id,
        lambda: _bulk_load_fd_year_values(
            version_id=version_id,
            model=model,
            value_attr=value_attr,
        ),
    )
    return bulk.get(fd_id, {})


def _bulk_load_ei_year_values(
    *,
    version_id: int | None,
    model: type,
) -> dict[int, dict[tuple[int, str, int], Decimal | None]]:
    q = model.query
    if version_id is not None:
        q = q.filter(model.database_version_id == version_id)
    result: dict[int, dict[tuple[int, str, int], Decimal | None]] = {}
    for row in q.all():
        if row.year_number is None or not row.row_kind:
            continue
        fd_id = int(row.id_federal_district)
        key = (int(row.id_economic_activity_type), str(row.row_kind), int(row.year_number))
        result.setdefault(fd_id, {})[key] = row.parameter_value
    return result


def get_fd_ei_year_values(
    *,
    version_id: int | None,
    model: type,
    fd_id: int,
) -> dict[tuple[int, str, int], Decimal | None]:
    bulk = _get_bulk(
        _DATASET_EI_YEAR,
        version_id,
        lambda: _bulk_load_ei_year_values(version_id=version_id, model=model),
    )
    return bulk.get(fd_id, {})


def _bulk_load_ei_coef_values(
    *,
    version_id: int | None,
    model: type,
) -> dict[int, dict[int, tuple[Decimal | None, Decimal | None]]]:
    q = model.query
    if version_id is not None:
        q = q.filter(model.database_version_id == version_id)
    result: dict[int, dict[int, tuple[Decimal | None, Decimal | None]]] = {}
    for row in q.all():
        fd_id = int(row.id_federal_district)
        result.setdefault(fd_id, {})[int(row.id_economic_activity_type)] = (
            row.coefficient_a,
            row.coefficient_x,
        )
    return result


def get_fd_ei_coef_values(
    *,
    version_id: int | None,
    model: type,
    fd_id: int,
) -> dict[int, tuple[Decimal | None, Decimal | None]]:
    bulk = _get_bulk(
        _DATASET_EI_COEF,
        version_id,
        lambda: _bulk_load_ei_coef_values(version_id=version_id, model=model),
    )
    return bulk.get(fd_id, {})


def _bulk_load_pop_ei_year_values(
    *,
    version_id: int | None,
    model: type,
) -> dict[int, dict[tuple[str, int], Decimal | None]]:
    q = model.query
    if version_id is not None:
        q = q.filter(model.database_version_id == version_id)
    result: dict[int, dict[tuple[str, int], Decimal | None]] = {}
    for row in q.all():
        if row.year_number is None or not row.row_kind:
            continue
        fd_id = int(row.id_federal_district)
        key = (str(row.row_kind), int(row.year_number))
        result.setdefault(fd_id, {})[key] = row.parameter_value
    return result


def get_fd_pop_ei_year_values(
    *,
    version_id: int | None,
    model: type,
    fd_id: int,
) -> dict[tuple[str, int], Decimal | None]:
    bulk = _get_bulk(
        _DATASET_POP_EI_YEAR,
        version_id,
        lambda: _bulk_load_pop_ei_year_values(version_id=version_id, model=model),
    )
    return bulk.get(fd_id, {})


def _bulk_load_pop_ei_coef_values(
    *,
    version_id: int | None,
    model: type,
) -> dict[int, tuple[Decimal | None, Decimal | None]]:
    q = model.query
    if version_id is not None:
        q = q.filter(model.database_version_id == version_id)
    result: dict[int, tuple[Decimal | None, Decimal | None]] = {}
    for row in q.all():
        fd_id = int(row.id_federal_district)
        result[fd_id] = (row.coefficient_a, row.coefficient_x)
    return result


def get_fd_pop_ei_coef(
    *,
    version_id: int | None,
    model: type,
    fd_id: int,
) -> tuple[Decimal | None, Decimal | None]:
    bulk = _get_bulk(
        _DATASET_POP_EI_COEF,
        version_id,
        lambda: _bulk_load_pop_ei_coef_values(version_id=version_id, model=model),
    )
    return bulk.get(fd_id, (None, None))

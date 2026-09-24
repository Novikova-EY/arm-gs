# -*- coding: utf-8 -*-
"""Итоговые суммы выработки ЭЭ: ЕЭС / ТИТЭС / ОЭС (внутри по РЭС) / Россия."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
    get_energy_system_type_list_full,
    get_energy_system_type_map,
)
from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
    get_regional_energy_systems_name_map,
    get_res_to_est_id_map,
    get_res_to_synchronous_area_ids_map,
)
from app.common.services.get_services.energy_systems.synchronous_area_get_services import (
    get_synchronous_area_list_full,
    synchronous_area_display_order_sort_key,
)
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_res_to_ues_id_map,
    get_ues_to_est_id_map,
    get_ues_to_res_ids_map,
    get_union_energy_system_display_order_map,
    get_union_energy_system_list_full,
    get_union_energy_systems_map,
    union_energy_system_hierarchy_sort_key,
)
from app.common.services.get_services.years.year_feature_services import get_year_feature_dict
from app.common.services.get_services.years.years_get_services import (
    get_year_numbers_sorted_for_current_db_version,
)
from app.energy_balance.services.ee_generation_hierarchy_control_services import (
    load_hierarchy_control_generation,
    overlay_hierarchy_control,
)
from app.energy_balance.services.station_ee_generation_page_services import (
    _add_period_sum,
    build_year_columns,
    format_generation_cell,
    format_generation_input_value,
    is_verification_nonzero,
    load_annual_res_control_generation_by_res,
)

DEFAULT_AGGREGATION_TYPES = ("russia", "ees", "sz", "oes")
VALID_AGGREGATION_TYPES = frozenset({"ees", "tites", "sz", "oes", "russia"})
_UNSPECIFIED_NAMES = frozenset({"", "не указано", "не указ", "—", "-"})


def resolve_rounding_digits(raw: Any, default: int = 1) -> int:
    try:
        digits = int(raw)
    except (TypeError, ValueError):
        return default
    if digits is None or digits < -1:
        return default
    return digits


def parse_ee_generation_aggregation_types(args) -> list[str]:
    """Оставлен для совместимости; витрина всегда показывает ЕЭС, СЗ и ОЭС."""
    raw = [
        (at or "").strip().lower()
        for at in args.getlist("aggregation_type")
        if (at or "").strip()
    ]
    filtered = [at for at in raw if at in VALID_AGGREGATION_TYPES]
    return filtered or list(DEFAULT_AGGREGATION_TYPES)


def parse_show_res(args) -> bool:
    """Кнопка «+ Региональные энергосистемы»: по умолчанию включена."""
    values = [
        str(v).strip().lower()
        for v in args.getlist("show_res")
        if v is not None and str(v).strip() != ""
    ]
    if not values:
        return True
    return any(v in {"1", "true", "on", "yes"} for v in values)


def parse_show_verification(args) -> bool:
    """Кнопка «Проверка»: по умолчанию выключена."""
    values = [
        str(v).strip().lower()
        for v in args.getlist("show_verification")
        if v is not None and str(v).strip() != ""
    ]
    if not values:
        return False
    return any(v in {"1", "true", "on", "yes"} for v in values)


def _is_unspecified_name(name: str | None) -> bool:
    return (name or "").strip().lower() in _UNSPECIFIED_NAMES


def _has_period_values(period_totals: dict | None, period_keys: list[int]) -> bool:
    if not period_totals:
        return False
    return any(period_totals.get(key) is not None for key in period_keys)


def _est_kind(name: str | None) -> str | None:
    name_u = (name or "").upper()
    if "ТИТЭС" in name_u:
        return "tites"
    if "ЕЭС" in name_u:
        return "ees"
    return None


def build_control_aggregates(
    res_control: dict[int, dict[int, Any]],
    *,
    period_keys: list[int],
    res_to_ues: dict[int, int],
    res_to_est: dict[int, int],
    res_to_sa_ids: dict[int, frozenset[int]] | dict[int, list[int]],
) -> dict[str, Any]:
    """Суммы контрольной выработки РЭС по ОЭС / типу ЭС / СЗ / России."""
    ues_totals: dict[int, dict] = defaultdict(dict)
    est_totals: dict[int, dict] = defaultdict(dict)
    sa_totals: dict[int, dict] = defaultdict(dict)
    total: dict = {}

    for res_id, periods in (res_control or {}).items():
        ues_id = res_to_ues.get(res_id)
        est_id = res_to_est.get(res_id)
        sa_ids = res_to_sa_ids.get(res_id) or ()
        for key in period_keys:
            value = (periods or {}).get(key)
            if value is None:
                continue
            _add_period_sum(total, key, value)
            if ues_id not in (None, -1):
                _add_period_sum(ues_totals[ues_id], key, value)
            if est_id not in (None, -1):
                _add_period_sum(est_totals[est_id], key, value)
            for sa_id in sa_ids:
                if sa_id not in (None, -1, 0):
                    _add_period_sum(sa_totals[sa_id], key, value)

    return {
        "regional_energy_systems": dict(res_control or {}),
        "union_energy_systems": dict(ues_totals),
        "energy_system_types": dict(est_totals),
        "synchronous_areas": dict(sa_totals),
        "total": total,
    }


def _sum_period_dicts(
    maps: list[dict | None],
    period_keys: list[int],
) -> dict[int, Decimal | None]:
    out: dict[int, Decimal | None] = {}
    for key in period_keys:
        total: Decimal | None = None
        for item in maps:
            value = (item or {}).get(key)
            if value is None:
                continue
            total = Decimal(str(total or 0)) + Decimal(str(value))
        out[key] = total
    return out


def _diff_period_dicts(
    left: dict | None,
    right: dict | None,
    period_keys: list[int],
) -> dict[int, Decimal | None]:
    out: dict[int, Decimal | None] = {}
    for key in period_keys:
        left_value = (left or {}).get(key)
        right_value = (right or {}).get(key)
        if left_value is None and right_value is None:
            out[key] = None
            continue
        out[key] = Decimal(str(left_value or 0)) - Decimal(str(right_value or 0))
    return out


def _ues_sa_ids(
    ues_id: int,
    ues_to_res_ids: dict[int, list[int]],
    res_to_sa_map: dict,
) -> set[int]:
    sa_ids: set[int] = set()
    for res_id in ues_to_res_ids.get(ues_id) or []:
        for sa_id in res_to_sa_map.get(res_id) or []:
            if sa_id not in (None, -1, 0):
                sa_ids.add(int(sa_id))
    return sa_ids


def _sa_child_period_maps(
    sa_id: int,
    *,
    ues_totals: dict,
    res_totals: dict,
    sorted_union_energy_system_ids: list[int],
    ues_to_res_ids: dict[int, list[int]],
    res_to_sa_map: dict,
    regional_energy_system_names: dict[int, str],
) -> list[dict]:
    """ОЭС, целиком входящие в СЗ, иначе РЭС этой СЗ (без двойного счёта)."""
    child_maps: list[dict] = []
    for ues_id in sorted_union_energy_system_ids:
        if ues_id in (None, -1, 0):
            continue
        sa_ids = _ues_sa_ids(ues_id, ues_to_res_ids, res_to_sa_map)
        if sa_ids == {sa_id}:
            child_maps.append(ues_totals.get(ues_id) or {})
            continue
        if sa_id not in sa_ids:
            continue
        for res_id in ues_to_res_ids.get(ues_id) or []:
            res_name = regional_energy_system_names.get(res_id) or ""
            if res_id in (None, -1, 0) or _is_unspecified_name(res_name):
                continue
            if sa_id in (res_to_sa_map.get(res_id) or []):
                child_maps.append(res_totals.get(res_id) or {})
    return child_maps


def _row(
    *,
    label: str,
    level: str,
    row_class: str,
    period_totals: dict,
    period_keys: list[int],
    rounding_digits: int,
    entity_id: int | None = None,
    editable: bool = False,
    ues_id: int | None = None,
    est_id: int | None = None,
    sa_ids: list[int] | None = None,
    is_verification: bool = False,
    info_tooltip: str | None = None,
) -> dict[str, Any]:
    show_zero = bool(is_verification)
    return {
        "label": label,
        "level": level,
        "row_class": row_class,
        "entity_id": entity_id,
        "editable": bool(editable) and not is_verification,
        "ues_id": ues_id,
        "est_id": est_id,
        "sa_ids": list(sa_ids or []),
        "is_verification": bool(is_verification),
        "info_tooltip": info_tooltip or "",
        "period_values": {key: period_totals.get(key) for key in period_keys},
        "input_values": {
            key: format_generation_input_value(period_totals.get(key), rounding_digits)
            for key in period_keys
        },
        "cell_nonzero": [
            is_verification_nonzero(period_totals.get(key)) for key in period_keys
        ],
        "cells": [
            format_generation_cell(
                period_totals.get(key), rounding_digits, show_zero=show_zero
            )
            for key in period_keys
        ],
    }


def build_ee_generation_totals_rows(
    *,
    aggregates: dict[str, Any],
    period_columns: list[tuple[int, str]],
    aggregation_types: list[str],
    rounding_digits: int,
    energy_system_type_names: dict[int, str],
    sorted_energy_system_type_ids: list[int],
    union_energy_system_names: dict[int, str],
    sorted_union_energy_system_ids: list[int],
    regional_energy_system_names: dict[int, str],
    ues_to_res_ids: dict[int, list[int]],
    synchronous_area_names: dict[int, str] | None = None,
    sorted_synchronous_area_ids: list[int] | None = None,
    show_res: bool = True,
    res_to_est: dict[int, int] | None = None,
    res_to_sa_ids: dict[int, frozenset[int]] | dict[int, list[int]] | None = None,
    ues_to_est: dict[int, int] | None = None,
) -> list[dict[str, Any]]:
    """Строки витрины: Россия, затем ЕЭС/ТИТЭС, СЗ, ОЭС (опционально с РЭС)."""
    period_keys = [period_key for period_key, _label in period_columns]
    est_totals = aggregates.get("energy_system_types") or {}
    ues_totals = aggregates.get("union_energy_systems") or {}
    res_totals = aggregates.get("regional_energy_systems") or {}
    res_to_est_map = res_to_est or {}
    res_to_sa_map = res_to_sa_ids or {}
    ues_to_est_map = ues_to_est or {}
    tites_id = None
    for est_id in sorted_energy_system_type_ids:
        if _est_kind(energy_system_type_names.get(est_id) or "") == "tites":
            tites_id = est_id
    named_ues_ids = [
        ues_id
        for ues_id in sorted_union_energy_system_ids
        if ues_id not in (None, -1, 0)
        and not _is_unspecified_name(union_energy_system_names.get(ues_id) or "")
    ]

    def _verify_row(*, label: str, tooltip: str, period_totals: dict, entity_id=None) -> dict[str, Any]:
        return _row(
            label=label,
            level="verification",
            row_class="ee-totals-verify-row",
            period_totals=period_totals,
            period_keys=period_keys,
            rounding_digits=rounding_digits,
            entity_id=entity_id,
            editable=False,
            is_verification=True,
            info_tooltip=tooltip,
        )

    rows: list[dict[str, Any]] = []

    if "russia" in aggregation_types:
        rows.append(
            _row(
                label="Россия, всего",
                level="russia",
                row_class="table-danger",
                period_totals=aggregates.get("total") or {},
                period_keys=period_keys,
                rounding_digits=rounding_digits,
                editable=True,
            )
        )

    for est_id in sorted_energy_system_type_ids:
        name = energy_system_type_names.get(est_id) or ""
        if _is_unspecified_name(name):
            continue
        kind = _est_kind(name)
        if kind is None or kind not in aggregation_types:
            continue
        rows.append(
            _row(
                label=f"{name}, всего",
                level="est",
                row_class="table-info" if kind == "ees" else "table-warning",
                period_totals=est_totals.get(est_id) or {},
                period_keys=period_keys,
                rounding_digits=rounding_digits,
                entity_id=est_id,
                editable=True,
            )
        )
        if kind == "ees":
            oes_sum = _sum_period_dicts(
                [ues_totals.get(ues_id) or {} for ues_id in named_ues_ids],
                period_keys,
            )
            tites_totals = est_totals.get(tites_id) or {} if tites_id else {}
            children = _sum_period_dicts([oes_sum, tites_totals], period_keys)
            rows.append(
                _verify_row(
                    label="Проверка для ЕЭС России",
                    tooltip=(
                        "Проверка для ЕЭС России = ЕЭС России, всего − "
                        "сумма выработки ЭЭ по всем ОЭС − ТИТЭС, всего"
                    ),
                    period_totals=_diff_period_dicts(
                        est_totals.get(est_id) or {}, children, period_keys
                    ),
                    entity_id=est_id,
                )
            )

    if "sz" in aggregation_types:
        sa_totals = aggregates.get("synchronous_areas") or {}
        sa_names = synchronous_area_names or {}
        for sa_id in sorted_synchronous_area_ids or []:
            sa_name = sa_names.get(sa_id) or ""
            if _is_unspecified_name(sa_name) or sa_id in (None, -1, 0):
                continue
            rows.append(
                _row(
                    label=f"{sa_name}, всего",
                    level="sa",
                    row_class="table-secondary",
                    period_totals=sa_totals.get(sa_id) or {},
                    period_keys=period_keys,
                    rounding_digits=rounding_digits,
                    entity_id=sa_id,
                    editable=True,
                )
            )
            sa_children = _sum_period_dicts(
                _sa_child_period_maps(
                    sa_id,
                    ues_totals=ues_totals,
                    res_totals=res_totals,
                    sorted_union_energy_system_ids=named_ues_ids,
                    ues_to_res_ids=ues_to_res_ids,
                    res_to_sa_map=res_to_sa_map,
                    regional_energy_system_names=regional_energy_system_names,
                ),
                period_keys,
            )
            rows.append(
                _verify_row(
                    label=f"Проверка для {sa_name}",
                    tooltip=(
                        f"Проверка для {sa_name} = {sa_name}, всего − "
                        "сумма выработки ЭЭ по всем ОЭС и РЭС, входящим в эту синхронную зону"
                    ),
                    period_totals=_diff_period_dicts(
                        sa_totals.get(sa_id) or {}, sa_children, period_keys
                    ),
                    entity_id=sa_id,
                )
            )

    if "oes" in aggregation_types:
        for ues_id in sorted_union_energy_system_ids:
            ues_name = union_energy_system_names.get(ues_id) or ""
            if _is_unspecified_name(ues_name) or ues_id in (None, -1, 0):
                continue
            nested_res_rows: list[dict[str, Any]] = []
            seen_res: set[int] = set()
            for res_id in ues_to_res_ids.get(ues_id) or []:
                if res_id in seen_res or res_id in (None, -1, 0):
                    continue
                seen_res.add(res_id)
                res_name = regional_energy_system_names.get(res_id) or ""
                if _is_unspecified_name(res_name):
                    continue
                sa_ids = sorted(res_to_sa_map.get(res_id) or [])
                nested_res_rows.append(
                    _row(
                        label=f"{res_name}, всего",
                        level="res",
                        row_class="table-secondary",
                        period_totals=res_totals.get(res_id) or {},
                        period_keys=period_keys,
                        rounding_digits=rounding_digits,
                        entity_id=res_id,
                        editable=True,
                        ues_id=ues_id,
                        est_id=res_to_est_map.get(res_id) or ues_to_est_map.get(ues_id),
                        sa_ids=sa_ids,
                    )
                )
            nested_res_rows.sort(key=lambda item: (item.get("label") or "").lower())
            if not nested_res_rows and not _has_period_values(
                ues_totals.get(ues_id) or {}, period_keys
            ):
                continue
            rows.append(
                _row(
                    label=f"{ues_name}, всего",
                    level="ues",
                    row_class="table-primary",
                    period_totals=ues_totals.get(ues_id) or {},
                    period_keys=period_keys,
                    rounding_digits=rounding_digits,
                    entity_id=ues_id,
                    editable=True,
                    est_id=ues_to_est_map.get(ues_id),
                )
            )
            if show_res:
                rows.extend(nested_res_rows)
            res_sum = _sum_period_dicts(
                [res_totals.get(row["entity_id"]) or {} for row in nested_res_rows],
                period_keys,
            )
            rows.append(
                _verify_row(
                    label=f"Проверка для {ues_name}",
                    tooltip=(
                        f"Проверка для {ues_name} = {ues_name}, всего − "
                        "сумма выработки ЭЭ по всем РЭС данной ОЭС"
                    ),
                    period_totals=_diff_period_dicts(
                        ues_totals.get(ues_id) or {}, res_sum, period_keys
                    ),
                    entity_id=ues_id,
                )
            )

    return rows


def _ues_to_res_from_maps(res_to_ues: dict[int, int]) -> dict[int, list[int]]:
    combined: dict[int, list[int]] = defaultdict(list)
    for ues_id, res_ids in (get_ues_to_res_ids_map() or {}).items():
        if ues_id in (None, -1):
            continue
        for res_id in res_ids or []:
            if res_id not in (None, -1) and res_id not in combined[ues_id]:
                combined[ues_id].append(res_id)
    for res_id, ues_id in res_to_ues.items():
        if ues_id in (None, -1) or res_id in (None, -1):
            continue
        if res_id not in combined[ues_id]:
            combined[ues_id].append(res_id)
    return dict(combined)


def _sorted_synchronous_area_ids(synchronous_area_list: list) -> tuple[list[int], dict[int, str]]:
    """Порядок СЗ как на /refdata/synchronous_area: display_order по возрастанию, NULL в конце."""
    filtered = [
        sa
        for sa in synchronous_area_list
        if getattr(sa, "id", None)
        and sa.id > 0
        and not _is_unspecified_name(getattr(sa, "name", None))
    ]
    filtered.sort(key=synchronous_area_display_order_sort_key)
    names = {sa.id: sa.name for sa in filtered if sa.id}
    return [sa.id for sa in filtered], names


def build_ee_generation_totals_summary_context(
    *,
    start_year: int,
    end_year: int,
    aggregation_types: list[str],
    rounding_digits: int,
    filter_year_list: list[int] | None = None,
    show_res: bool = True,
) -> dict[str, Any]:
    if start_year > end_year:
        start_year, end_year = end_year, start_year

    period_columns = build_year_columns(start_year, end_year)
    period_keys = [period_key for period_key, _label in period_columns]
    regional_energy_system_names = dict(get_regional_energy_systems_name_map() or {})
    res_ids = [
        res_id
        for res_id in regional_energy_system_names
        if res_id not in (None, -1, 0)
    ]
    res_control = load_annual_res_control_generation_by_res(
        res_ids, start_year, end_year
    )
    res_to_ues = dict(get_res_to_ues_id_map() or {})
    res_to_est = dict(get_res_to_est_id_map() or {})
    res_to_sa_ids = dict(get_res_to_synchronous_area_ids_map() or {})
    ues_to_est = dict(get_ues_to_est_id_map() or {})
    aggregates = build_control_aggregates(
        res_control,
        period_keys=period_keys,
        res_to_ues=res_to_ues,
        res_to_est=res_to_est,
        res_to_sa_ids=res_to_sa_ids,
    )
    aggregates = overlay_hierarchy_control(
        aggregates,
        load_hierarchy_control_generation(start_year, end_year),
    )

    energy_system_type_list = get_energy_system_type_list_full()
    energy_system_type_names = get_energy_system_type_map()
    sorted_energy_system_type_ids = [
        est.id for est in energy_system_type_list if est.id not in (None, 0)
    ]

    union_energy_system_names = dict(get_union_energy_systems_map() or {})
    ues_display_orders = get_union_energy_system_display_order_map()
    union_energy_system_list = [
        ues
        for ues in get_union_energy_system_list_full()
        if ues.id
        and not _is_unspecified_name(getattr(ues, "name", None))
    ]
    sorted_union_energy_system_ids = sorted(
        [ues.id for ues in union_energy_system_list if ues.id],
        key=lambda uid: union_energy_system_hierarchy_sort_key(
            uid, union_energy_system_names, ues_display_orders
        ),
    )
    ues_to_res_ids = _ues_to_res_from_maps(res_to_ues)
    sorted_synchronous_area_ids, synchronous_area_names = _sorted_synchronous_area_ids(
        get_synchronous_area_list_full()
    )

    rows = build_ee_generation_totals_rows(
        aggregates=aggregates,
        period_columns=period_columns,
        aggregation_types=aggregation_types,
        rounding_digits=rounding_digits,
        energy_system_type_names=energy_system_type_names,
        sorted_energy_system_type_ids=sorted_energy_system_type_ids,
        union_energy_system_names=union_energy_system_names,
        sorted_union_energy_system_ids=sorted_union_energy_system_ids,
        regional_energy_system_names=regional_energy_system_names,
        ues_to_res_ids=ues_to_res_ids,
        synchronous_area_names=synchronous_area_names,
        sorted_synchronous_area_ids=sorted_synchronous_area_ids,
        show_res=show_res,
        res_to_est=res_to_est,
        res_to_sa_ids=res_to_sa_ids,
        ues_to_est=ues_to_est,
    )

    year_list = list(filter_year_list or [])
    if not year_list:
        year_list = get_year_numbers_sorted_for_current_db_version() or list(
            range(start_year, end_year + 1)
        )
    year_list = sorted(set(year_list) | {int(start_year), int(end_year)})

    return {
        "page_title": "Выработка ЭЭ - агрегационные суммы",
        "start_year": start_year,
        "end_year": end_year,
        "rounding_digits": rounding_digits,
        "aggregation_types": aggregation_types,
        "show_res": show_res,
        "period_columns": period_columns,
        "year_features": get_year_feature_dict(),
        "filter_year_list": year_list,
        "rows": rows,
    }

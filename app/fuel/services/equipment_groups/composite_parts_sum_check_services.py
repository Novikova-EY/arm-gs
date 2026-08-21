# -*- coding: utf-8 -*-
"""
Контроль Access «Проверка-суммы-частей»: parent.FuelParam.X − Σ children.X.

Порог как у коллег: |Δ| > 0.5 → подсветка ячейки родителя и текст с цифрами.
Если у станции (родителя) ved>0, учёт на уровне станции — сумму по детям не сверяем.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable, Mapping

from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.services.equipment_groups.composite_station_semantics import (
    fuel_param_row_participates,
    is_composite_child_group,
    is_composite_parent_group,
)

# Поля как в Access «Проверка-суммы-частей(просмотр)» + бассейны витрины параметров.
COMPOSITE_PARTS_SUM_CHECK_ATTRS: tuple[str, ...] = (
    "e",
    "q",
    "qotr",
    "b",
    "gaz",
    "isk_gaz",
    "mazut",
    "torf",
    "slan",
    "proch",
    "ugol",
    "don",
    "podm",
    "pech",
    "arkt",
    "kuzn",
    "ural",
    "bashk",
    "kazah",
    "kan",
    "tung",
    "irkut",
    "hak",
    "tuv",
    "bur",
    "chit",
    "yakut",
    "amur",
    "urg",
    "ushum",
    "prim",
    "mag",
    "chukot",
    "kamch",
    "sah",
)

COMPOSITE_PARTS_SUM_MISMATCH_THRESHOLD = Decimal("0.5")

_DEFAULT_LABELS: dict[str, str] = {
    "e": "E",
    "q": "Q",
    "qotr": "QOTR",
    "b": "B",
    "gaz": "Газ",
    "isk_gaz": "Иск. газ",
    "mazut": "Мазут",
    "torf": "Торф",
    "slan": "Сланцы",
    "proch": "Прочее",
    "ugol": "Уголь",
    "don": "Дон",
    "podm": "Подм",
    "pech": "Печ",
    "arkt": "Арктикуголь",
    "kuzn": "Кузбасс",
    "ural": "Урал",
    "bashk": "Башкортостан",
    "kazah": "Казахстан",
    "kan": "Канск",
    "tung": "Тунгусск",
    "irkut": "Иркутск",
    "hak": "Хакасия",
    "tuv": "Тува",
    "bur": "Бурятия",
    "chit": "Чита",
    "yakut": "Якутия",
    "amur": "Амур",
    "urg": "Юрга",
    "ushum": "Ушумун",
    "prim": "Приморье",
    "mag": "Магадан",
    "chukot": "Чукотка",
    "kamch": "Камчатка",
    "sah": "Сахалин",
}


def _to_decimal(value: Any) -> Decimal:
    """Access Nz(x, 0): None / пусто → 0."""
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _is_real_fuel_param(param: Any) -> bool:
    """Синтетическая строка «…, всего» без сохранённого FuelParam — не сверяем."""
    if param is None:
        return False
    if isinstance(param, EquipmentGroupFuelParam):
        return True
    # Duck-typing для тестов / detached объектов с id строки параметров.
    return getattr(param, "id", None) is not None


def _format_decimal(value: Decimal, rounding_digits: int) -> str:
    if rounding_digits is None or rounding_digits < 0:
        text = format(value.normalize(), "f")
    else:
        quant = Decimal("1").scaleb(-int(rounding_digits))
        text = format(value.quantize(quant, rounding=ROUND_HALF_UP), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _attr_label(attr: str, labels: Mapping[str, str] | None) -> str:
    if labels and attr in labels and labels[attr]:
        return str(labels[attr])
    return _DEFAULT_LABELS.get(attr, attr)


def build_mismatch_message(
    *,
    attr: str,
    parent_value: Decimal,
    children_sum: Decimal,
    delta: Decimal,
    labels: Mapping[str, str] | None = None,
    rounding_digits: int = 1,
) -> str:
    label = _attr_label(attr, labels)
    p_s = _format_decimal(parent_value, rounding_digits)
    c_s = _format_decimal(children_sum, rounding_digits)
    d_s = _format_decimal(abs(delta), rounding_digits)
    return (
        f"{label}: у родителя {p_s}, сумма по группам {c_s}, "
        f"расхождение {d_s} (порог {COMPOSITE_PARTS_SUM_MISMATCH_THRESHOLD})"
    )


def compare_parent_to_children_sum(
    parent_param: Any,
    child_params: Iterable[Any],
    *,
    attrs: Iterable[str] = COMPOSITE_PARTS_SUM_CHECK_ATTRS,
    threshold: Decimal = COMPOSITE_PARTS_SUM_MISMATCH_THRESHOLD,
    labels: Mapping[str, str] | None = None,
    rounding_digits: int = 1,
) -> dict[str, dict[str, Any]]:
    """
    Сверяет один год: parent − Σ children по attrs.
    Возвращает {attr: {parent, children_sum, delta, message}} только для |Δ| > threshold.

    Если у родителя ved>0, станция учитывается целиком (station_only) —
    сумму по детям не сверяем.
    """
    children = [p for p in child_params if p is not None]
    if not _is_real_fuel_param(parent_param) or not children:
        return {}
    if fuel_param_row_participates(parent_param):
        return {}

    out: dict[str, dict[str, Any]] = {}
    for attr in attrs:
        parent_v = _to_decimal(getattr(parent_param, attr, None))
        children_sum = sum(
            (_to_decimal(getattr(p, attr, None)) for p in children),
            Decimal("0"),
        )
        delta = parent_v - children_sum
        if abs(delta) <= threshold:
            continue
        out[attr] = {
            "parent": parent_v,
            "children_sum": children_sum,
            "delta": delta,
            "message": build_mismatch_message(
                attr=attr,
                parent_value=parent_v,
                children_sum=children_sum,
                delta=delta,
                labels=labels,
                rounding_digits=rounding_digits,
            ),
        }
    return out


def _param_by_year(rows: list | None) -> dict[int, Any]:
    by_year: dict[int, Any] = {}
    for _eg, param in rows or []:
        if param is None:
            continue
        y = getattr(param, "year_number", None)
        if y is None:
            continue
        by_year[int(y)] = param
    return by_year


def build_composite_parts_sum_mismatch_for_station_block(
    station_block: Mapping[str, Any],
    *,
    attrs: Iterable[str] = COMPOSITE_PARTS_SUM_CHECK_ATTRS,
    threshold: Decimal = COMPOSITE_PARTS_SUM_MISMATCH_THRESHOLD,
    labels: Mapping[str, str] | None = None,
    rounding_digits: int = 1,
) -> dict[str, dict[str, dict[str, Any]]]:
    """
    По одному station_block составной станции.
    Ключ: «{parent_eg_id}:{year}» → {attr → details}.
    """
    if not station_block.get("has_composite_structure"):
        return {}

    parent_gb = None
    child_gbs: list = []
    for gb in station_block.get("group_blocks") or []:
        eg = gb.get("equipment_group")
        if gb.get("is_composite_parent") or is_composite_parent_group(eg):
            parent_gb = gb
        elif gb.get("is_composite_child") or is_composite_child_group(eg):
            child_gbs.append(gb)

    if parent_gb is None or not child_gbs:
        return {}

    parent_eg = parent_gb.get("equipment_group")
    parent_id = getattr(parent_eg, "id", None)
    if parent_id is None:
        parent_id = station_block.get("composite_parent_eg_id")
    if parent_id is None:
        return {}

    parent_by_year = _param_by_year(parent_gb.get("rows"))
    children_by_year: dict[int, list] = {}
    for gb in child_gbs:
        for y, param in _param_by_year(gb.get("rows")).items():
            children_by_year.setdefault(y, []).append(param)

    result: dict[str, dict[str, dict[str, Any]]] = {}
    for year, parent_param in parent_by_year.items():
        mismatches = compare_parent_to_children_sum(
            parent_param,
            children_by_year.get(year) or [],
            attrs=attrs,
            threshold=threshold,
            labels=labels,
            rounding_digits=rounding_digits,
        )
        if mismatches:
            result[f"{int(parent_id)}:{int(year)}"] = mismatches
    return result


def build_composite_parts_sum_mismatch_by_row(
    hierarchy: list | None,
    *,
    attrs: Iterable[str] = COMPOSITE_PARTS_SUM_CHECK_ATTRS,
    threshold: Decimal = COMPOSITE_PARTS_SUM_MISMATCH_THRESHOLD,
    labels: Mapping[str, str] | None = None,
    rounding_digits: int = 1,
) -> dict[str, dict[str, dict[str, Any]]]:
    """
    Обход иерархии витрины параметров.
    Возвращает map «{parent_eg_id}:{year}» → {attr → {parent, children_sum, delta, message}}.
    """
    merged: dict[str, dict[str, dict[str, Any]]] = {}
    for est in hierarchy or []:
        for ues in est.get("ues_list") or []:
            for res in ues.get("res_list") or []:
                for sb in res.get("station_blocks") or []:
                    part = build_composite_parts_sum_mismatch_for_station_block(
                        sb,
                        attrs=attrs,
                        threshold=threshold,
                        labels=labels,
                        rounding_digits=rounding_digits,
                    )
                    merged.update(part)
    return merged

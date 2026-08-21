# -*- coding: utf-8 -*-
"""
Пересчёт строки родителя составной станции как Σ детей.

Access: кнопка «Сумма» формы «Редактирование» (Сумма_Click) + запрос
«Сумма_частей(выборка)»: GROUP BY MAIN, YEAR; Sum(Nz(поле,0));
EURT = IIf(EOTP>0, EUST/EOTP*1000, 0); TURT = IIf(Q>0, TUST/Q*1000, 0).
Доп. угли (sd) тоже суммируются; строка доп. параметров создаётся, если есть
значение > 0 (bdop).
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Sequence

from sqlalchemy import or_

from app.common.services.database_version_filter import (
    get_current_db_version_id,
    set_db_version_on_create,
)
from app.extensions import db
from app.fuel.models.fue_equipment_group_extra_fuel_param_model import (
    EquipmentGroupExtraFuelParam,
)
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.services.equipment_groups.composite_station_semantics import (
    _as_int,
    is_composite_parent_group,
)
from app.fuel.services.equipment_groups.equipment_group_extra_fuel_params_services import (
    EQUIPMENT_GROUP_DETAILS_EXTRA_ATTRS,
)
from app.fuel.services.equipment_groups.equipment_group_extra_fuel_params_write_services import (
    save_equipment_group_extra_fuel_params_for_year,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
    compute_fuel_param_derived_value,
    fill_missing_hours_on_fuel_param,
)

# Access «Сумма_частей(выборка)» Sum(...) + объёмные поля АРМ (isk_gaz, sn_ee, sn_te, nt_sum).
COMPOSITE_PARTS_RECALC_SUM_ATTRS: tuple[str, ...] = (
    "nust",
    "nr",
    "e",
    "ewtp",
    "eotp",
    "eust",
    "sn_ee",
    "q",
    "qotr",
    "tust",
    "sn_te",
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
    "nt",
    "nt_sum",
)

COMPOSITE_PARTS_RECALC_EXTRA_ATTRS: tuple[str, ...] = tuple(
    EQUIPMENT_GROUP_DETAILS_EXTRA_ATTRS
)

_RATIO_SCALE = Decimal("1000")


def _to_decimal(value: Any) -> Decimal:
    """Access Nz(x, 0): None / пусто → 0."""
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def sum_attr_from_records(records: Iterable[Any], attr: str) -> Decimal:
    """Σ Nz(record.attr, 0) по записям."""
    return sum((_to_decimal(getattr(r, attr, None)) for r in records), Decimal("0"))


def access_ratio_or_zero(numerator: Any, denominator: Any) -> Decimal:
    """Access IIf(denom>0, num/denom*1000, 0) — EURT / TURT."""
    denom = _to_decimal(denominator)
    if denom <= 0:
        return Decimal("0")
    return _to_decimal(numerator) / denom * _RATIO_SCALE


def build_parent_sums_from_children(
    child_params: Sequence[Any],
    *,
    attrs: Iterable[str] = COMPOSITE_PARTS_RECALC_SUM_ATTRS,
) -> dict[str, Decimal]:
    """
    Суммы объёмных полей и Access-удельные EURT/TURT по уже отобранным детям.
    """
    children = [p for p in child_params if p is not None]
    sums: dict[str, Decimal] = {
        attr: sum_attr_from_records(children, attr) for attr in attrs
    }
    sums["eurt"] = access_ratio_or_zero(sums.get("eust"), sums.get("eotp"))
    sums["turt"] = access_ratio_or_zero(sums.get("tust"), sums.get("q"))
    return sums


def _load_composite_child_groups(parent: EquipmentGroup) -> list[EquipmentGroup]:
    """Дочерние EG: MAIN = parent.NUMB, та же версия БД (как карточка группы)."""
    parent_numb = _as_int(getattr(parent, "numb", None))
    if parent_numb is None:
        return []

    child_q = EquipmentGroup.query.filter(EquipmentGroup.main == parent_numb)
    parent_vid = getattr(parent, "database_version_id", None)
    if parent_vid is None:
        parent_vid = get_current_db_version_id()

    if parent_vid is not None:
        versioned = (
            child_q.filter(EquipmentGroup.database_version_id == parent_vid)
            .order_by(EquipmentGroup.id.asc())
            .all()
        )
        if versioned:
            return versioned
        return (
            child_q.filter(EquipmentGroup.database_version_id.is_(None))
            .order_by(EquipmentGroup.id.asc())
            .all()
        )
    return (
        child_q.filter(EquipmentGroup.database_version_id.is_(None))
        .order_by(EquipmentGroup.id.asc())
        .all()
    )


def _pick_param_for_year(
    rows: Sequence[Any],
    year_number: int,
    version_id: int | None,
) -> Any | None:
    matched = [
        p
        for p in rows
        if p is not None and _as_int(getattr(p, "year_number", None)) == int(year_number)
    ]
    if not matched:
        return None
    if version_id is not None:
        for p in matched:
            if getattr(p, "database_version_id", None) == version_id:
                return p
    for p in matched:
        if getattr(p, "database_version_id", None) is None:
            return p
    return matched[0]


def _load_fuel_params_for_groups(
    group_ids: Sequence[int],
    year_number: int,
) -> list[EquipmentGroupFuelParam]:
    if not group_ids:
        return []
    version_id = get_current_db_version_id()
    q = EquipmentGroupFuelParam.query.filter(
        EquipmentGroupFuelParam.equipment_group_id.in_(list(group_ids)),
        EquipmentGroupFuelParam.year_number == int(year_number),
    )
    if version_id is not None:
        q = q.filter(
            or_(
                EquipmentGroupFuelParam.database_version_id == version_id,
                EquipmentGroupFuelParam.database_version_id.is_(None),
            )
        )
    else:
        q = q.filter(EquipmentGroupFuelParam.database_version_id.is_(None))
    by_gid: dict[int, list[EquipmentGroupFuelParam]] = {}
    for row in q.all():
        gid = getattr(row, "equipment_group_id", None)
        if gid is None:
            continue
        by_gid.setdefault(int(gid), []).append(row)
    picked: list[EquipmentGroupFuelParam] = []
    for gid in group_ids:
        row = _pick_param_for_year(by_gid.get(int(gid), []), year_number, version_id)
        if row is not None:
            picked.append(row)
    return picked


def _load_extra_params_for_groups(
    group_ids: Sequence[int],
    year_number: int,
) -> list[EquipmentGroupExtraFuelParam]:
    if not group_ids:
        return []
    version_id = get_current_db_version_id()
    q = EquipmentGroupExtraFuelParam.query.filter(
        EquipmentGroupExtraFuelParam.equipment_group_id.in_(list(group_ids)),
        EquipmentGroupExtraFuelParam.year_number == int(year_number),
    )
    if version_id is not None:
        q = q.filter(
            or_(
                EquipmentGroupExtraFuelParam.database_version_id == version_id,
                EquipmentGroupExtraFuelParam.database_version_id.is_(None),
            )
        )
    else:
        q = q.filter(EquipmentGroupExtraFuelParam.database_version_id.is_(None))
    by_gid: dict[int, list[EquipmentGroupExtraFuelParam]] = {}
    for row in q.all():
        gid = getattr(row, "equipment_group_id", None)
        if gid is None:
            continue
        by_gid.setdefault(int(gid), []).append(row)
    picked: list[EquipmentGroupExtraFuelParam] = []
    for gid in group_ids:
        row = _pick_param_for_year(by_gid.get(int(gid), []), year_number, version_id)
        if row is not None:
            picked.append(row)
    return picked


def _get_or_create_parent_fuel_param(
    parent: EquipmentGroup,
    year_number: int,
) -> EquipmentGroupFuelParam:
    version_id = get_current_db_version_id()
    existing = EquipmentGroupFuelParam.query.filter_by(
        equipment_group_id=parent.id,
        year_number=int(year_number),
    ).all()
    param = _pick_param_for_year(existing, year_number, version_id)
    if param is not None:
        if (
            version_id is not None
            and getattr(param, "database_version_id", None) != version_id
        ):
            param.database_version_id = version_id
        return param

    param = EquipmentGroupFuelParam(
        equipment_group_id=parent.id,
        year_number=int(year_number),
        database_version_id=version_id,
        name=getattr(parent, "name", None) or getattr(parent, "name_ext", None),
        numb1120=_as_int(getattr(parent, "numb", None)),
    )
    set_db_version_on_create(param)
    db.session.add(param)
    return param


def _apply_arm_derived_after_sum(param: EquipmentGroupFuelParam) -> None:
    """h / snk / sn_t по формулам АРМ, если есть входы (hfix=1 не трогает h)."""
    for attr in ("h", "snk", "sn_t"):
        calc = compute_fuel_param_derived_value(param, attr)
        if calc is not None:
            setattr(param, attr, calc)
    fill_missing_hours_on_fuel_param(param)


def recalculate_composite_parent_from_children(
    equipment_group_id: int,
    year_number: int,
) -> dict[str, Any]:
    """
    Пишет на родителя составной станции суммы детей за year_number.

    Возвращает dict: ok, error, updated_fuel, updated_extra, children_count,
    child_ids. Не делает commit.
    """
    parent = db.session.get(EquipmentGroup, int(equipment_group_id))
    if parent is None:
        return {"ok": False, "error": "Группа оборудования не найдена."}
    if not is_composite_parent_group(parent):
        return {
            "ok": False,
            "error": "Пересчёт доступен только для составной станции (признак comp=1).",
        }

    children = _load_composite_child_groups(parent)
    if not children:
        return {
            "ok": False,
            "error": "У составной станции нет дочерних групп оборудования.",
        }

    child_ids = [int(c.id) for c in children if getattr(c, "id", None) is not None]
    child_params = _load_fuel_params_for_groups(child_ids, year_number)
    if not child_params:
        return {
            "ok": False,
            "error": (
                f"Нет топливных параметров дочерних групп за {int(year_number)} год."
            ),
        }

    sums = build_parent_sums_from_children(child_params)
    parent_param = _get_or_create_parent_fuel_param(parent, year_number)
    for attr, value in sums.items():
        if hasattr(parent_param, attr):
            setattr(parent_param, attr, value)
    _apply_arm_derived_after_sum(parent_param)

    child_extras = _load_extra_params_for_groups(child_ids, year_number)
    extra_sums = {
        attr: sum_attr_from_records(child_extras, attr)
        for attr in COMPOSITE_PARTS_RECALC_EXTRA_ATTRS
    }
    has_positive_extra = any(v > 0 for v in extra_sums.values())
    existing_extra = EquipmentGroupExtraFuelParam.query.filter_by(
        equipment_group_id=parent.id,
        year_number=int(year_number),
    ).first()
    updated_extra = False
    if has_positive_extra or existing_extra is not None:
        extra_values = {attr: extra_sums[attr] for attr in COMPOSITE_PARTS_RECALC_EXTRA_ATTRS}
        _row, details = save_equipment_group_extra_fuel_params_for_year(
            equipment_group_id=int(parent.id),
            year_number=int(year_number),
            values=extra_values,
            commit=False,
        )
        updated_extra = bool(details) or has_positive_extra or existing_extra is not None

    return {
        "ok": True,
        "error": None,
        "updated_fuel": True,
        "updated_extra": updated_extra,
        "children_count": len(child_params),
        "child_ids": child_ids,
        "year_number": int(year_number),
        "equipment_group_id": int(parent.id),
    }

# -*- coding: utf-8 -*-
"""
Контроль составных станций на этапах Коэфф / Распред / Топливо.

Типичный промах: родитель в фильтре (ved>0) без E, а энергия посчитана
на дочерней группе с ved=0 — ребёнок не входит в (ved>0), ΣE дырявая.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Sequence

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.services.equipment_groups.composite_station_semantics import (
    fuel_param_row_participates,
    is_composite_child_group,
    is_composite_parent_group,
)

KIND_ENERGY_ON_INACTIVE_CHILD = "energy_on_inactive_child"
KIND_BOTH_LEVELS_ACTIVE = "both_levels_active"

# Как у «Проверка-суммы-частей»: мелочь ≤ 0.5 не считаем энергией.
ENERGY_NONEMPTY_THRESHOLD = Decimal("0.5")


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _energy_abs(param: Any | None) -> Decimal:
    if param is None:
        return Decimal("0")
    v = _as_decimal(getattr(param, "e", None))
    if v is None:
        return Decimal("0")
    return abs(v)


def _has_energy(param: Any | None) -> bool:
    return _energy_abs(param) > ENERGY_NONEMPTY_THRESHOLD


def _group_name(equipment_group: Any) -> str:
    if equipment_group is None:
        return ""
    return (
        getattr(equipment_group, "name", None)
        or getattr(equipment_group, "name_ext", None)
        or f"id={getattr(equipment_group, 'id', '')}"
    )


def _child_payload(equipment_group: Any, param: Any | None) -> dict:
    e = None if param is None else _as_decimal(getattr(param, "e", None))
    ved = None if param is None else getattr(param, "ved", None)
    return {
        "equipment_group_id": getattr(equipment_group, "id", None),
        "numb": getattr(equipment_group, "numb", None),
        "main": getattr(equipment_group, "main", None),
        "name": _group_name(equipment_group),
        "ved": ved,
        "e": e,
    }


def oes_code_from_groups(groups: Sequence[Any]) -> int | None:
    """Единственный oes среди групп; None — пусто или несколько ОЭС."""
    codes: set[int] = set()
    for group in groups:
        code = _as_int(getattr(group, "oes", None))
        if code is not None:
            codes.add(code)
    if len(codes) == 1:
        return next(iter(codes))
    return None


def classify_composite_cluster_energy_level(
    *,
    parent_group: Any,
    parent_param: Any | None,
    children: Sequence[tuple[Any, Any | None]],
) -> dict | None:
    """
    Промах уровня учёта за один год. None — кластер согласован с фильтром ved>0.

    parent_param — FuelParam расчётного года. Участие смотрим по ved этой строки,
    не по попаданию в фильтр из‑за базового года.
    """
    if parent_group is None or not is_composite_parent_group(parent_group):
        return None
    if not fuel_param_row_participates(parent_param):
        return None

    active_children: list[tuple[Any, Any]] = []
    inactive_with_energy: list[tuple[Any, Any]] = []
    for child_group, child_param in children:
        if child_group is None:
            continue
        if fuel_param_row_participates(child_param):
            active_children.append((child_group, child_param))
        elif _has_energy(child_param):
            inactive_with_energy.append((child_group, child_param))

    parent_e = _as_decimal(getattr(parent_param, "e", None)) if parent_param is not None else None
    parent_ved = getattr(parent_param, "ved", None) if parent_param is not None else None

    if active_children:
        child_e_sum = sum((_energy_abs(p) for _g, p in active_children), Decimal("0"))
        return {
            "kind": KIND_BOTH_LEVELS_ACTIVE,
            "parent_equipment_group_id": getattr(parent_group, "id", None),
            "parent_numb": getattr(parent_group, "numb", None),
            "parent_name": _group_name(parent_group),
            "parent_ved": parent_ved,
            "parent_e": parent_e,
            "children": [_child_payload(g, p) for g, p in active_children],
            "child_e_sum": child_e_sum,
            "message": (
                "Родитель и дочерние группы одновременно с ved>0 — риск двойного счёта. "
                "У родителя составной станции должен быть ved=0."
            ),
        }

    if inactive_with_energy and not _has_energy(parent_param):
        child_e_sum = sum((_energy_abs(p) for _g, p in inactive_with_energy), Decimal("0"))
        return {
            "kind": KIND_ENERGY_ON_INACTIVE_CHILD,
            "parent_equipment_group_id": getattr(parent_group, "id", None),
            "parent_numb": getattr(parent_group, "numb", None),
            "parent_name": _group_name(parent_group),
            "parent_ved": parent_ved,
            "parent_e": parent_e,
            "children": [_child_payload(g, p) for g, p in inactive_with_energy],
            "child_e_sum": child_e_sum,
            "message": (
                "Родитель в фильтре (ved>0) без E, энергия на дочерней группе с ved=0 — "
                "в сумму Распреда не входит."
            ),
        }

    return None


def _prefer_version_groups(
    groups: Sequence[EquipmentGroup],
    database_version_id: int | None,
) -> list[EquipmentGroup]:
    by_numb: dict[int, EquipmentGroup] = {}
    no_numb: list[EquipmentGroup] = []
    for group in groups:
        numb = group.numb
        if numb is None:
            no_numb.append(group)
            continue
        prev = by_numb.get(int(numb))
        if prev is None:
            by_numb[int(numb)] = group
            continue
        if database_version_id is not None:
            if prev.database_version_id == database_version_id:
                continue
            if group.database_version_id == database_version_id:
                by_numb[int(numb)] = group
    return list(by_numb.values()) + no_numb


def _pick_fuel_param(
    existing: EquipmentGroupFuelParam | None,
    candidate: EquipmentGroupFuelParam,
    database_version_id: int | None,
) -> EquipmentGroupFuelParam:
    def tier(row: EquipmentGroupFuelParam) -> int:
        vid = getattr(row, "database_version_id", None)
        if database_version_id is not None and vid == database_version_id:
            return 3
        if vid is None:
            return 2
        return 1

    if existing is None or tier(candidate) > tier(existing):
        return candidate
    return existing


def _parents_participating_in_year(
    session: Session,
    *,
    database_version_id: int | None,
    year_number: int,
    oes_code: int | None = None,
) -> list[EquipmentGroup]:
    """
    Родители составных станций с ved>0 за год на любой строке FuelParam.

    Не фильтруем FuelParam.database_version_id: строка года часто остаётся
    с vid другой версии, хотя EquipmentGroup уже в текущей — иначе Распред
    молча выкидывает станцию из (ved>0).

    oes_code ограничивает поиск той же ОЭС, что и текущий расчёт: иначе
    Липецк (oes=2) всплывает на странице Средней Волги (oes=3).
    """
    q = (
        session.query(EquipmentGroup)
        .join(
            EquipmentGroupFuelParam,
            EquipmentGroupFuelParam.equipment_group_id == EquipmentGroup.id,
        )
        .filter(EquipmentGroupFuelParam.year_number == int(year_number))
        .filter(EquipmentGroupFuelParam.ved.isnot(None))
        .filter(EquipmentGroupFuelParam.ved > 0)
    )
    if oes_code is not None:
        q = q.filter(
            or_(
                EquipmentGroup.oes == int(oes_code),
                EquipmentGroupFuelParam.oes == str(int(oes_code)),
            )
        )
    if database_version_id is not None and hasattr(EquipmentGroup, "database_version_id"):
        q = q.filter(
            or_(
                EquipmentGroup.database_version_id == database_version_id,
                EquipmentGroup.database_version_id.is_(None),
            )
        )
    return [
        g
        for g in _prefer_version_groups(q.all(), database_version_id)
        if is_composite_parent_group(g) and g.numb is not None
    ]


def find_composite_energy_level_issues(
    session: Session,
    *,
    database_version_id: int | None,
    year_number: int,
    selected_group_ids: Sequence[int],
) -> list[dict]:
    """
    Составные родители, у которых энергия на «не том» уровне за год.

    Смотрим группы фильтра Распреда и родителей той же ОЭС с ved>0 за год —
    даже если они не попали в отбор из‑за database_version_id на строке топлива.
    Родителей чужой ОЭС не трогаем (Липецк не должен всплывать на Средней Волге).
    """
    selected_ids = {int(gid) for gid in selected_group_ids if gid is not None}
    selected = []
    if selected_ids:
        selected = (
            session.query(EquipmentGroup)
            .filter(EquipmentGroup.id.in_(selected_ids))
            .all()
        )
    parents_by_id: dict[int, EquipmentGroup] = {}
    for group in selected:
        if is_composite_parent_group(group) and group.numb is not None:
            parents_by_id[group.id] = group
    oes_code = oes_code_from_groups(selected)
    if oes_code is not None:
        for group in _parents_participating_in_year(
            session,
            database_version_id=database_version_id,
            year_number=year_number,
            oes_code=oes_code,
        ):
            parents_by_id[group.id] = group
    parents = list(parents_by_id.values())
    if not parents:
        return []

    parent_numbs = [int(p.numb) for p in parents]
    child_q = session.query(EquipmentGroup).filter(
        EquipmentGroup.main.in_(parent_numbs)
    )
    if database_version_id is not None and hasattr(EquipmentGroup, "database_version_id"):
        child_q = child_q.filter(
            or_(
                EquipmentGroup.database_version_id == database_version_id,
                EquipmentGroup.database_version_id.is_(None),
            )
        )
    children = [
        g
        for g in _prefer_version_groups(child_q.all(), database_version_id)
        if is_composite_child_group(g)
    ]

    load_ids = [p.id for p in parents] + [c.id for c in children]
    fuel_rows = (
        session.query(EquipmentGroupFuelParam)
        .filter(
            EquipmentGroupFuelParam.equipment_group_id.in_(load_ids),
            EquipmentGroupFuelParam.year_number == int(year_number),
        )
        .all()
    )
    param_by_eg: dict[int, EquipmentGroupFuelParam] = {}
    for row in fuel_rows:
        gid = row.equipment_group_id
        param_by_eg[gid] = _pick_fuel_param(
            param_by_eg.get(gid), row, database_version_id
        )

    children_by_main: dict[int, list[EquipmentGroup]] = {}
    for child in children:
        children_by_main.setdefault(int(child.main), []).append(child)

    issues: list[dict] = []
    for parent in parents:
        kids = children_by_main.get(int(parent.numb), [])
        issue = classify_composite_cluster_energy_level(
            parent_group=parent,
            parent_param=param_by_eg.get(parent.id),
            children=[(kid, param_by_eg.get(kid.id)) for kid in kids],
        )
        if issue is None:
            continue
        issue["year_number"] = int(year_number)
        issue["in_filter"] = parent.id in selected_ids
        if not issue["in_filter"] and issue["kind"] == KIND_ENERGY_ON_INACTIVE_CHILD:
            issue["message"] = (
                "Родитель с ved>0 без E не попал в отбор Распреда, энергия на "
                "дочерней группе с ved=0 — в сумму не входит."
            )
        issues.append(issue)

    issues.sort(
        key=lambda item: (
            item.get("parent_numb") is None,
            item.get("parent_numb") if item.get("parent_numb") is not None else 0,
        )
    )
    return issues


def flash_text_for_composite_energy_level_issues(issues: Sequence[dict]) -> str | None:
    if not issues:
        return None
    n = len(issues)
    first = issues[0]
    name = first.get("parent_name") or f"numb={first.get('parent_numb')}"
    numb = first.get("parent_numb")
    suffix = f" (например {name}, numb={numb})" if n else ""
    if n == 1:
        return (
            f"Составная станция: {first.get('message')} "
            f"{name}, numb={numb}."
        )
    return (
        f"Составные станции: у {n} станций энергия не на том уровне учёта"
        f"{suffix}."
    )


def equipment_group_ids_for_composite_energy_level_issues(
    issues: Sequence[dict],
) -> list[int]:
    ids: list[int] = []
    seen: set[int] = set()
    for issue in issues:
        for raw in [issue.get("parent_equipment_group_id")] + [
            child.get("equipment_group_id") for child in (issue.get("children") or [])
        ]:
            if raw is None:
                continue
            gid = int(raw)
            if gid in seen:
                continue
            seen.add(gid)
            ids.append(gid)
    return ids

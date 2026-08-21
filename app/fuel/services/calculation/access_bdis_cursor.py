# -*- coding: utf-8 -*-
"""
Курсор Access FindFirst/FindNext по «Станции(Схема)» для Коэфф и Распред.

VBA Кнопка27 / Кнопка5:
  Set w = OpenRecordset(wname, DB_OPEN_DYNASET)
  w.FindFirst filter1
  Do Until w.NoMatch
    If year = byear Then hb = z(h): nustb = z(NUST)   ' и bnust1 = z(NUST) на Коэфф
    If year = cyear Then … использует hb / nustb / bnust1
    w.FindNext filter1

Индекс таблицы «Станции(Схема)»: unique numb1 = (numb1, v, YEAR).
hb не ищется по numb текущей станции — это значение с последней строки
базового года, на которую наехал курсор.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable, Sequence


def d0(value) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def parse_access_numb1(*candidates: Any) -> float:
    """Access Станции.numb1 — Double (256.1). Не путать с EG.n1 (мощность)."""
    for raw in candidates:
        if raw is None:
            continue
        s = str(raw).strip().replace(",", ".")
        if not s:
            continue
        try:
            return float(s)
        except ValueError:
            continue
    return 0.0


def access_dynaset_sort_key(
    *,
    numb1: Any,
    v: Any = 0,
    year: Any = 0,
) -> tuple[float, int, int]:
    """Порядок FindNext: индекс numb1 (numb1, v, YEAR)."""
    try:
        v_i = int(v or 0)
    except (TypeError, ValueError):
        v_i = 0
    try:
        y_i = int(year or 0)
    except (TypeError, ValueError):
        y_i = 0
    return (parse_access_numb1(numb1), v_i, y_i)


@dataclass
class AccessBdisCursorState:
    hb: Decimal = Decimal("0")
    nustb: Decimal = Decimal("0")
    bnust1: Decimal = Decimal("0")


def sort_access_filter_rows(
    rows: Sequence[Any],
    *,
    n1_of,
) -> list[Any]:
    """n1_of(row) → значение Access numb1 (EG.n1 / FuelParam.numb1 / numb)."""
    return sorted(
        rows,
        key=lambda r: access_dynaset_sort_key(
            numb1=n1_of(r),
            v=getattr(r, "v", None) or getattr(r, "variant_number", None) or 0,
            year=getattr(r, "year_number", None),
        ),
    )


def fuel_param_access_n1(fp: Any, groups_by_id: dict[int, Any] | None = None) -> Any:
    """Ключ FindNext: Access numb1 = EG.ordnumb. Поле n1 (установленная мощность) не использовать."""
    eg = getattr(fp, "equipment_group", None)
    gid = getattr(fp, "equipment_group_id", None)
    if groups_by_id is not None and gid is not None:
        eg = groups_by_id.get(gid) or eg
    return parse_access_numb1(
        getattr(eg, "ordnumb", None) if eg is not None else None,
        getattr(fp, "numb1", None),
        getattr(eg, "numb", None) if eg is not None else None,
        getattr(fp, "numb1120", None),
    )


def walk_access_bdis_cursor(
    rows: Iterable[Any],
    *,
    byear: int | None,
    cyear: int,
    state: AccessBdisCursorState | None = None,
) -> Iterable[tuple[str, Any, AccessBdisCursorState]]:
    """
    Как VBA: на каждой строке фильтра обновляет hb/nustb/bnust1 при year=byear
    и отдаёт расчётные строки year=cyear с текущим состоянием курсора.

    z(h): NULL/пусто → 0, без синтеза E/NUST.
    hb Dim на уровне Кнопка27 — не обнуляется на again:/BDis, только FindFirst
    с начала. Если первая строка cyear, берётся hb с конца прошлого прохода.
    """
    if state is None:
        state = AccessBdisCursorState()
    for row in rows:
        year = getattr(row, "year_number", None)
        try:
            year_i = int(year) if year is not None else None
        except (TypeError, ValueError):
            year_i = None
        if byear is not None and year_i == int(byear):
            state.hb = d0(getattr(row, "h", None))
            state.nustb = d0(getattr(row, "nust", None))
            state.bnust1 = state.nustb
            yield ("byear", row, state)
        if year_i == int(cyear):
            yield ("cyear", row, state)

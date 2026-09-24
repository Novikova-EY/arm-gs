# -*- coding: utf-8 -*-
"""Отбор удельных как Access U.Seek (Коэфф / Распред / Топливо — одна логика).

U.Index = numb2; Seek \">=\", numb1120, v, byear; последняя year ≤ cyear.
Годы раньше byear не входят. Пустая строка в окне — Match (как в таблице Access).
Нет строк в окне → None (Skip). Чужой Bookmark соседней станции не берём.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import and_, func, or_

from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)

SPECIFIC_PAYLOAD_ATTRS: tuple[str, ...] = (
    "y",
    "snk",
    "sntp",
    "bk",
    "btp",
    "snbas",
    "ksn",
    "bbas",
    "kh",
)


def _numeric_has_payload(value) -> bool:
    if value is None:
        return False
    try:
        return Decimal(str(value)) != 0
    except Exception:
        s = str(value).strip()
        return bool(s) and s.lower() not in ("nan", "none")


def specific_consumption_has_payload(row) -> bool:
    """Строка «с данными»: хотя бы одно из y/snk/sntp/bk/btp/… не пустое и не 0.

    y=0 при bk≠0 (КЭС) — это данные. Все нули / NULL — пустой год, шаг назад.
    """
    if row is None:
        return False
    return any(
        _numeric_has_payload(getattr(row, attr, None))
        for attr in SPECIFIC_PAYLOAD_ATTRS
    )


def pick_specific_consumption_access_seek(rows, *, byear: int | None, cyear: int):
    """Последняя строка этой станции с byear ≤ year ≤ cyear.

    Как VBA: не шаг назад «пока не найдём данные», не удельник соседней станции.
    Пустой год в окне остаётся выбранным (Access Match).
    """
    window: list = []
    for row in rows:
        y = getattr(row, "year_number", None)
        if y is None:
            continue
        yi = int(y)
        if byear is not None and yi < int(byear):
            continue
        if yi > int(cyear):
            continue
        window.append(row)
    if not window:
        return None
    window.sort(key=lambda r: int(r.year_number))
    return window[-1]


def pick_specific_consumption_year_stepback(rows):
    """rows уже отсортированы по year_number desc. Первая с данными, иначе None."""
    for row in rows:
        if specific_consumption_has_payload(row):
            return row
    return None


def pick_specific_consumption_for_fuel(rows):
    """Топливо: год с данными; иначе последняя строка даже пустая.

    Access U.NoMatch — только когда записей нет совсем. Пустая строка 2026
    (котельная 3607) всё равно Match: y/bk=0, но TUST = Q·TURT/1000 считается.
    Коэфф/Распред тоже Match на пустой строке, если в окне нет года с данными.
    """
    found = pick_specific_consumption_year_stepback(rows)
    if found is not None:
        return found
    return rows[0] if rows else None


def inherit_null_specific_fields(picked, rows):
    """NULL-поля выбранного года заполнить ближайшим более ранним не-NULL.

    Не меняет ORM-строку (иначе flush записал бы чужой snk в 2026).
    Явный 0 остаётся 0.
    """
    if picked is None:
        return None
    payload = {attr: getattr(picked, attr, None) for attr in SPECIFIC_PAYLOAD_ATTRS}
    picked_year = getattr(picked, "year_number", None)
    inherited = False
    for row in rows:
        row_year = getattr(row, "year_number", None)
        if picked_year is not None and row_year is not None and row_year >= picked_year:
            continue
        for attr in SPECIFIC_PAYLOAD_ATTRS:
            if payload[attr] is not None:
                continue
            src = getattr(row, attr, None)
            if src is not None:
                payload[attr] = src
                inherited = True
    if not inherited:
        return picked
    overlay = SimpleNamespace()
    for attr in SPECIFIC_PAYLOAD_ATTRS:
        setattr(overlay, attr, payload[attr])
    overlay.year_number = picked_year
    overlay.equipment_group_id = getattr(picked, "equipment_group_id", None)
    overlay.k = getattr(picked, "k", None)
    overlay.id = getattr(picked, "id", None)
    return overlay


def resolve_specific_consumption_for_fuel(rows):
    return inherit_null_specific_fields(pick_specific_consumption_for_fuel(rows), rows)


def resolve_specific_consumption_year_stepback(rows):
    return inherit_null_specific_fields(
        pick_specific_consumption_year_stepback(rows), rows
    )


def _load_specific_consumption_rows(
    session,
    *,
    equipment_group_id: int,
    target_year: int,
    database_version_id: int | None = None,
):
    q = session.query(EquipmentGroupSpecificFuelConsumption).filter(
        EquipmentGroupSpecificFuelConsumption.equipment_group_id == int(equipment_group_id),
        EquipmentGroupSpecificFuelConsumption.year_number <= int(target_year),
    )
    if database_version_id is not None:
        q = q.filter(
            (EquipmentGroupSpecificFuelConsumption.database_version_id == database_version_id)
            | (EquipmentGroupSpecificFuelConsumption.database_version_id.is_(None))
        )
    return q.order_by(EquipmentGroupSpecificFuelConsumption.year_number.desc()).all()


def _query_specific_consumption_with_picker(
    session,
    picker,
    *,
    equipment_group_id: int,
    target_year: int,
    database_version_id: int | None = None,
) -> EquipmentGroupSpecificFuelConsumption | None:
    rows = _load_specific_consumption_rows(
        session,
        equipment_group_id=equipment_group_id,
        target_year=target_year,
        database_version_id=database_version_id,
    )
    found = inherit_null_specific_fields(picker(rows), rows)
    if found is not None:
        return found
    if database_version_id is None:
        return None
    fallback = _load_specific_consumption_rows(
        session,
        equipment_group_id=equipment_group_id,
        target_year=target_year,
        database_version_id=None,
    )
    return inherit_null_specific_fields(picker(fallback), fallback)


def query_specific_consumption_access_seek(
    session,
    *,
    equipment_group_id: int,
    byear: int | None,
    cyear: int,
    database_version_id: int | None = None,
) -> EquipmentGroupSpecificFuelConsumption | None:
    """Коэфф / Распред / Топливо: U.Seek от byear, последняя year ≤ cyear этой станции."""

    def _rows(vid: int | None):
        q = session.query(EquipmentGroupSpecificFuelConsumption).filter(
            EquipmentGroupSpecificFuelConsumption.equipment_group_id
            == int(equipment_group_id),
            EquipmentGroupSpecificFuelConsumption.year_number <= int(cyear),
        )
        if byear is not None:
            q = q.filter(
                EquipmentGroupSpecificFuelConsumption.year_number >= int(byear)
            )
        if vid is not None:
            q = q.filter(
                (EquipmentGroupSpecificFuelConsumption.database_version_id == vid)
                | (EquipmentGroupSpecificFuelConsumption.database_version_id.is_(None))
            )
        return q.all()

    found = pick_specific_consumption_access_seek(
        _rows(database_version_id), byear=byear, cyear=cyear
    )
    if found is not None or database_version_id is None:
        return found
    return pick_specific_consumption_access_seek(
        _rows(None), byear=byear, cyear=cyear
    )


def query_specific_consumption_year_stepback(
    session,
    *,
    equipment_group_id: int,
    target_year: int,
    database_version_id: int | None = None,
) -> EquipmentGroupSpecificFuelConsumption | None:
    """
    Актуальные удельные: max(year) ≤ target_year, у которого есть y/bk/….
    Пустая строка расчётного года не перекрывает более раннюю с данными.
    NULL в выбранной строке добираем из более ранних лет.
    """
    return _query_specific_consumption_with_picker(
        session,
        pick_specific_consumption_year_stepback,
        equipment_group_id=equipment_group_id,
        target_year=target_year,
        database_version_id=database_version_id,
    )


def query_specific_consumption_for_fuel(
    session,
    *,
    equipment_group_id: int,
    target_year: int,
    database_version_id: int | None = None,
    byear: int | None = None,
) -> EquipmentGroupSpecificFuelConsumption | None:
    """Топливо: тот же Seek, что Коэфф/Распред. byear с параметра распределения."""
    return query_specific_consumption_access_seek(
        session,
        equipment_group_id=equipment_group_id,
        byear=byear,
        cyear=int(target_year),
        database_version_id=database_version_id,
    )


def access_numb2_key_ge(
    numb1120,
    v,
    year,
    *,
    seek_numb: int,
    seek_v: int = 0,
    seek_year: int,
) -> bool:
    """Индекс Access numb2: (numb1120, v, year) >= (seek_numb, seek_v, seek_year)."""
    n = int(numb1120)
    sv = int(v or 0)
    y = int(year)
    if n != int(seek_numb):
        return n > int(seek_numb)
    if sv != int(seek_v):
        return sv > int(seek_v)
    return y >= int(seek_year)


@dataclass
class AccessSeekBookmark:
    """VBA ``bm`` / ``bm1``: последняя удачная строка Seek в цикле станций."""

    row: object | None = None


def apply_access_seek_bookmark(this_row, bookmark: AccessSeekBookmark, *, no_match: bool):
    """Access: ``If U.NoMatch Then GoTo skip`` иначе ``Bookmark = bm``.

    ``this_row`` — последняя year этой станции в ``[byear, cyear]`` (или None).
    ``no_match`` — DAO Seek ``">=", numb, v, byear`` по *всей* таблице: нет ключа ≥.
    Нет строк у себя, но Seek нашёл более позднюю станцию → оставляем bm
    предыдущей станции цикла (как живая Кнопка5/27/49).
    """
    if this_row is not None:
        bookmark.row = this_row
        return this_row
    if no_match:
        return None
    return bookmark.row


def query_access_numb2_seek_no_match(
    session,
    model,
    *,
    numb1120: int | None,
    byear: int | None,
    database_version_id: int | None = None,
    extra_filters=(),
) -> bool:
    """True, если ``Seek ">=", numb1120, 0, byear`` дал NoMatch (нет ключа ≥ в таблице)."""
    if numb1120 is None or byear is None:
        return True
    numb_col = func.coalesce(model.numb1120, EquipmentGroup.numb)
    q = session.query(model.id).join(
        EquipmentGroup, model.equipment_group_id == EquipmentGroup.id
    )
    q = q.filter(
        or_(
            numb_col > int(numb1120),
            and_(numb_col == int(numb1120), model.year_number >= int(byear)),
        )
    )
    for clause in extra_filters:
        q = q.filter(clause)
    if database_version_id is not None:
        q = q.filter(
            (model.database_version_id == database_version_id)
            | (model.database_version_id.is_(None))
        )
    return q.first() is None


def query_ud_seek_no_match(
    session,
    *,
    numb1120: int | None,
    byear: int | None,
    database_version_id: int | None = None,
) -> bool:
    return query_access_numb2_seek_no_match(
        session,
        EquipmentGroupSpecificFuelConsumption,
        numb1120=numb1120,
        byear=byear,
        database_version_id=database_version_id,
    )


def resolve_access_ud_seek(
    session,
    this_row,
    bookmark: AccessSeekBookmark,
    *,
    numb1120: int | None,
    byear: int | None,
    database_version_id: int | None = None,
):
    """Seek этой станции; пустое окно при не-NoMatch → bm предыдущей станции."""
    return apply_access_seek_bookmark(
        this_row,
        bookmark,
        no_match=query_ud_seek_no_match(
            session,
            numb1120=numb1120,
            byear=byear,
            database_version_id=database_version_id,
        ),
    )


def fuel_row_numb1120(row, groups_by_id: dict | None = None) -> int | None:
    """Access ``w("numb1120")`` для Seek."""
    raw = getattr(row, "numb1120", None)
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    gid = getattr(row, "equipment_group_id", None)
    eg = getattr(row, "equipment_group", None)
    if groups_by_id is not None and gid is not None:
        eg = groups_by_id.get(gid) or eg
    numb = getattr(eg, "numb", None) if eg is not None else None
    if numb is None:
        return None
    try:
        return int(numb)
    except (TypeError, ValueError):
        return None

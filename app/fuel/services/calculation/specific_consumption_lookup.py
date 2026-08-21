# -*- coding: utf-8 -*-
"""Отбор удельных как Access U.Seek: последняя запись year ≤ расчётный.

Пустой год (все NULL/0) пропускаем — это ARM-строка, которой в Access нет.
NULL в выбранной строке добираем из более ранних лет (Access без этой строки
взял бы 2025/2024 как есть: 3121 snk=13% не теряется из‑за пустого 2026).
Явный 0 не подменяем (Access z(0)=0).
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

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
    """
    Access Распред/Коэфф: U.Seek \">=\", numb1120, v, byear; затем последняя
    строка того же numb с year ≤ cyear (Bookmark).

    Годы раньше byear в окно не входят (в отличие от шага назад Топлива).
    Пустая ARM-строка поверх года с данными (Липецк 268: пустой 2026, в Access
    строки нет) — Skip как шаг назад по payload, иначе Seek берёт y=0 и
    затирает EWTP. Явный 0 при bk≠0 (КЭС) остаётся строкой таблицы.

    Если в [byear, cyear] есть только пустая строка — это всё равно Match
    (УТЭЦ 1330: y=0, Bk Null → ветка Else koptim). None только когда строк
    в окне нет совсем (тогда цикл подставляет Bookmark предыдущей станции).
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
    with_payload = [row for row in window if specific_consumption_has_payload(row)]
    if with_payload:
        return with_payload[-1]
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
    """Коэфф/Распред: U.Seek от byear, последняя строка year ≤ cyear.

    Пустой ARM-год поверх payload skip; только пустая строка в окне — Match.
    """

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
) -> EquipmentGroupSpecificFuelConsumption | None:
    """Топливо: шаг назад по пустым годам; нет payload — берём пустую строку.

    NULL-поля добираем из более ранних лет. None только если записей
    year ≤ target нет (Access U.NoMatch → skip2).
    """
    return _query_specific_consumption_with_picker(
        session,
        pick_specific_consumption_for_fuel,
        equipment_group_id=equipment_group_id,
        target_year=target_year,
        database_version_id=database_version_id,
    )

# -*- coding: utf-8 -*-
"""Цели Excel-импорта модуля «Топливо» во все версии БД.

Сопоставление группы: numb (NUMB1120) + копии с тем же external_code.
При fill_missing_versions для версий без группы добавляется (None, version_id)
— только у таблиц с nullable equipment_group_id.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import cast
from sqlalchemy.types import String

from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.refdata.services.refdata_all_versions_common import (
    all_database_version_ids_for_refdata,
)


def normalize_import_numb(value) -> str | None:
    """Нормализует numb/NUMB1120 для сравнения с EquipmentGroup.numb."""
    if value is None:
        return None
    if isinstance(value, float):
        try:
            import math

            if math.isnan(value):
                return None
        except TypeError:
            pass
        if value.is_integer():
            return str(int(value))
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Decimal):
        try:
            if value == value.to_integral_value():
                return str(int(value))
        except (InvalidOperation, ValueError, TypeError):
            pass
    s = str(value).strip()
    if not s or s.lower() in ("nan", "none"):
        return None
    if s.isdigit():
        return s
    try:
        f = float(s.replace(",", "."))
        if f.is_integer():
            return str(int(f))
    except (TypeError, ValueError):
        pass
    return s


def resolve_equipment_group_import_targets(
    numb_value,
    *,
    fill_missing_versions: bool = False,
    require_group_match: bool = True,
) -> list[tuple[int | None, int | None]]:
    """
    Список (equipment_group_id, database_version_id) для записи строки Excel
    во все версии БД.

    :param fill_missing_versions: добавить (None, version_id) для версий без ГО
    :param require_group_match: если ГО нет ни в одной версии — вернуть []
        (False = как «Тепло и тарифы»: писать во все версии даже без ГО)
    """
    numb_str = normalize_import_numb(numb_value)
    if not numb_str:
        return []

    groups = list(
        EquipmentGroup.query.filter(cast(EquipmentGroup.numb, String) == numb_str).all()
    )
    codes = {
        (getattr(group, "external_code", None) or "").strip()
        for group in groups
        if (getattr(group, "external_code", None) or "").strip()
    }
    if codes:
        siblings = EquipmentGroup.query.filter(
            EquipmentGroup.external_code.in_(sorted(codes))
        ).all()
        by_id = {group.id: group for group in groups if getattr(group, "id", None)}
        for sibling in siblings:
            if getattr(sibling, "id", None):
                by_id[sibling.id] = sibling
        groups = list(by_id.values())

    targets: list[tuple[int | None, int | None]] = [
        (group.id, getattr(group, "database_version_id", None))
        for group in groups
        if getattr(group, "id", None) is not None
    ]
    if require_group_match and not targets:
        return []

    if fill_missing_versions:
        covered = {
            version_id for _, version_id in targets if version_id is not None
        }
        for version_id in all_database_version_ids_for_refdata():
            if version_id not in covered:
                targets.append((None, version_id))
    return targets


def lookup_imported_row(
    model,
    *,
    equipment_group_id,
    year_number,
    database_version_id,
    extra_eq: dict | None = None,
):
    """
    Находит уже загруженную строку.

    При наличии ГО — по (equipment_group_id, year) [+ extra], без фильтра версии
    (уникальный ключ обычно без database_version_id).
    Без ГО — по (equipment_group_id IS NULL, year, database_version_id) [+ extra].
    """
    extra_eq = extra_eq or {}
    query = model.query.filter_by(year_number=year_number, **extra_eq)
    if equipment_group_id is not None:
        return query.filter_by(equipment_group_id=equipment_group_id).first()
    query = query.filter(model.equipment_group_id.is_(None))
    if database_version_id is not None:
        query = query.filter_by(database_version_id=database_version_id)
    else:
        query = query.filter(model.database_version_id.is_(None))
    return query.first()

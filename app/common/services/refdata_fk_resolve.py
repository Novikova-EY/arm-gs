# -*- coding: utf-8 -*-
"""
Приведение id справочников «Субъект РФ» / «РЭС» к версии БД сущности (EquipmentGroup и др.).

Числовые id в refdata версионируются: один и тот же субъект в другой версии имеет другой id.
"""
from __future__ import annotations

from app.common.services.database_version_filter import filter_by_explicit_db_version
from app.refdata.models.energy_systems.regional_energy_system_model import (
    RegionalEnergySystem,
)
from app.refdata.models.territories.regional_district_model import RegionalDistrict


def coerce_regional_district_id_for_db_version(rd_id: int | None, version_id) -> int | None:
    """Тихое приведение: несуществующий или «чужой» id → id в нужной версии или None."""
    if rd_id is None:
        return None
    rd = RegionalDistrict.query.get(rd_id)
    if not rd:
        return None
    if getattr(rd, "database_version_id", None) == version_id:
        return rd_id
    ref = getattr(rd, "ref_uuid", None)
    if not ref:
        return None
    match = (
        filter_by_explicit_db_version(
            RegionalDistrict.query,
            RegionalDistrict,
            version_id,
        )
        .filter(RegionalDistrict.ref_uuid == ref)
        .first()
    )
    return match.id if match else None


def coerce_regional_energy_system_id_for_db_version(res_id: int | None, version_id) -> int | None:
    """Тихое приведение id РЭС к версии БД."""
    if res_id is None:
        return None
    res = RegionalEnergySystem.query.get(res_id)
    if not res:
        return None
    if getattr(res, "database_version_id", None) == version_id:
        return res_id
    ref = getattr(res, "ref_uuid", None)
    if not ref:
        return None
    match = (
        filter_by_explicit_db_version(
            RegionalEnergySystem.query,
            RegionalEnergySystem,
            version_id,
        )
        .filter(RegionalEnergySystem.ref_uuid == ref)
        .first()
    )
    return match.id if match else None


def resolve_regional_district_id_for_db_version(rd_id: int | None, version_id):
    """
    Для сохранения из формы: (id для версии или None, текст ошибки или None).
    """
    if rd_id is None:
        return None, None
    coerced = coerce_regional_district_id_for_db_version(rd_id, version_id)
    if coerced is not None:
        return coerced, None
    rd = RegionalDistrict.query.get(rd_id)
    if not rd:
        return None, (
            f"Субъект РФ (id={rd_id}) отсутствует в справочнике. "
            "Выберите значение из списка заново."
        )
    ref = getattr(rd, "ref_uuid", None)
    if not ref:
        return None, (
            "Выбранный субъект РФ относится к другой версии справочника; "
            "для сопоставления с версией этой группы нет ref_uuid. "
            "Выберите субъект из выпадающего списка ещё раз."
        )
    return None, (
        f"Субъект РФ «{rd.name}» недоступен в версии БД этой группы оборудования."
    )


def resolve_regional_energy_system_id_for_db_version(res_id: int | None, version_id):
    """Для сохранения из формы: (id для версии или None, текст ошибки или None)."""
    if res_id is None:
        return None, None
    coerced = coerce_regional_energy_system_id_for_db_version(res_id, version_id)
    if coerced is not None:
        return coerced, None
    res = RegionalEnergySystem.query.get(res_id)
    if not res:
        return None, (
            f"Региональная энергосистема (id={res_id}) отсутствует в справочнике. "
            "Выберите значение из списка заново."
        )
    ref = getattr(res, "ref_uuid", None)
    if not ref:
        return None, (
            "Выбранная РЭС относится к другой версии справочника; "
            "для сопоставления с версией этой группы нет ref_uuid. "
            "Выберите РЭС из выпадающего списка ещё раз."
        )
    return None, (
        f"РЭС «{res.name}» недоступна в версии БД этой группы оборудования."
    )

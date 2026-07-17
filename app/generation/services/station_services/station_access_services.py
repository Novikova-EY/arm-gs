# -*- coding: utf-8 -*-
"""Права доступа к операциям со станциями (децентрализованная зона / модуль «Топливо»)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func

from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType

if TYPE_CHECKING:
    from app.generation.models.station.station_model import Station

FUEL_DECENTRALIZED_CREATOR_ROLE_FULL_NAMES = frozenset(
    {"Топливо-админ", "Топливо-редактор"}
)
DECENTRALIZED_ZONE_MACHINE_EDIT_ROLES = frozenset(
    {
        "admin",
        "fuel-admin",
        "fuel-editor",
        "generation-admin",
        "generation-editor",
    }
)
DECENTRALIZED_ZONE_ENERGY_SYSTEM_TYPE_NAME = "Децентрализованная зона"
UNSPECIFIED_REF_LABEL = "не указано"
# Синтетические ключи иерархии для station_list (не пересекаются с реальными id справочников)
DECENTRALIZED_ZONE_SYNTHETIC_UES_ID = -1
DECENTRALIZED_ZONE_SYNTHETIC_RES_ID = -1


def is_fuel_decentralized_station_creator(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return any(
        (role.name_full or "") in FUEL_DECENTRALIZED_CREATOR_ROLE_FULL_NAMES
        for role in getattr(user, "roles", []) or []
    )


def _normalize_ref_label(value: str | None) -> str:
    return (value or "").strip().lower()


def find_choice_id_by_label(choices, label: str = UNSPECIFIED_REF_LABEL):
    normalized = _normalize_ref_label(label)
    for choice in choices:
        try:
            choice_id, choice_label = choice[0], choice[1]
        except (TypeError, IndexError):
            continue
        if isinstance(choice_label, str) and _normalize_ref_label(choice_label) == normalized:
            return choice_id
    return None


def get_decentralized_zone_energy_system_type_name(database_version_id: int | None = None) -> str:
    from app.common.services.database_version_filter import get_current_db_version_id

    version_id = database_version_id
    if version_id is None:
        version_id = get_current_db_version_id()

    query = EnergySystemType.query.filter(
        func.lower(func.trim(EnergySystemType.name))
        == _normalize_ref_label(DECENTRALIZED_ZONE_ENERGY_SYSTEM_TYPE_NAME)
    )
    if version_id is None:
        query = query.filter(EnergySystemType.database_version_id.is_(None))
    else:
        query = query.filter(EnergySystemType.database_version_id == version_id)

    row = query.first()
    return row.name if row and row.name else DECENTRALIZED_ZONE_ENERGY_SYSTEM_TYPE_NAME


def get_decentralized_zone_energy_system_type_id(database_version_id: int | None = None) -> int | None:
    from app.common.services.database_version_filter import get_current_db_version_id

    version_id = database_version_id
    if version_id is None:
        version_id = get_current_db_version_id()

    query = EnergySystemType.query.filter(
        func.lower(func.trim(EnergySystemType.name))
        == _normalize_ref_label(DECENTRALIZED_ZONE_ENERGY_SYSTEM_TYPE_NAME)
    )
    if version_id is None:
        query = query.filter(EnergySystemType.database_version_id.is_(None))
    else:
        query = query.filter(EnergySystemType.database_version_id == version_id)

    row = query.first()
    return row.id if row else None


def get_decentralized_zone_res_ids(database_version_id: int | None = None) -> frozenset[int]:
    """Id РЭС «не указано» (без запятой в названии) — признак децентрализованной зоны."""
    from app.common.services.database_version_filter import get_current_db_version_id
    from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem

    version_id = database_version_id
    if version_id is None:
        version_id = get_current_db_version_id()

    query = RegionalEnergySystem.query
    if version_id is None:
        query = query.filter(RegionalEnergySystem.database_version_id.is_(None))
    else:
        query = query.filter(RegionalEnergySystem.database_version_id == version_id)

    result = set()
    for res in query.all():
        name = (res.name or "").strip()
        if "," in name:
            continue
        if _normalize_ref_label(name) == UNSPECIFIED_REF_LABEL:
            result.add(res.id)
    return frozenset(result)


def is_decentralized_zone_res_id(res_id: int | None) -> bool:
    if res_id is None:
        return False
    return res_id in get_decentralized_zone_res_ids()


def get_station_list_group_info(station: "Station") -> dict:
    """Метаданные группировки станции для station_list (сортировка, пагинация, итоги)."""
    from app.extensions import db
    from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem

    is_dz = is_decentralized_zone_station(station)
    info = {
        "is_decentralized_zone": is_dz,
        "sort_tier": 1 if is_dz else 0,
        "energy_system_type_id": None,
        "union_energy_system_id": None,
        "regional_energy_system_id": None,
        "regional_district_id": station.id_regional_district,
        "energy_unit_id": station.id_energy_unit,
    }
    if is_dz:
        info["energy_system_type_id"] = get_decentralized_zone_energy_system_type_id()
        info["regional_energy_system_id"] = station.id_regional_energy_system
        return info

    res = None
    if getattr(station, "id_regional_energy_system", None):
        res = getattr(station, "regional_energy_system_obj", None)
        if res is None:
            res = db.session.get(RegionalEnergySystem, station.id_regional_energy_system)
    elif station.regional_district and station.regional_district.regional_energy_systems:
        res = station.regional_district.regional_energy_systems[0]

    if res:
        info["regional_energy_system_id"] = res.id
        ues = getattr(res, "union_energy_system", None)
        if ues:
            info["union_energy_system_id"] = ues.id
            est = getattr(ues, "energy_system_type", None)
            if est:
                info["energy_system_type_id"] = est.id
    return info


def get_station_regional_energy_system_display_name(station: "Station") -> str | None:
    res_obj = getattr(station, "regional_energy_system_obj", None)
    if res_obj and getattr(res_obj, "name", None):
        return res_obj.name
    return getattr(station, "regional_energy_system", None)


def station_has_unspecified_regional_energy_system(station: "Station") -> bool:
    name = get_station_regional_energy_system_display_name(station)
    if not name:
        return False
    if "," in name:
        return False
    return _normalize_ref_label(name) == UNSPECIFIED_REF_LABEL


def is_decentralized_zone_station(station: "Station") -> bool:
    return station_has_unspecified_regional_energy_system(station)


def can_fuel_user_add_machine_to_station(user, station: "Station") -> bool:
    return (
        is_fuel_decentralized_station_creator(user)
        and station_has_unspecified_regional_energy_system(station)
    )


def can_fuel_user_edit_decentralized_station_details(user, station: "Station") -> bool:
    """Редактирование карточки станции ДЭЗ и выработки — только Топливо-админ/редактор."""
    return (
        is_fuel_decentralized_station_creator(user)
        and is_decentralized_zone_station(station)
    )


def can_edit_decentralized_zone_machine_details(user, station: "Station") -> bool:
    """Редактирование карточки агрегата на станции ДЭЗ — топливо/генерация admin+editor."""
    if not getattr(user, "is_authenticated", False):
        return False
    if not is_decentralized_zone_station(station):
        return False
    role_names = set(getattr(user, "role_names", []) or [])
    if role_names & DECENTRALIZED_ZONE_MACHINE_EDIT_ROLES:
        return True
    return is_fuel_decentralized_station_creator(user)

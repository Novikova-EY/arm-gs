# -*- coding: utf-8 -*-
"""
Сервис для обеспечения наличия EquipmentGroupSetStation и EquipmentGroupSet
при выборе типа группы оборудования на агрегате.
Логика аналогична загрузке из Excel (stations_equipment_groups).
"""

from __future__ import annotations

import uuid

from app.extensions import db
from app.common.services.database_version_filter import (
    get_current_db_version_id,
    set_db_version_on_create,
)
from app.generation.models.station.station_model import Station
from app.generation.models.machine.machine_model import Machine
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
    EquipmentGroupType,
)
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam


NEW_EQUIPMENT_GROUP_SUFFIX = " (нов)"
EQUIPMENT_GROUP_CONTEXT_COPY_FIELDS = (
    "name_ext",
    "niv",
    "comp",
    "main",
    "d",
    "r",
    "forem",
    "vedomstvo",
    "obl",
    "regional_district_id",
    "regional_energy_system_id",
    "dep",
    "id_department",
    "oes",
    "er",
    "fo",
    "numb",
    "tm",
    "n1",
    "n2",
    "p1",
    "p2",
    "ordnumb",
    "addr",
    "note",
    "codegor",
    "be",
    "gk",
    "gkf",
)


def _generate_stable_external_code_equipment_group(
    station_external_code: str | None,
    type_ref_uuid: str | None,
    numb: int | str | None,
    group_variant: str | None = None,
) -> str:
    key = (
        f"import|equipment_group|station|{station_external_code or ''}"
        f"|type|{type_ref_uuid or ''}|numb|{numb or ''}"
        f"|variant|{group_variant or 'base'}"
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def _find_equipment_group_by_external_code(
    external_code: str | None,
    version_id: int | None,
) -> EquipmentGroup | None:
    if not external_code:
        return None

    query = EquipmentGroup.query.filter(EquipmentGroup.external_code == external_code)
    if version_id is None:
        query = query.filter(EquipmentGroup.database_version_id.is_(None))
    else:
        query = query.filter(EquipmentGroup.database_version_id == version_id)
    return query.order_by(EquipmentGroup.id.asc()).first()


def _year_has_plan_feature(year_number: int | None, version_id: int | None) -> bool:
    if year_number is None:
        return False
    from app.common.services.get_services.years.year_feature_services import (
        get_year_feature_dict_for_version,
    )

    year_features = get_year_feature_dict_for_version(version_id)
    return str(year_features.get(year_number) or "").strip().lower() == "план"


def _machine_requires_new_equipment_group(machine: Machine | None, version_id: int | None) -> bool:
    if machine is None:
        return False
    year_number = getattr(machine, "date_exploitation_expected", None)
    if year_number is None:
        return False
    try:
        year_number = int(year_number)
    except (TypeError, ValueError):
        return False
    return _year_has_plan_feature(year_number, version_id)


def _compose_equipment_group_name(
    station: Station | None,
    group_type: EquipmentGroupType | None,
    *,
    is_new_group: bool,
) -> str | None:
    if not station or not station.name or not group_type or not group_type.name:
        return None
    base_name = f"{station.name} ({group_type.name})"
    return f"{base_name}{NEW_EQUIPMENT_GROUP_SUFFIX}" if is_new_group else base_name


def _is_new_equipment_group_name(name: str | None) -> bool:
    return bool(name and str(name).strip().endswith(NEW_EQUIPMENT_GROUP_SUFFIX))


def _get_linked_equipment_groups(link_id: int) -> list[EquipmentGroup]:
    rows = (
        EquipmentGroupSet.query
        .join(EquipmentGroup, EquipmentGroup.id == EquipmentGroupSet.equipment_group_id)
        .filter(EquipmentGroupSet.equipment_group_set_station_id == link_id)
        .order_by(EquipmentGroup.id.asc())
        .all()
    )
    return [row.equipment_group for row in rows if getattr(row, "equipment_group", None) is not None]


def _sync_equipment_group_context_from_source(
    target: EquipmentGroup,
    source: EquipmentGroup | None,
    station: Station | None,
) -> bool:
    """
    Новая variant-группа, созданная из карточки агрегата, должна наследовать
    территориальные и идентификационные поля от базовой группы, иначе она
    не проходит фильтры страницы fuel/stations_equipment_groups.
    """
    changed = False

    if source is not None:
        for field_name in EQUIPMENT_GROUP_CONTEXT_COPY_FIELDS:
            source_value = getattr(source, field_name, None)
            if getattr(target, field_name, None) != source_value:
                setattr(target, field_name, source_value)
                changed = True

    if station is not None:
        if getattr(target, "regional_district_id", None) != getattr(station, "id_regional_district", None):
            target.regional_district_id = getattr(station, "id_regional_district", None)
            changed = True
        if getattr(target, "regional_energy_system_id", None) != getattr(station, "id_regional_energy_system", None):
            target.regional_energy_system_id = getattr(station, "id_regional_energy_system", None)
            changed = True

    old_rd = getattr(target, "regional_district_id", None)
    old_res = getattr(target, "regional_energy_system_id", None)
    target._populate_regional_ids()
    if (
        getattr(target, "regional_district_id", None),
        getattr(target, "regional_energy_system_id", None),
    ) != (old_rd, old_res):
        changed = True

    if changed:
        db.session.add(target)
    return changed


def ensure_equipment_group_set_for_station(
    station_id: int,
    equipment_group_type_id: int,
    version_id: int | None = None,
) -> EquipmentGroupSet | None:
    """
    Проверяет наличие EquipmentGroupSetStation для (station_id, equipment_group_type_id).
    Если нет — создает EquipmentGroupSetStation, затем EquipmentGroup и EquipmentGroupSet.
    Логика аналогична import_fuel_db_equipment_groups (шаг 4.1).

    Args:
        station_id: ID электростанции
        equipment_group_type_id: ID типа группы оборудования (EquipmentGroupType)
        version_id: ID версии БД (если None — использует текущую)

    Returns:
        EquipmentGroupSet или None при ошибке
    """
    return ensure_equipment_group_set_variant_for_station(
        station_id=station_id,
        equipment_group_type_id=equipment_group_type_id,
        version_id=version_id,
        is_new_group=False,
    )


def ensure_equipment_group_set_variant_for_station(
    station_id: int,
    equipment_group_type_id: int,
    version_id: int | None = None,
    *,
    is_new_group: bool = False,
) -> EquipmentGroupSet | None:
    """
    Обеспечивает наличие связки EquipmentGroupSetStation и конкретной fuel-группы
    для варианта обычного или «(нов)» оборудования.
    """
    if version_id is None:
        version_id = get_current_db_version_id()

    current_version = get_current_db_version_id()

    station = Station.query.get(station_id)
    if not station:
        return None
    group_type = EquipmentGroupType.query.get(equipment_group_type_id)
    if not group_type:
        return None

    link_query = EquipmentGroupSetStation.query.filter(
        EquipmentGroupSetStation.station_id == station_id,
        EquipmentGroupSetStation.equipment_group_type_id == equipment_group_type_id,
    )
    if version_id is None:
        link_query = link_query.filter(EquipmentGroupSetStation.database_version_id.is_(None))
    else:
        link_query = link_query.filter(EquipmentGroupSetStation.database_version_id == version_id)
    link = link_query.first()

    if not link:
        link = EquipmentGroupSetStation(
            station_id=station_id,
            equipment_group_type_id=equipment_group_type_id,
        )
        if version_id is not None:
            link.database_version_id = version_id
        elif current_version is not None:
            set_db_version_on_create(link)
        db.session.add(link)
        db.session.flush()

    station_ext_code = (station.external_code or "").strip()
    type_key = getattr(group_type, "ref_uuid", None) or group_type.name or str(equipment_group_type_id)
    target_external_code = _generate_stable_external_code_equipment_group(
        station_ext_code,
        type_key,
        None,
        group_variant="new" if is_new_group else None,
    )
    linked_equipment_groups = _get_linked_equipment_groups(link.id)
    base_group_on_link = next(
        (group for group in linked_equipment_groups if not _is_new_equipment_group_name(getattr(group, "name", None))),
        None,
    )
    target_group_on_link = next(
        (
            group
            for group in linked_equipment_groups
            if _is_new_equipment_group_name(getattr(group, "name", None)) == is_new_group
        ),
        None,
    )

    if target_group_on_link is not None:
        _sync_equipment_group_context_from_source(
            target_group_on_link,
            base_group_on_link if base_group_on_link and base_group_on_link.id != target_group_on_link.id else None,
            station,
        )
        set_v2 = (
            EquipmentGroupSet.query
            .filter_by(
                equipment_group_id=target_group_on_link.id,
                equipment_group_set_station_id=link.id,
            )
            .first()
        )
        if set_v2:
            return set_v2

    equipment_group = _find_equipment_group_by_external_code(
        target_external_code,
        version_id,
    )
    if equipment_group is None:
        equipment_group = EquipmentGroup(
            name=_compose_equipment_group_name(
                station,
                group_type,
                is_new_group=is_new_group,
            )
        )
        equipment_group.external_code = target_external_code
        if version_id is not None:
            equipment_group.database_version_id = version_id
        elif current_version is not None:
            set_db_version_on_create(equipment_group)
        db.session.add(equipment_group)
        db.session.flush()
    _sync_equipment_group_context_from_source(
        equipment_group,
        base_group_on_link if base_group_on_link and base_group_on_link.id != equipment_group.id else None,
        station,
    )

    set_v2 = EquipmentGroupSet(
        equipment_group_id=equipment_group.id,
        equipment_group_set_station_id=link.id,
    )
    db.session.add(set_v2)
    db.session.flush()
    return set_v2


def get_station_fuel_equipment_group_choice_tuples(
    station_id: int,
    version_id: int | None = None,
) -> list[tuple[int, str]]:
    """
    Список (id, название) итоговых групп оборудования (gs_fue_equipment_groups),
    привязанных к электростанции через v2-связки для указанной версии БД.
    """
    if version_id is None:
        version_id = get_current_db_version_id()

    link_q = EquipmentGroupSetStation.query.filter(
        EquipmentGroupSetStation.station_id == station_id,
    )
    if version_id is None:
        link_q = link_q.filter(EquipmentGroupSetStation.database_version_id.is_(None))
    else:
        link_q = link_q.filter(EquipmentGroupSetStation.database_version_id == version_id)

    link_ids = [row.id for row in link_q.with_entities(EquipmentGroupSetStation.id).all()]
    if not link_ids:
        return []

    rows = (
        db.session.query(EquipmentGroup.id, EquipmentGroup.name)
        .join(
            EquipmentGroupSet,
            EquipmentGroupSet.equipment_group_id == EquipmentGroup.id,
        )
        .filter(EquipmentGroupSet.equipment_group_set_station_id.in_(link_ids))
        .distinct()
        .order_by(EquipmentGroup.name.asc())
        .all()
    )
    return [
        (r.id, ((r.name or "").strip() or f"Группа #{r.id}"))
        for r in rows
    ]


def sync_machine_fuel_equipment_group(machine: Machine | None, version_id: int | None = None) -> EquipmentGroup | None:
    """
    Синхронизирует конкретную fuel-группу агрегата с его текущим типом группы оборудования.
    Если тип снят, очищает MachineFuelParam.equipment_group_id.
    """
    if machine is None:
        return None
    if version_id is None:
        version_id = getattr(machine, "database_version_id", None) or get_current_db_version_id()

    machine_fuel_param = getattr(machine, "machine_fuel_param", None)
    if not machine.id_station or not machine.id_equipment_group:
        if machine_fuel_param is not None and machine_fuel_param.equipment_group_id is not None:
            machine_fuel_param.equipment_group_id = None
            db.session.add(machine_fuel_param)
        return None

    is_new_group = _machine_requires_new_equipment_group(machine, version_id)
    set_v2 = ensure_equipment_group_set_variant_for_station(
        station_id=machine.id_station,
        equipment_group_type_id=machine.id_equipment_group,
        version_id=version_id,
        is_new_group=is_new_group,
    )
    if set_v2 is None:
        return None

    if machine_fuel_param is None:
        machine_fuel_param = MachineFuelParam(machine_id=machine.id)
        if version_id is not None:
            machine_fuel_param.database_version_id = version_id
        db.session.add(machine_fuel_param)
        db.session.flush()

    if machine_fuel_param.equipment_group_id != set_v2.equipment_group_id:
        machine_fuel_param.equipment_group_id = set_v2.equipment_group_id
        db.session.add(machine_fuel_param)

    return set_v2.equipment_group

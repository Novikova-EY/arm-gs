# -*- coding: utf-8 -*-
"""
Сервис для обеспечения наличия EquipmentGroupSetStation и EquipmentGroupSet
при выборе типа группы оборудования на агрегате.
Логика аналогична загрузке из Excel (stations_equipment_groups).
"""

from __future__ import annotations

from app.extensions import db
from app.common.services.database_version_filter import (
    get_current_db_version_id,
    set_db_version_on_create,
)
from app.generation.models.station.station_model import Station
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
    EquipmentGroupType,
)
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_model import EquipmentGroup


def ensure_equipment_group_set_for_station(
    station_id: int,
    equipment_group_type_id: int,
    version_id: int | None = None,
) -> EquipmentGroupSet | None:
    """
    Проверяет наличие EquipmentGroupSetStation для (station_id, equipment_group_type_id).
    Если нет — создаёт EquipmentGroupSetStation, затем EquipmentGroup и EquipmentGroupSet.
    Логика аналогична import_fuel_db_equipment_groups (шаг 4.1).

    Args:
        station_id: ID станции
        equipment_group_type_id: ID типа группы оборудования (EquipmentGroupType)
        version_id: ID версии БД (если None — использует текущую)

    Returns:
        EquipmentGroupSet или None при ошибке
    """
    if version_id is None:
        version_id = get_current_db_version_id()

    current_version = get_current_db_version_id()

    # Проверяем, что станция и тип существуют
    station = Station.query.get(station_id)
    if not station:
        return None
    group_type = EquipmentGroupType.query.get(equipment_group_type_id)
    if not group_type:
        return None

    # Ищем или создаём EquipmentGroupSetStation
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

    # Ищем EquipmentGroupSet для этой связи
    set_v2 = EquipmentGroupSet.query.filter_by(
        equipment_group_set_station_id=link.id
    ).first()

    if not set_v2:
        group_name = None
        if station.name and group_type.name:
            group_name = f"{station.name} ({group_type.name})"
        equipment_group = EquipmentGroup(name=group_name)
        if version_id is not None:
            equipment_group.database_version_id = version_id
        elif current_version is not None:
            set_db_version_on_create(equipment_group)
        db.session.add(equipment_group)
        db.session.flush()

        set_v2 = EquipmentGroupSet(
            equipment_group_id=equipment_group.id,
            equipment_group_set_station_id=link.id,
        )
        db.session.add(set_v2)
        db.session.flush()

    return set_v2

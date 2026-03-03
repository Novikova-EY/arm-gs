# -*- coding: utf-8 -*-
"""Сервис для страницы «Топливные параметры групп оборудования (дополнительные)»."""
from collections import defaultdict

from sqlalchemy.orm import selectinload

from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation


def load_equipment_group_extra_fuel_params_for_stations(stations):
    """
    Загружает equipment_group_set_links с extra_fuel_params (на equipment_group_set)
    для списка станций.
    """
    if not stations:
        return
    station_ids = [s.id for s in stations]
    links = (
        EquipmentGroupSetStation.query.filter(
            EquipmentGroupSetStation.station_id.in_(station_ids)
        )
        .options(
            selectinload(EquipmentGroupSetStation.equipment_group_set).selectinload(
                EquipmentGroupSet.extra_fuel_params
            ),
            selectinload(EquipmentGroupSetStation.equipment_group_set).joinedload(
                EquipmentGroupSet.equipment_group
            ),
        )
        .all()
    )
    links_by_station = defaultdict(list)
    for link in links:
        links_by_station[link.station_id].append(link)
    for station in stations:
        station.equipment_group_set_links = links_by_station.get(station.id, [])

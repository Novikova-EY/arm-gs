# -*- coding: utf-8 -*-
"""Сервис для страницы «Топливные параметры групп оборудования» — загрузка fuel_params."""
from collections import defaultdict

from sqlalchemy.orm import selectinload

from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.external_mapping.fue_em_business_unit_model import (
    BusinessUnitExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_equipment_group_model import (
    EquipmentGroupExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_department_model import (
    DepartmentExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_economic_region_model import (
    EconomicRegionExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_gen_company_model import (
    GenCompanyExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_territories_energy_model import (
    TerritoriesEnergyExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_union_energy_system_model import (
    UnionEnergySystemExternalMapping,
)


def build_obor_name_map(stations):
    """
    Собирает все obor из fuel_params станций и возвращает словарь obor -> gruppa_oborud
    для отображения EquipmentGroupExternalMapping.gruppa_oborud вместо кода obor.
    """
    obor_ids = set()
    for station in stations or []:
        for link in getattr(station, "equipment_group_set_links", []) or []:
            for param in getattr(link, "fuel_params", []) or []:
                if param.obor is not None:
                    obor_ids.add(param.obor)
    if not obor_ids:
        return {}
    mappings = EquipmentGroupExternalMapping.query.filter(
        EquipmentGroupExternalMapping.code.in_(obor_ids)
    ).all()
    return {
        m.code: (m.gruppa_oborud or str(m.code))
        for m in mappings
        if m.code is not None
    }


def build_obl_name_map(stations):
    """
    Собирает все obl из fuel_params станций и возвращает словарь obl -> external_name
    для отображения TerritoriesEnergyExternalMapping.external_name вместо кода obl.
    """
    obl_ids = set()
    for station in stations or []:
        for link in getattr(station, "equipment_group_set_links", []) or []:
            for param in getattr(link, "fuel_params", []) or []:
                if param.obl is not None:
                    obl_ids.add(param.obl)
    if not obl_ids:
        return {}
    obl_strs = [str(o) for o in obl_ids]
    mappings = TerritoriesEnergyExternalMapping.query.filter(
        TerritoriesEnergyExternalMapping.external_id.in_(obl_strs)
    ).all()
    return {
        m.external_id: (m.external_name or m.external_id)
        for m in mappings
        if m.external_id
    }


def build_dep_name_map(stations):
    """
    Собирает все dep из fuel_params станций и возвращает словарь dep -> external_name
    для отображения DepartmentExternalMapping.external_name вместо кода dep.
    """
    dep_ids = set()
    for station in stations or []:
        for link in getattr(station, "equipment_group_set_links", []) or []:
            for param in getattr(link, "fuel_params", []) or []:
                if param.dep is not None:
                    dep_ids.add(param.dep)
    if not dep_ids:
        return {}
    dep_strs = [str(d) for d in dep_ids]
    mappings = DepartmentExternalMapping.query.filter(
        DepartmentExternalMapping.external_id.in_(dep_strs)
    ).all()
    return {
        m.external_id: (m.external_name or m.external_id)
        for m in mappings
        if m.external_id
    }


def build_oes_name_map(stations):
    """
    Собирает все oes из fuel_params станций и возвращает словарь oes -> external_nameoes (или external_name)
    для отображения UnionEnergySystemExternalMapping.external_nameoes вместо кода oes.
    """
    oes_ids = set()
    for station in stations or []:
        for link in getattr(station, "equipment_group_set_links", []) or []:
            for param in getattr(link, "fuel_params", []) or []:
                if param.oes is not None:
                    oes_ids.add(param.oes)
    if not oes_ids:
        return {}
    oes_strs = [str(o) for o in oes_ids]
    mappings = UnionEnergySystemExternalMapping.query.filter(
        UnionEnergySystemExternalMapping.external_id.in_(oes_strs)
    ).all()
    return {
        m.external_id: (m.external_nameoes or m.external_name or m.external_id)
        for m in mappings
        if m.external_id
    }


def build_er_name_map(stations):
    """
    Собирает все er из fuel_params станций и возвращает словарь er -> external_name
    для отображения EconomicRegionExternalMapping.external_name вместо кода er.
    """
    er_ids = set()
    for station in stations or []:
        for link in getattr(station, "equipment_group_set_links", []) or []:
            for param in getattr(link, "fuel_params", []) or []:
                if param.er is not None:
                    er_ids.add(param.er)
    if not er_ids:
        return {}
    er_strs = [str(e) for e in er_ids]
    mappings = EconomicRegionExternalMapping.query.filter(
        EconomicRegionExternalMapping.external_id.in_(er_strs)
    ).all()
    return {
        m.external_id: (m.external_name or m.external_id)
        for m in mappings
        if m.external_id
    }


def build_gk_name_map(stations):
    """
    Собирает все gk из fuel_params станций и возвращает словарь gk -> external_name
    для отображения GenCompanyExternalMapping.external_name вместо кода gk.
    """
    gk_ids = set()
    for station in stations or []:
        for link in getattr(station, "equipment_group_set_links", []) or []:
            for param in getattr(link, "fuel_params", []) or []:
                if param.gk is not None:
                    gk_ids.add(param.gk)
    if not gk_ids:
        return {}
    gk_strs = [str(g) for g in gk_ids]
    mappings = GenCompanyExternalMapping.query.filter(
        GenCompanyExternalMapping.external_id.in_(gk_strs)
    ).all()
    return {
        m.external_id: (m.external_name or m.external_id)
        for m in mappings
        if m.external_id
    }


def build_be_name_map(stations):
    """
    Собирает все be из fuel_params станций и возвращает словарь be -> external_name
    для отображения BusinessUnitExternalMapping.external_name вместо кода be.
    """
    be_ids = set()
    for station in stations or []:
        for link in getattr(station, "equipment_group_set_links", []) or []:
            for param in getattr(link, "fuel_params", []) or []:
                if param.be is not None:
                    be_ids.add(param.be)
    if not be_ids:
        return {}
    be_strs = [str(b) for b in be_ids]
    mappings = BusinessUnitExternalMapping.query.filter(
        BusinessUnitExternalMapping.external_id.in_(be_strs)
    ).all()
    return {
        m.external_id: (m.external_name or m.external_id)
        for m in mappings
        if m.external_id
    }


def load_equipment_group_fuel_params_for_stations(stations):
    """
    Загружает equipment_group_set_links с fuel_params для списка станций.
    Заполняет station.equipment_group_set_links предзагруженными данными,
    чтобы избежать N+1 при доступе в шаблоне.
    """
    if not stations:
        return
    station_ids = [s.id for s in stations]
    links = (
        EquipmentGroupSetStation.query.filter(
            EquipmentGroupSetStation.station_id.in_(station_ids)
        )
        .options(
            selectinload(EquipmentGroupSetStation.fuel_params),
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

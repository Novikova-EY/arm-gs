# -*- coding: utf-8 -*-
"""Сборка JSON-набора equipment_group_params (группа оборудования × год)."""
from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy.orm import joinedload

from app.extensions import db
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)
from app.generation.models.station.station_model import Station
from app.api.services.generation_objects_exchange_services import (
    clip_years,
    dataset_envelope,
    json_number,
    load_exchange_years,
    resolve_database_version,
    _version_filter,
)
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
    EquipmentGroupType,
)

DATASET_EQUIPMENT_GROUP_PARAMS = "equipment_group_params"

KEY_GROUP_CODE = "external_code"
KEY_STATION_CODE = "station_external_code"
KEY_GROUP_NAME = "Название группы оборудования"
KEY_GROUP_TYPE = "Тип группы оборудования"
KEY_TECHNOLOGY_TYPE = "Тип технологии"
KEY_TECHNOLOGY_AVAILABILITY = "Доступность технологии"
KEY_GROUP_NUMB = "Код группы оборудования"
KEY_YEAR = "Год"

PARAM_FIELDS: tuple[tuple[str, str], ...] = (
    ("nust", EquipmentGroupFuelParam.NUST_COLUMN_LABEL),
    ("nr", EquipmentGroupFuelParam.NR_COLUMN_LABEL),
    ("h", EquipmentGroupFuelParam.H_COLUMN_LABEL),
    ("hfix", EquipmentGroupFuelParam.HFIX_COLUMN_LABEL),
    ("e", EquipmentGroupFuelParam.E_COLUMN_LABEL),
    ("ewtp", "Теплофикационная выработка ЭЭ, тыс.кВтч"),
    ("eotp", EquipmentGroupFuelParam.EOTP_COLUMN_LABEL),
    ("eurt", EquipmentGroupFuelParam.EURT_COLUMN_LABEL),
    ("eust", EquipmentGroupFuelParam.EUST_COLUMN_LABEL),
    ("sn_ee", EquipmentGroupFuelParam.SN_EE_COLUMN_LABEL),
    ("snk", EquipmentGroupSpecificFuelConsumption.SNK_COLUMN_LABEL),
    ("q", EquipmentGroupFuelParam.Q_COLUMN_LABEL),
    ("qotr", "Тепловое потребление (отборов турбин), тыс.Гкал"),
    ("turt", EquipmentGroupFuelParam.TURT_COLUMN_LABEL),
    ("tust", EquipmentGroupFuelParam.TUST_COLUMN_LABEL),
    ("sn_te", EquipmentGroupFuelParam.SN_TE_COLUMN_LABEL),
    ("sn_t", EquipmentGroupFuelParam.SN_T_COLUMN_LABEL),
    ("b", "Расход топлива, всего"),
    ("nt", EquipmentGroupFuelParam.NT_COLUMN_LABEL),
    ("nt_sum", EquipmentGroupFuelParam.NT_SUM_COLUMN_LABEL),
)


def _rel_name(obj: Any, *attrs: str) -> str:
    current = obj
    for attr in attrs:
        current = getattr(current, attr, None) if current is not None else None
    value = getattr(current, "name", None) if current is not None else None
    return (value or "").strip()


def group_station_and_type(
    group: EquipmentGroup,
) -> tuple[Station | None, EquipmentGroupType | None]:
    for link in getattr(group, "equipment_group_links_v2", None) or []:
        set_station = getattr(link, "equipment_group_set_station", None)
        if set_station is None:
            continue
        return (
            getattr(set_station, "station", None),
            getattr(set_station, "equipment_group_type", None),
        )
    return None, None


def build_equipment_group_param_row(
    *,
    external_code: str | None,
    station_external_code: str | None,
    name: str | None,
    group_type: str | None,
    technology_type: str | None,
    technology_availability: str | None,
    numb: Any,
    year: int,
    param: Any | None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        KEY_GROUP_CODE: external_code or "",
        KEY_STATION_CODE: station_external_code or "",
        KEY_GROUP_NAME: name or "",
        KEY_GROUP_TYPE: group_type or "",
        KEY_TECHNOLOGY_TYPE: technology_type or "",
        KEY_TECHNOLOGY_AVAILABILITY: technology_availability or "",
        KEY_GROUP_NUMB: json_number(numb),
        KEY_YEAR: int(year),
    }
    for attr, label in PARAM_FIELDS:
        row[label] = json_number(getattr(param, attr, None) if param is not None else None) or 0
    return row


def build_equipment_group_params_rows(
    groups: Iterable[EquipmentGroup],
    years: list[int],
    param_map: dict[tuple[int, int], EquipmentGroupFuelParam],
) -> list[dict[str, Any]]:
    """Группа × год; без строки топливных параметров в году — не отдаём."""
    rows: list[dict[str, Any]] = []
    for group in groups:
        station, group_type = group_station_and_type(group)
        type_name = _rel_name(group_type)
        tech_type = _rel_name(group_type, "technology_type")
        tech_avail = _rel_name(group_type, "technology_availability")
        station_code = getattr(station, "external_code", None) if station else None
        for year in years:
            param = param_map.get((group.id, year))
            if param is None:
                continue
            rows.append(
                build_equipment_group_param_row(
                    external_code=group.external_code,
                    station_external_code=station_code,
                    name=group.name,
                    group_type=type_name,
                    technology_type=tech_type,
                    technology_availability=tech_avail,
                    numb=group.numb,
                    year=year,
                    param=param,
                )
            )
    return rows


def _load_groups(version_id: int | None) -> list[EquipmentGroup]:
    return (
        db.session.query(EquipmentGroup)
        .options(
            joinedload(EquipmentGroup.equipment_group_links_v2)
            .joinedload(EquipmentGroupSet.equipment_group_set_station)
            .joinedload(EquipmentGroupSetStation.station),
            joinedload(EquipmentGroup.equipment_group_links_v2)
            .joinedload(EquipmentGroupSet.equipment_group_set_station)
            .joinedload(EquipmentGroupSetStation.equipment_group_type)
            .joinedload(EquipmentGroupType.technology_type),
            joinedload(EquipmentGroup.equipment_group_links_v2)
            .joinedload(EquipmentGroupSet.equipment_group_set_station)
            .joinedload(EquipmentGroupSetStation.equipment_group_type)
            .joinedload(EquipmentGroupType.technology_availability),
        )
        .filter(_version_filter(EquipmentGroup, version_id))
        .order_by(EquipmentGroup.numb.asc().nullslast(), EquipmentGroup.id.asc())
        .all()
    )


def _load_param_map(
    group_ids: list[int],
    years: list[int],
    version_id: int | None,
) -> dict[tuple[int, int], EquipmentGroupFuelParam]:
    if not group_ids or not years:
        return {}
    rows = (
        db.session.query(EquipmentGroupFuelParam)
        .filter(EquipmentGroupFuelParam.equipment_group_id.in_(group_ids))
        .filter(EquipmentGroupFuelParam.year_number.in_(years))
        .filter(_version_filter(EquipmentGroupFuelParam, version_id))
        .all()
    )
    return {
        (int(row.equipment_group_id), int(row.year_number)): row
        for row in rows
        if row.equipment_group_id is not None and row.year_number is not None
    }


def load_equipment_group_params_dataset(
    *,
    version_id: int | None = None,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    resolved_id, version_number = resolve_database_version(version_id)
    years = clip_years(
        load_exchange_years(resolved_id),
        year=year,
        start_year=start_year,
        end_year=end_year,
    )
    groups = _load_groups(resolved_id)
    rows = build_equipment_group_params_rows(
        groups,
        years,
        _load_param_map([g.id for g in groups], years, resolved_id),
    )
    return dataset_envelope(
        DATASET_EQUIPMENT_GROUP_PARAMS,
        database_version=resolved_id,
        version_number=version_number,
        rows=rows,
    )

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Копирование набора данных «Децентрализованная зона» из одной версии БД во все остальные.

Набор соответствует двум страницам с фильтром energy_system_type_filter = «Децентрализованная зона»
(/generation/stations/station_list и /fuel/stations_equipment_groups):

  * станции, у которых РЭС – «не указано» (признак ДЗ: get_decentralized_zone_res_ids);
  * агрегаты этих станций и их данные по годам: мощности, топливо, названия, тип ТЭС;
  * группы оборудования (gs_fue_equipment_groups), привязанные к этим станциям,
    вместе с дочерними группами составных станций (main = numb родителя);
  * связки «группа ↔ станция» (gs_fue_equipment_group_type_stations + gs_fue_equipment_group_sets);
  * параметры групп по годам (fuel_param, extra_fuel_param, specific_fuel_consumption,
    specific_fuel_cost, specific_fuel_price, natural_fuel, fuel_formula, heat_and_tariffs,
    coefficient_results, electricity_production_cost);
  * привязка агрегатов к группам в модуле «Топливо» (gs_fue_machine_fuel_param).

Идентификаторы строк в целевой версии новые; межверсийная идентичность – external_code
станции/агрегата/группы и ref_uuid справочников. Повторный запуск дублей не создаёт:
существующие строки (по external_code, (группа, год) и т.п.) пропускаются.

Запуск (из корня репозитория, с настроенным .env / БД):

  python scripts/copy_decentralized_zone_stations_and_equipment_groups_to_all_versions.py
  python scripts/copy_decentralized_zone_stations_and_equipment_groups_to_all_versions.py --apply --yes
  python scripts/copy_decentralized_zone_stations_and_equipment_groups_to_all_versions.py --source-version 20 --target-versions 22,37

По умолчанию источник определяется автоматически: версия с наибольшим числом станций ДЗ
(при равенстве – с меньшим id, т.е. исходная; на момент написания – версия 20 с 33 станциями).
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect

from app import create_app
from app.common.models.database_version_model import DatabaseVersion
from app.common.services.clear_all_caches import clear_all_application_caches
from app.common.services.refdata_fk_resolve import (
    coerce_regional_district_id_for_db_version,
    coerce_regional_energy_system_id_for_db_version,
)
from app.common.services.tranzaction_services import _commit_with_retry
from app.extensions import db
from app.fuel.models.coefficient.equipment_group_coefficient_result_model import (
    EquipmentGroupCoefficientResult,
)
from app.fuel.models.fue_distribution_parameter_model import DistributionParameter
from app.fuel.models.fue_equipment_group_electricity_production_cost_model import (
    EquipmentGroupElectricityProductionCost,
)
from app.fuel.models.fue_equipment_group_extra_fuel_param_model import (
    EquipmentGroupExtraFuelParam,
)
from app.fuel.models.fue_equipment_group_fuel_formula_model import EquipmentGroupFuelFormula
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_heat_and_tariffs_model import (
    EquipmentGroupHeatAndTariffs,
)
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_natural_fuel_model import EquipmentGroupNaturalFuel
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)
from app.fuel.models.fue_equipment_group_specific_fuel_cost_model import (
    EquipmentGroupSpecificFuelCost,
)
from app.fuel.models.fue_equipment_group_specific_fuel_price_model import (
    EquipmentGroupSpecificFuelPrice,
)
from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
from app.generation.models.machine.machine_fuel_model import MachineFuel
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_name_model import MachineName
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.machine.machine_tes_type_model import MachineTesType
from app.generation.models.station.station_group_model import StationGroup
from app.generation.models.station.station_model import Station
from app.generation.services.station_services.station_access_services import (
    get_decentralized_zone_res_ids,
)
from app.refdata.models.energy_systems.energy_area_model import EnergyArea
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.fuels.fuel_model import Fuel
from app.refdata.models.gen_companies.gen_company_model import GenCompany
from app.refdata.models.refdata_for_stations.condition_type_model import ConditionType
from app.refdata.models.refdata_for_stations.machine.machine_type_model import MachineType
from app.refdata.models.refdata_for_stations.machine.tes_machine_type_model import (
    TesMachineType,
)
from app.refdata.models.refdata_for_stations.machine.tes_type_model import TesType
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
    EquipmentGroupType,
)
from app.refdata.models.refdata_for_stations.technologies.technology_availability_model import (
    TechnologyAvailability,
)
from app.refdata.models.refdata_for_stations.technologies.technology_type_model import (
    TechnologyType,
)
from app.refdata.models.years.year_model import Year

# Служебные колонки: id выдаёт БД, created_at/updated_at – серверные значения.
SERVICE_COLUMNS = frozenset({"id", "created_at", "updated_at"})

# Параметры групп оборудования: копируются по (группа, год) и не имеют собственного «смысла» версии.
PARAM_MODELS = (
    EquipmentGroupFuelParam,
    EquipmentGroupExtraFuelParam,
    EquipmentGroupSpecificFuelConsumption,
    EquipmentGroupSpecificFuelCost,
    EquipmentGroupSpecificFuelPrice,
    EquipmentGroupNaturalFuel,
    EquipmentGroupFuelFormula,
    EquipmentGroupHeatAndTariffs,
    EquipmentGroupCoefficientResult,
    EquipmentGroupElectricityProductionCost,
)

# Дополнительные поля естественного ключа строки параметров (кроме года).
PARAM_KEY_EXTRA_FIELDS = {
    "gs_fue_equipment_group_fuel_formula": ("variant_number",),
    "gs_fue_equipment_group_electricity_production_cost": ("cost_code",),
    "gs_fue_equipment_group_coefficient_results": ("distribution_parameter_id",),
}

# Таблицы с FK (year_number, database_version_id) → gs_sys_years: год обязан быть
# в версии-цели, иначе строка не переносится.
PARAM_MODELS_WITH_VERSIONED_YEAR_FK = frozenset(
    {
        EquipmentGroupNaturalFuel.__tablename__,
        EquipmentGroupHeatAndTariffs.__tablename__,
    }
)

MACHINE_FK_FIELDS = (
    ("id_condition_type", ConditionType, "Условие агрегата"),
    ("id_gen_company", GenCompany, "Генерирующая компания"),
    ("id_energy_area", EnergyArea, "Энергорайон"),
    ("id_machine_type", MachineType, "Тип агрегата"),
    ("id_tes_machine_type", TesMachineType, "Тип ТЭС-агрегата"),
    ("id_technology_availability", TechnologyAvailability, "Доступность технологии"),
    ("id_technology_type", TechnologyType, "Тип технологии"),
    ("id_equipment_group", EquipmentGroupType, "Тип группы оборудования агрегата"),
)

# Справочники, которых может не быть в целевой версии: для полноты набора копия строки
# справочника создаётся в целевой версии с тем же ref_uuid (иначе у агрегата «пропадёт»
# генкомпания и в списке станций не будет колонки ГК).
AUTO_COPIED_REFDATA = {GenCompany: "Генерирующая компания"}


class RefdataResolver:
    """Поиск id справочной записи в целевой версии БД.

    Порядок: та же строка (id версии совпал) → ref_uuid в целевой версии → ref_uuid
    без версии (legacy) → совпадение по названию в целевой версии.
    """

    def __init__(self, target_version_id: int):
        self.version_id = target_version_id
        self._cache: dict[tuple[str, int], int | None] = {}
        self.missing: set[str] = set()
        self.created_refdata: dict[str, int] = defaultdict(int)

    def resolve(self, model, source_id: int | None, label: str) -> int | None:
        if source_id is None:
            return None
        cache_key = (model.__name__, source_id)
        if cache_key not in self._cache:
            resolved = self._lookup(model, source_id)
            if resolved is None:
                self.missing.add(f"{label} id={source_id}")
            self._cache[cache_key] = resolved
        return self._cache[cache_key]

    def resolve_regional_district(self, source_id: int | None) -> int | None:
        if source_id is None:
            return None
        resolved = coerce_regional_district_id_for_db_version(source_id, self.version_id)
        if resolved is None:
            self.missing.add(f"Субъект РФ id={source_id}")
        return resolved

    def resolve_regional_energy_system(self, source_id: int | None) -> int | None:
        if source_id is None:
            return None
        resolved = coerce_regional_energy_system_id_for_db_version(source_id, self.version_id)
        if resolved is None:
            self.missing.add(f"РЭС id={source_id}")
        return resolved

    def _lookup(self, model, source_id: int) -> int | None:
        source = db.session.get(model, source_id)
        if source is None:
            return None
        if getattr(source, "database_version_id", None) == self.version_id:
            return source_id

        ref_uuid = (getattr(source, "ref_uuid", None) or "").strip()
        if ref_uuid:
            for version_filter in (
                model.database_version_id == self.version_id,
                model.database_version_id.is_(None),
            ):
                row = (
                    model.query.filter(model.ref_uuid == ref_uuid)
                    .filter(version_filter)
                    .order_by(model.id.asc())
                    .first()
                )
                if row is not None:
                    return row.id

        name = (getattr(source, "name", None) or "").strip()
        if name and hasattr(model, "name"):
            row = (
                model.query.filter(model.name == name)
                .filter(model.database_version_id == self.version_id)
                .order_by(model.id.asc())
                .first()
            )
            if row is not None:
                return row.id

        if model in AUTO_COPIED_REFDATA:
            return self._copy_refdata(model, source)
        return None

    def _copy_refdata(self, model, source) -> int:
        """Копия строки справочника в целевой версии (тот же ref_uuid)."""
        row = model(
            database_version_id=self.version_id,
            **_row_values(
                model,
                source,
                frozenset({"database_version_id", "version"}),
            ),
        )
        db.session.add(row)
        db.session.flush()
        self.created_refdata[model.__tablename__] += 1
        return row.id


@dataclass
class VersionResult:
    counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    skipped: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    warnings: set[str] = field(default_factory=set)


def _row_values(model, source, skip: frozenset[str] = frozenset()) -> dict:
    """Значения всех колонок строки-источника, кроме служебных и перечисленных в skip.

    Ключи – имена атрибутов модели (а не колонок БД): у части полей модуля «Топливо»
    они различаются (например, колонка «вед» маппится на атрибут ved_cyrillic).
    """
    return {
        prop.key: getattr(source, prop.key)
        for prop in inspect(model).column_attrs
        if prop.key not in SERVICE_COLUMNS and prop.key not in skip
    }


def _detect_source_version() -> int | None:
    """Версия с наибольшим числом станций ДЗ (при равенстве – с меньшим id)."""
    found: list[tuple[int, int]] = []
    versions = (
        DatabaseVersion.query.filter(DatabaseVersion.id.isnot(None))
        .order_by(DatabaseVersion.id.asc())
        .all()
    )
    for version in versions:
        res_ids = list(get_decentralized_zone_res_ids(version.id))
        if not res_ids:
            continue
        count = Station.query.filter(
            Station.database_version_id == version.id,
            Station.id_regional_energy_system.in_(res_ids),
        ).count()
        if count:
            found.append((version.id, count))
    if not found:
        return None
    found.sort(key=lambda item: (-item[1], item[0]))
    if len(found) > 1 and found[0][1] == found[1][1]:
        # Набор уже скопирован в несколько версий: берём самую старую (исходную) –
        # повторный запуск тогда ничего не меняет.
        print(
            f"Станции ДЗ есть в нескольких версиях {found[:3]}; "
            f"источник по умолчанию – {found[0][0]}. "
            f"Другой источник задаётся через --source-version."
        )
    return found[0][0]


def _load_source(source_version_id: int) -> tuple[list[Station], list[EquipmentGroup]]:
    res_ids = list(get_decentralized_zone_res_ids(source_version_id))
    if not res_ids:
        raise SystemExit(
            f"В версии {source_version_id} нет РЭС «не указано» "
            f"(признак децентрализованной зоны)."
        )
    stations = (
        Station.query.filter(
            Station.database_version_id == source_version_id,
            Station.id_regional_energy_system.in_(res_ids),
        )
        .order_by(Station.id.asc())
        .all()
    )
    groups = _source_equipment_groups([station.id for station in stations], source_version_id)
    return stations, groups


def _source_equipment_groups(station_ids: list[int], source_version_id: int) -> list[EquipmentGroup]:
    """Группы, привязанные к станциям, плюс дочерние группы составных станций (main = numb)."""
    if not station_ids:
        return []

    group_ids = {
        row[0]
        for row in db.session.query(EquipmentGroupSet.equipment_group_id)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSet.equipment_group_set_station_id == EquipmentGroupSetStation.id,
        )
        .filter(EquipmentGroupSetStation.station_id.in_(station_ids))
        .distinct()
        .all()
    }

    groups: dict[int, EquipmentGroup] = {}
    pending = list(group_ids)
    while pending:
        group = db.session.get(EquipmentGroup, pending.pop())
        if group is None or group.id in groups:
            continue
        groups[group.id] = group
        if group.numb is None:
            continue
        children = (
            EquipmentGroup.query.filter(
                EquipmentGroup.main == group.numb,
                EquipmentGroup.database_version_id == source_version_id,
            )
            .order_by(EquipmentGroup.id.asc())
            .all()
        )
        pending.extend(child.id for child in children if child.id not in groups)
    return [groups[group_id] for group_id in sorted(groups)]


def _station_machines(source_station_id: int) -> list[Machine]:
    return (
        Machine.query.filter(Machine.id_station == source_station_id)
        .order_by(Machine.id.asc())
        .all()
    )


def _machine_rows(model, machine_id: int) -> list:
    return (
        model.query.filter(model.id_machine == machine_id)
        .order_by(model.year_number.asc(), model.id.asc())
        .all()
    )


def _target_years(target_version_id: int) -> set[int]:
    return {
        row[0]
        for row in db.session.query(Year.number)
        .filter(Year.database_version_id == target_version_id)
        .all()
    }


def _copy_station(
    source: Station, target_version_id: int, resolver: RefdataResolver
) -> tuple[Station, bool]:
    existing = (
        Station.query.filter(
            Station.external_code == source.external_code,
            Station.database_version_id == target_version_id,
        )
        .order_by(Station.id.asc())
        .first()
    )
    if existing is not None:
        return existing, False

    station = Station(
        external_code=source.external_code,
        database_version_id=target_version_id,
        id_station_group=resolver.resolve(
            StationGroup, source.id_station_group, "Группа станций"
        ),
        id_condition_type=resolver.resolve(
            ConditionType, source.id_condition_type, "Условие станции"
        ),
        id_energy_unit=resolver.resolve(EnergyUnit, source.id_energy_unit, "Энергоузел"),
        id_station_type=resolver.resolve(
            StationType, source.id_station_type, "Тип станции"
        ),
        id_regional_district=resolver.resolve_regional_district(
            source.id_regional_district
        ),
        id_regional_energy_system=resolver.resolve_regional_energy_system(
            source.id_regional_energy_system
        ),
        **_row_values(
            Station,
            source,
            frozenset(
                {
                    "external_code",
                    "database_version_id",
                    "version",
                    "id_station_group",
                    "id_condition_type",
                    "id_energy_unit",
                    "id_station_type",
                    "id_regional_district",
                    "id_regional_energy_system",
                }
            ),
        ),
    )
    db.session.add(station)
    db.session.flush()
    return station, True


def _copy_machine(
    source: Machine,
    target_station_id: int,
    target_version_id: int,
    resolver: RefdataResolver,
) -> tuple[Machine, bool]:
    existing = (
        Machine.query.filter(
            Machine.external_code == source.external_code,
            Machine.database_version_id == target_version_id,
        )
        .order_by(Machine.id.asc())
        .first()
    )
    if existing is not None:
        return existing, False

    fk_fields = {item[0] for item in MACHINE_FK_FIELDS}
    machine = Machine(
        external_code=source.external_code,
        id_station=target_station_id,
        database_version_id=target_version_id,
        **{
            field_name: resolver.resolve(model, getattr(source, field_name), label)
            for field_name, model, label in MACHINE_FK_FIELDS
        },
        **_row_values(
            Machine,
            source,
            frozenset({"external_code", "id_station", "database_version_id", "version"})
            | fk_fields,
        ),
    )
    db.session.add(machine)
    db.session.flush()
    return machine, True


def _copy_year_rows(
    model,
    source_machine_id: int,
    target_machine_id: int,
    target_version_id: int,
    transform=None,
) -> int:
    existing_years = {
        row[0]
        for row in db.session.query(model.year_number)
        .filter(model.id_machine == target_machine_id)
        .all()
    }
    created = 0
    for source in _machine_rows(model, source_machine_id):
        if source.year_number in existing_years:
            continue
        values = _row_values(
            model, source, frozenset({"id_machine", "database_version_id"})
        )
        if transform is not None:
            values.update(transform(source))
        db.session.add(
            model(
                id_machine=target_machine_id,
                database_version_id=target_version_id,
                **values,
            )
        )
        existing_years.add(source.year_number)
        created += 1
    return created


def _copy_machine_details(
    source_machine: Machine,
    target_machine: Machine,
    target_version_id: int,
    resolver: RefdataResolver,
) -> dict[str, int]:
    return {
        MachinePower.__tablename__: _copy_year_rows(
            MachinePower, source_machine.id, target_machine.id, target_version_id
        ),
        MachineFuel.__tablename__: _copy_year_rows(
            MachineFuel,
            source_machine.id,
            target_machine.id,
            target_version_id,
            transform=lambda row: {
                "id_fuel": resolver.resolve(Fuel, row.id_fuel, "Вид топлива")
            },
        ),
        MachineName.__tablename__: _copy_year_rows(
            MachineName, source_machine.id, target_machine.id, target_version_id
        ),
        MachineTesType.__tablename__: _copy_year_rows(
            MachineTesType,
            source_machine.id,
            target_machine.id,
            target_version_id,
            transform=lambda row: {
                "id_tes_type": resolver.resolve(
                    TesType, row.id_tes_type, "Тип ТЭС"
                )
            },
        ),
    }


def _target_group_id(
    source_group_id: int | None,
    target_version_id: int,
    group_map: dict[int, int],
) -> int | None:
    if source_group_id is None:
        return None
    if source_group_id in group_map:
        return group_map[source_group_id]
    source = db.session.get(EquipmentGroup, source_group_id)
    if source is None:
        return None
    target = (
        EquipmentGroup.query.filter(
            EquipmentGroup.external_code == source.external_code,
            EquipmentGroup.database_version_id == target_version_id,
        )
        .order_by(EquipmentGroup.id.asc())
        .first()
    )
    return target.id if target is not None else None


def _copy_machine_fuel_param(
    source_machine: Machine,
    target_machine: Machine,
    target_version_id: int,
    group_map: dict[int, int],
) -> int:
    source = (
        MachineFuelParam.query.filter(MachineFuelParam.machine_id == source_machine.id)
        .order_by(MachineFuelParam.id.asc())
        .first()
    )
    if source is None:
        return 0
    existing = (
        MachineFuelParam.query.filter(MachineFuelParam.machine_id == target_machine.id)
        .order_by(MachineFuelParam.id.asc())
        .first()
    )
    if existing is not None:
        return 0

    db.session.add(
        MachineFuelParam(
            machine_id=target_machine.id,
            equipment_group_id=_target_group_id(
                source.equipment_group_id, target_version_id, group_map
            ),
            database_version_id=target_version_id,
            **_row_values(
                MachineFuelParam,
                source,
                frozenset({"machine_id", "equipment_group_id", "database_version_id"}),
            ),
        )
    )
    return 1


def _ensure_equipment_group(
    source: EquipmentGroup, target_version_id: int, resolver: RefdataResolver
) -> tuple[EquipmentGroup, bool]:
    existing = (
        EquipmentGroup.query.filter(
            EquipmentGroup.external_code == source.external_code,
            EquipmentGroup.database_version_id == target_version_id,
        )
        .order_by(EquipmentGroup.id.asc())
        .first()
    )
    if existing is not None:
        return existing, False

    group = EquipmentGroup(
        external_code=source.external_code,
        database_version_id=target_version_id,
        regional_district_id=resolver.resolve_regional_district(
            source.regional_district_id
        ),
        regional_energy_system_id=resolver.resolve_regional_energy_system(
            source.regional_energy_system_id
        ),
        **_row_values(
            EquipmentGroup,
            source,
            frozenset(
                {
                    "external_code",
                    "database_version_id",
                    "regional_district_id",
                    "regional_energy_system_id",
                }
            ),
        ),
    )
    db.session.add(group)
    db.session.flush()
    return group, True


def _ensure_group_station_links(
    source_group: EquipmentGroup,
    target_group: EquipmentGroup,
    target_version_id: int,
    station_map: dict[int, int],
    resolver: RefdataResolver,
) -> tuple[int, int]:
    """Связки группы со станциями. Возвращает (создано связок, создано связок станция+тип)."""
    links_created = 0
    links_created_by_set_station = 0
    source_links = (
        db.session.query(
            EquipmentGroupSetStation.station_id,
            EquipmentGroupSetStation.equipment_group_type_id,
        )
        .join(
            EquipmentGroupSet,
            EquipmentGroupSet.equipment_group_set_station_id == EquipmentGroupSetStation.id,
        )
        .filter(EquipmentGroupSet.equipment_group_id == source_group.id)
        .order_by(EquipmentGroupSetStation.id.asc())
        .all()
    )
    for station_id, group_type_id in source_links:
        target_station_id = station_map.get(station_id)
        if target_station_id is None:
            resolver.missing.add(
                f"Станция id={station_id} группы «{source_group.name}» не найдена в целевой версии"
            )
            continue
        target_type_id = resolver.resolve(
            EquipmentGroupType, group_type_id, "Тип группы оборудования"
        )

        set_station_query = EquipmentGroupSetStation.query.filter(
            EquipmentGroupSetStation.station_id == target_station_id,
            EquipmentGroupSetStation.database_version_id == target_version_id,
        )
        if target_type_id is None:
            set_station_query = set_station_query.filter(
                EquipmentGroupSetStation.equipment_group_type_id.is_(None)
            )
        else:
            set_station_query = set_station_query.filter(
                EquipmentGroupSetStation.equipment_group_type_id == target_type_id
            )
        set_station = set_station_query.order_by(
            EquipmentGroupSetStation.id.asc()
        ).first()
        if set_station is None:
            set_station = EquipmentGroupSetStation(
                station_id=target_station_id,
                equipment_group_type_id=target_type_id,
                database_version_id=target_version_id,
            )
            db.session.add(set_station)
            db.session.flush()
            links_created_by_set_station += 1

        link_exists = EquipmentGroupSet.query.filter(
            EquipmentGroupSet.equipment_group_id == target_group.id,
            EquipmentGroupSet.equipment_group_set_station_id == set_station.id,
        ).first()
        if link_exists is None:
            db.session.add(
                EquipmentGroupSet(
                    equipment_group_id=target_group.id,
                    equipment_group_set_station_id=set_station.id,
                )
            )
            links_created += 1
    return links_created, links_created_by_set_station


def _copy_group_params(
    model,
    source_group: EquipmentGroup,
    target_group: EquipmentGroup,
    target_version_id: int,
    target_years: set[int],
    resolver: RefdataResolver,
) -> tuple[int, int]:
    """Параметры группы по годам. Возвращает (создано, пропущено)."""
    extra_key_fields = PARAM_KEY_EXTRA_FIELDS.get(model.__tablename__, ())
    existing_keys = {
        tuple(getattr(row, key) for key in ("year_number",) + extra_key_fields)
        for row in model.query.filter(model.equipment_group_id == target_group.id).all()
    }

    created = 0
    skipped = 0
    source_rows = (
        model.query.filter(model.equipment_group_id == source_group.id)
        .order_by(model.id.asc())
        .all()
    )
    for source in source_rows:
        if (
            model.__tablename__ in PARAM_MODELS_WITH_VERSIONED_YEAR_FK
            and source.year_number not in target_years
        ):
            skipped += 1
            continue

        values = _row_values(
            model, source, frozenset({"equipment_group_id", "database_version_id"})
        )
        if model is EquipmentGroupCoefficientResult:
            values["distribution_parameter_id"] = resolver.resolve(
                DistributionParameter,
                source.distribution_parameter_id,
                "Параметр распределения",
            )
            if values["distribution_parameter_id"] is None:
                skipped += 1
                continue

        row_key = tuple(
            values.get(key) for key in ("year_number",) + extra_key_fields
        )
        if row_key in existing_keys:
            continue

        db.session.add(
            model(
                equipment_group_id=target_group.id,
                database_version_id=target_version_id,
                **values,
            )
        )
        existing_keys.add(row_key)
        created += 1
    return created, skipped


def _run_version(
    target_version_id: int,
    source_stations: list[Station],
    source_groups: list[EquipmentGroup],
) -> VersionResult:
    result = VersionResult()
    resolver = RefdataResolver(target_version_id)
    target_years = _target_years(target_version_id)
    station_map: dict[int, int] = {}
    group_map: dict[int, int] = {}

    # 1. Станции ДЗ.
    for source_station in source_stations:
        target_station, created = _copy_station(
            source_station, target_version_id, resolver
        )
        station_map[source_station.id] = target_station.id
        result.counts[Station.__tablename__] += int(created)

    # 2. Группы оборудования, их связки со станциями и параметры.
    for source_group in source_groups:
        target_group, created = _ensure_equipment_group(
            source_group, target_version_id, resolver
        )
        group_map[source_group.id] = target_group.id
        result.counts[EquipmentGroup.__tablename__] += int(created)

        links, new_set_stations = _ensure_group_station_links(
            source_group, target_group, target_version_id, station_map, resolver
        )
        result.counts[EquipmentGroupSet.__tablename__] += links
        result.counts[EquipmentGroupSetStation.__tablename__] += new_set_stations

        for model in PARAM_MODELS:
            created_rows, skipped_rows = _copy_group_params(
                model,
                source_group,
                target_group,
                target_version_id,
                target_years,
                resolver,
            )
            result.counts[model.__tablename__] += created_rows
            result.skipped[model.__tablename__] += skipped_rows

    # 3. Агрегаты станций, их данные по годам и привязка к группам.
    for source_station in source_stations:
        target_station_id = station_map[source_station.id]
        for source_machine in _station_machines(source_station.id):
            target_machine, created = _copy_machine(
                source_machine, target_station_id, target_version_id, resolver
            )
            result.counts[Machine.__tablename__] += int(created)
            for table_name, created_rows in _copy_machine_details(
                source_machine, target_machine, target_version_id, resolver
            ).items():
                result.counts[table_name] += created_rows
            result.counts[MachineFuelParam.__tablename__] += _copy_machine_fuel_param(
                source_machine, target_machine, target_version_id, group_map
            )

    result.warnings = set(resolver.missing)
    for table_name, created in resolver.created_refdata.items():
        result.counts[table_name] += created
    return result


def _parse_target_versions(raw: str | None) -> list[int] | None:
    if not raw:
        return None
    result: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            result.append(int(part))
        except ValueError:
            raise SystemExit(f"Некорректный id версии в --target-versions: {part!r}")
    return result or None


def _print_version_result(version: DatabaseVersion, result: VersionResult) -> None:
    print(f"Версия {version.id} ({version.version_number}):")
    printed = False
    for table_name in sorted(result.counts):
        created = result.counts[table_name]
        skipped = result.skipped.get(table_name, 0)
        if not created and not skipped:
            continue
        line = f"  {table_name}: создано {created}"
        if skipped:
            line += f", пропущено {skipped}"
        print(line)
        printed = True
    if not printed:
        print("  новые строки не нужны – данные уже на месте")
    for warning in sorted(result.warnings):
        print(f"  ! не сопоставлено: {warning}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Скопировать станции «Децентрализованной зоны» вместе с их группами "
            "оборудования и параметрами из одной версии БД во все остальные."
        )
    )
    parser.add_argument(
        "--source-version",
        type=int,
        default=None,
        help="id версии-источника (database_version_id); по умолчанию определяется автоматически.",
    )
    parser.add_argument(
        "--target-versions",
        default=None,
        help="Список id целевых версий через запятую; по умолчанию все остальные.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только план, без commit (по умолчанию, если нет --apply).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Выполнить вставки и commit.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Без подтверждения (для --apply).",
    )
    args = parser.parse_args()

    apply_changes = bool(args.apply)

    app = create_app()
    with app.app_context():
        source_version_id = args.source_version or _detect_source_version()
        if source_version_id is None:
            raise SystemExit("Не найдено версий БД со станциями децентрализованной зоны.")
        source_version = db.session.get(DatabaseVersion, source_version_id)
        if source_version is None:
            raise SystemExit(
                f"В gs_sys.gs_database_versions нет id={source_version_id}."
            )

        source_stations, source_groups = _load_source(source_version_id)
        if not source_stations:
            print(
                f"В версии {source_version_id} нет станций с РЭС «не указано» – нечего копировать."
            )
            return 0

        target_ids = _parse_target_versions(args.target_versions)
        target_query = DatabaseVersion.query.filter(
            DatabaseVersion.id.isnot(None),
            DatabaseVersion.id != source_version_id,
        )
        if target_ids:
            target_query = target_query.filter(DatabaseVersion.id.in_(target_ids))
        targets = target_query.order_by(DatabaseVersion.id.asc()).all()
        if not targets:
            print("Других версий в gs_sys.gs_database_versions нет. Нечего копировать.")
            return 0

        machine_count = sum(len(_station_machines(station.id)) for station in source_stations)

        print("=" * 78)
        print("Копирование набора «Децентрализованная зона» по версиям БД")
        print("=" * 78)
        print(f"Старт:     {datetime.now().isoformat(timespec='seconds')}")
        print(
            f"Источник:  database_version_id = {source_version_id} "
            f"({source_version.version_number})"
        )
        print(
            f"Набор:     станций {len(source_stations)}, агрегатов {machine_count}, "
            f"групп оборудования {len(source_groups)}"
        )
        print(f"Цели:      database_version_id in {[v.id for v in targets]}")
        print(f"Режим:     {'APPLY' if apply_changes else 'DRY-RUN (без commit)'}")
        print()

        if apply_changes and not args.yes:
            answer = input(
                f"Скопировать набор в {len(targets)} верс(ий) БД? [y/N]: "
            )
            if str(answer).strip().lower() not in ("y", "yes", "д", "да"):
                print("Отмена.")
                return 0

        failures: list[int] = []
        totals: dict[str, int] = defaultdict(int)
        for version in targets:
            try:
                result = _run_version(version.id, source_stations, source_groups)
                if apply_changes:
                    _commit_with_retry()
                else:
                    db.session.rollback()
            except Exception as exc:  # noqa: BLE001 – версия изолирована, отчёт в конце
                db.session.rollback()
                failures.append(version.id)
                print(f"Версия {version.id} ({version.version_number}): ОШИБКА {exc!r}")
                continue
            _print_version_result(version, result)
            for table_name, created in result.counts.items():
                totals[table_name] += created
        print("-" * 78)
        print(
            ("Создано записей: " if apply_changes else "Будет создано записей: ")
            + str(sum(totals.values()))
        )
        for table_name in sorted(totals):
            print(f"  {table_name}: {totals[table_name]}")
        if failures:
            print(f"Версии с ошибками: {failures}")
        if apply_changes and not failures:
            cache_result = clear_all_application_caches()
            print(f"Кэши приложения: {cache_result}")
        print(f"Конец:     {datetime.now().isoformat(timespec='seconds')}")
        return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

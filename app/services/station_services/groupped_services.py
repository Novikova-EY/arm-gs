from app import db
from decimal import Decimal
from sqlalchemy import func
from collections import defaultdict
from sqlalchemy.orm import joinedload
from app.models import (
    UnionEnergySystem, RegionalEnergySystem, EnergySystemType, 
    RegionalDistrict, Station, Machine, MachinePower, MachineTesType,
)

def get_station_hierarchy_aggregates(start_year, end_year):
    return (
        db.session.query(
            Station.id_energy_unit.label("energy_unit_id"),
            RegionalDistrict.id.label("regional_district_id"),
            RegionalEnergySystem.id.label("regional_energy_system_id"),
            UnionEnergySystem.id.label("union_energy_system_id"),
            EnergySystemType.id.label("energy_system_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .join(RegionalEnergySystem.union_energy_system)
        .join(UnionEnergySystem.energy_system_type)
        .join(Machine, Machine.id_station == Station.id)
        .join(MachinePower, MachinePower.id_machine == Machine.id)
        .filter(MachinePower.year_number >= start_year, MachinePower.year_number <= end_year)
        .group_by(
            Station.id_energy_unit,
            RegionalDistrict.id,
            RegionalEnergySystem.id,
            UnionEnergySystem.id,
            EnergySystemType.id,
            MachinePower.year_number
        )
        .all()
    )


def build_hierarchy_structure(aggregated_rows, stations: list[Station], include_names=False):
    grouped_data = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(
                    lambda: defaultdict(list)
                )
            )
        )
    )

    p_ust_by_energy_unit = defaultdict(lambda: defaultdict(Decimal))
    p_ogr_by_energy_unit = defaultdict(lambda: defaultdict(Decimal))
    p_rasp_by_energy_unit = defaultdict(lambda: defaultdict(Decimal))

    p_ust_by_regional_district = defaultdict(lambda: defaultdict(Decimal))
    p_ogr_by_regional_district = defaultdict(lambda: defaultdict(Decimal))
    p_rasp_by_regional_district = defaultdict(lambda: defaultdict(Decimal))

    p_ust_by_regional_energy_system = defaultdict(lambda: defaultdict(Decimal))
    p_ogr_by_regional_energy_system = defaultdict(lambda: defaultdict(Decimal))
    p_rasp_by_regional_energy_system = defaultdict(lambda: defaultdict(Decimal))

    p_ust_by_union_energy_system = defaultdict(lambda: defaultdict(Decimal))
    p_ogr_by_union_energy_system = defaultdict(lambda: defaultdict(Decimal))
    p_rasp_by_union_energy_system = defaultdict(lambda: defaultdict(Decimal))

    p_ust_by_energy_system_type = defaultdict(lambda: defaultdict(Decimal))
    p_ogr_by_energy_system_type = defaultdict(lambda: defaultdict(Decimal))
    p_rasp_by_energy_system_type = defaultdict(lambda: defaultdict(Decimal))

    p_ust_total = defaultdict(Decimal)
    p_ogr_total = defaultdict(Decimal)
    p_rasp_total = defaultdict(Decimal)

    # Названия
    est_names = {}
    ues_names = {}
    res_names = {}
    rd_names = {}
    eu_names = {}

    # 📦 Структура агрегатов по уровням
    for row in aggregated_rows:
        est_id = row.energy_system_type_id
        ues_id = row.union_energy_system_id
        res_id = row.regional_energy_system_id
        rd_id = row.regional_district_id
        eu_id = row.energy_unit_id
        year = row.year

        val = Decimal(row.p_ust or 0)
        p_ust_by_energy_unit[eu_id][year] += val
        p_ust_by_regional_district[rd_id][year] += val
        p_ust_by_regional_energy_system[res_id][year] += val
        p_ust_by_union_energy_system[ues_id][year] += val
        p_ust_by_energy_system_type[est_id][year] += val
        p_ust_total[year] += val

        val = Decimal(row.p_ogr or 0)
        p_ogr_by_energy_unit[eu_id][year] += val
        p_ogr_by_regional_district[rd_id][year] += val
        p_ogr_by_regional_energy_system[res_id][year] += val
        p_ogr_by_union_energy_system[ues_id][year] += val
        p_ogr_by_energy_system_type[est_id][year] += val
        p_ogr_total[year] += val

        val = Decimal(row.p_rasp or 0)
        p_rasp_by_energy_unit[eu_id][year] += val
        p_rasp_by_regional_district[rd_id][year] += val
        p_rasp_by_regional_energy_system[res_id][year] += val
        p_rasp_by_union_energy_system[ues_id][year] += val
        p_rasp_by_energy_system_type[est_id][year] += val
        p_rasp_total[year] += val

    # 📦 Группировка станций
    for station in stations:
        if not station.regional_district or not station.regional_district.regional_energy_systems:
            continue

        for res in station.regional_district.regional_energy_systems:
            ues = res.union_energy_system
            if not ues:
                continue

            est_id = ues.id_energy_system_type
            ues_id = ues.id
            res_id = res.id
            rd_id = station.id_regional_district
            eu_id = station.id_energy_unit or 100

            grouped_data[est_id][ues_id][res_id][rd_id][eu_id].append(station)

            if include_names:
                est_names[est_id] = ues.energy_system_type.name if ues.energy_system_type else f"id={est_id}"
                ues_names[ues_id] = ues.name
                res_names[res_id] = res.name
                rd_names[rd_id] = station.regional_district.name
                if station.energy_unit:
                    eu_names[eu_id] = station.energy_unit.name
                else:
                    eu_names[eu_id] = "не указано"

    # 📦 Итог
    return {
        "grouped_stations": grouped_data,
        "aggregated_by_energy_unit": {
            "p_ust": p_ust_by_energy_unit,
            "p_ogr": p_ogr_by_energy_unit,
            "p_rasp": p_rasp_by_energy_unit,
        },
        "aggregated_by_regional_district": {
            "p_ust": p_ust_by_regional_district,
            "p_ogr": p_ogr_by_regional_district,
            "p_rasp": p_rasp_by_regional_district,
        },
        "aggregated_by_regional_energy_system": {
            "p_ust": p_ust_by_regional_energy_system,
            "p_ogr": p_ogr_by_regional_energy_system,
            "p_rasp": p_rasp_by_regional_energy_system,
        },
        "aggregated_by_union_energy_system": {
            "p_ust": p_ust_by_union_energy_system,
            "p_ogr": p_ogr_by_union_energy_system,
            "p_rasp": p_rasp_by_union_energy_system,
        },
        "aggregated_by_energy_system_type": {
            "p_ust": p_ust_by_energy_system_type,
            "p_ogr": p_ogr_by_energy_system_type,
            "p_rasp": p_rasp_by_energy_system_type,
        },
        "aggregated_total": {
            "p_ust": p_ust_total,
            "p_ogr": p_ogr_total,
            "p_rasp": p_rasp_total,
        },
        **(
            {
                "energy_system_type_name": est_names,
                "union_energy_system_name": ues_names,
                "regional_energy_system_name": res_names,
                "regional_district_name": rd_names,
                "energy_unit_name": eu_names,
            } if include_names else {}
        )
    }




def fetch_machines_with_rowspans(station_ids: list[int]):
    """
    Возвращает агрегаты с правильным group_rowspan и fuel_rowspan, как раньше.
    Сортировка и проставление rowspans вручную.
    """
    # Загружаем агрегаты
    machines = Machine.query.options(
        joinedload(Machine.station_type),
        joinedload(Machine.tes_machine_type),
        joinedload(Machine.machine_station),
        joinedload(Machine.machine_tes_types).joinedload(MachineTesType.tes_type),
    ).filter(Machine.id_station.in_(station_ids)).all()

    # Привязываем к станциям
    station_machine_map = defaultdict(list)
    for m in machines:
        station_machine_map[m.id_station].append(m)

    # Для каждой станции сортируем и проставляем rowspan
    for machine_list in station_machine_map.values():
        # сортировка
        machine_list.sort(key=lambda m: (
            (m.machine_group or "").lower(),
            (m.fuel_so or "").lower(),
            int(m.machine_number) if m.machine_number and str(m.machine_number).isdigit() else float('inf')
        ))

        # group_rowspan
        group_dict = defaultdict(list)
        for m in machine_list:
            group_key = (m.machine_group or "").strip()
            group_dict[group_key].append(m)
        for group in group_dict.values():
            group[0].group_rowspan = len(group)
            for m in group[1:]:
                m.group_rowspan = 0

        # fuel_rowspan
        fuel_dict = defaultdict(list)
        for m in machine_list:
            fuel_key = (m.fuel_so or "").strip()
            fuel_dict[fuel_key].append(m)
        for group in fuel_dict.values():
            group[0].fuel_rowspan = len(group)
            for m in group[1:]:
                m.fuel_rowspan = 0

    # Объединяем все машины в один список
    all_machines = []
    for lst in station_machine_map.values():
        all_machines.extend(lst)

    return all_machines
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


def build_hierarchy_structure(stations: list[Station], include_names=False):
    from collections import defaultdict

    # Многоуровневая вложенность
    grouped_data = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(
                    lambda: defaultdict(list)
                )
            )
        )
    )

    # Для имен
    est_names = {}
    ues_names = {}
    res_names = {}
    rd_names = {}
    eu_names = {}

    for station in stations:
        # Проверка наличия регионального округа и региональной энергосистемы
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

            # Важно: проверяем наличие энергоузла
            if station.id_energy_unit is not None:
                eu_id = station.id_energy_unit
                eu_name = station.energy_unit.name if station.energy_unit else 100
            else:
                eu_id = 100
                eu_name = "без энергоузла"

            # Добавляем станцию в иерархию
            grouped_data[est_id][ues_id][res_id][rd_id][eu_id].append(station)

            if include_names:
                est_names[est_id] = ues.energy_system_type.name if ues.energy_system_type else f"id={est_id}"
                ues_names[ues_id] = ues.name
                res_names[res_id] = res.name
                rd_names[rd_id] = station.regional_district.name
                eu_names[eu_id] = eu_name

    result = {
        "grouped_stations": grouped_data,
        "stations": stations,
    }

    if include_names:
        result.update({
            "energy_system_type_name": est_names,
            "union_energy_system_name": ues_names,
            "regional_energy_system_name": res_names,
            "regional_district_name": rd_names,
            "energy_unit_name": eu_names,
        })

    return result



def fetch_machines_with_rowspans(station_ids: list[int]):
    machines = Machine.query.options(
        joinedload(Machine.station_type),
        joinedload(Machine.tes_machine_type),
        joinedload(Machine.machine_station),
        joinedload(Machine.machine_tes_types).joinedload(MachineTesType.tes_type),
    ).filter(Machine.id_station.in_(station_ids)).all()

    station_machine_map = defaultdict(list)
    for m in machines:
        station_machine_map[m.id_station].append(m)

    for machine_list in station_machine_map.values():
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

    all_machines = []
    for lst in station_machine_map.values():
        all_machines.extend(lst)

    # 🛡 Устанавливаем значения по умолчанию, если агрегат оказался вне всех групп
    for m in all_machines:
        if m.group_rowspan is None:
            m.group_rowspan = 1
        if m.fuel_rowspan is None:
            m.fuel_rowspan = 1

    return all_machines
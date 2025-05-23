from decimal import Decimal
from collections import defaultdict

def group_stations_hierarchy(stations, include_names=False):
    grouped_data = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(
                    lambda: defaultdict(list)
                )
            )
        )
    )

    energy_system_type_name = {}
    union_energy_system_name = {}
    regional_energy_system_name = {}
    regional_district_name = {}
    energy_unit_name = {}

    # Агрегаты по уровням
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

    for station in stations:
        rd = station.regional_district
        if not rd or not rd.regional_energy_systems:
            continue

        for res in rd.regional_energy_systems:
            ues = res.union_energy_system
            if not ues:
                continue

            ues_id = ues.id
            est_id = ues.id_energy_system_type
            regional_district_id = rd.id
            energy_unit_id = station.energy_unit.id if station.energy_unit else 100
            res_id = res.id

            grouped_data[est_id][ues_id][res_id][regional_district_id][energy_unit_id].append(station)

            if hasattr(station, "powers_by_year") and station.powers_by_year:
                for year, values in station.powers_by_year.items():
                    if not values:
                        continue

                    for key, target_dicts in [
                        ("p_ust", [p_ust_by_energy_unit, p_ust_by_regional_district, p_ust_by_regional_energy_system, p_ust_by_union_energy_system, p_ust_by_energy_system_type, p_ust_total]),
                        ("p_ogr", [p_ogr_by_energy_unit, p_ogr_by_regional_district, p_ogr_by_regional_energy_system, p_ogr_by_union_energy_system, p_ogr_by_energy_system_type, p_ogr_total]),
                        ("p_rasp", [p_rasp_by_energy_unit, p_rasp_by_regional_district, p_rasp_by_regional_energy_system, p_rasp_by_union_energy_system, p_rasp_by_energy_system_type, p_rasp_total])
                    ]:
                        raw_val = values.get(key)
                        if raw_val is None:
                            continue
                        try:
                            val = raw_val if isinstance(raw_val, Decimal) else Decimal(str(raw_val).replace(",", "."))
                        except Exception:
                            continue

                        target_dicts[0][energy_unit_id][year] += val
                        target_dicts[1][regional_district_id][year] += val
                        target_dicts[2][res_id][year] += val
                        target_dicts[3][ues_id][year] += val
                        target_dicts[4][est_id][year] += val
                        target_dicts[5][year] += val

            if include_names:
                if est_id not in energy_system_type_name:
                    energy_system_type_name[est_id] = ues.energy_system_type.name if ues.energy_system_type else f"id={est_id}"
                if ues_id not in union_energy_system_name:
                    union_energy_system_name[ues_id] = ues.name or f"id={ues_id}"
                if res_id not in regional_energy_system_name:
                    regional_energy_system_name[res_id] = res.name or f"id={res_id}"
                if regional_district_id not in regional_district_name:
                    regional_district_name[regional_district_id] = rd.name or f"id={regional_district_id}"
                if energy_unit_id not in energy_unit_name:
                    energy_unit_name[energy_unit_id] = station.energy_unit.name if station.energy_unit else "не указано"

    for energy_system_type in grouped_data.values():
        for union_energy_system in energy_system_type.values():
            for regional_energy_system in union_energy_system.values():
                for regional_district in regional_energy_system.values():
                    for energy_unit in regional_district.values():
                        energy_unit.sort(key=lambda station: (
                            next((m.station_type.id for m in station.machines if m.station_type), 0),
                            station.name
                        ))

    all_stations = []
    for energy_system_type in grouped_data.values():
        for union_energy_system in energy_system_type.values():
            for regional_energy_system in union_energy_system.values():
                for regional_district in regional_energy_system.values():
                    for energy_unit in regional_district.values():
                        all_stations.extend(energy_unit)

    result = {
        "grouped_stations": grouped_data,
        "stations": all_stations,
        "aggregated_by_energy_unit": p_ust_by_energy_unit,
        "aggregated_by_regional_district": p_ust_by_regional_district,
        "aggregated_by_regional_energy_system": p_ust_by_regional_energy_system,
        "aggregated_by_union_energy_system": p_ust_by_union_energy_system,
        "aggregated_by_energy_system_type": p_ust_by_energy_system_type,
        "aggregated_total": p_ust_total,
    }

    if include_names:
        result.update({
            "energy_system_type_name": energy_system_type_name,
            "union_energy_system_name": union_energy_system_name,
            "regional_energy_system_name": regional_energy_system_name,
            "regional_district_name": regional_district_name,
            "energy_unit_name": energy_unit_name,
        })

    return result


def group_machines_by_group_and_fuel(stations):
    for station in stations:
        # ⚠️ Предполагаем, что фильтрация агрегатов по видимости уже выполнена.
        # Если ещё нет — сделай это тут:
        station.machines = [m for m in station.machines if getattr(m, "visible", True)]

        # Сортировка по номеру агрегата и дате ввода
        station.machines.sort(
            key=lambda m: (
                int(m.machine_number) if m.machine_number and str(m.machine_number).isdigit() else float('inf'),
                m.date_exploitation or float('inf')
            )
        )

        # Группировка по fuel_so
        fuel_groups = defaultdict(list)
        for machine in station.machines:
            fuel_groups[machine.fuel_so].append(machine)

        fuel_sorted_machines = []
        for fuel, fuel_machines in fuel_groups.items():
            if not fuel_machines:
                continue

            # rowspan по fuel
            fuel_machines[0].fuel_rowspan = len(fuel_machines)
            for machine in fuel_machines[1:]:
                machine.fuel_rowspan = 0

            # Внутри fuel группируем по machine_group
            group_groups = defaultdict(list)
            for machine in fuel_machines:
                group_groups[machine.machine_group].append(machine)

            for group, group_machines in group_groups.items():
                if not group_machines:
                    continue
                group_machines[0].group_rowspan = len(group_machines)
                for machine in group_machines[1:]:
                    machine.group_rowspan = 0

                fuel_sorted_machines.extend(group_machines)

        station.machines = fuel_sorted_machines

    return stations




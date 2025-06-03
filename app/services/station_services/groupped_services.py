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
    """
    Устанавливает:
    - group_rowspan: количество агрегатов с одинаковым machine_group
    - fuel_rowspan: количество агрегатов с одинаковым fuel_so
    Эти значения независимы.
    """
    if not stations:
        return stations

    is_single = not isinstance(stations, list)
    stations = [stations] if is_single else stations

    for station in stations:
        if not hasattr(station, 'machines'):
            continue

        # Фильтруем видимые агрегаты
        station.machines = [m for m in station.machines if getattr(m, "visible", True)]

        # Сортировка: по группе, топливу и номеру
        station.machines.sort(
            key=lambda m: (
                (m.machine_group or "").lower(),
                (m.fuel_so or "").lower(),
                int(m.machine_number) if m.machine_number and str(m.machine_number).isdigit() else float('inf')
            )
        )

        # --- Проставляем group_rowspan ---
        group_dict = defaultdict(list)
        for m in station.machines:
            group_key = (m.machine_group or "").strip()
            group_dict[group_key].append(m)

        for machines_in_group in group_dict.values():
            machines_in_group[0].group_rowspan = len(machines_in_group)
            for m in machines_in_group[1:]:
                m.group_rowspan = 0

        # --- Проставляем fuel_rowspan ---
        fuel_dict = defaultdict(list)
        for m in station.machines:
            fuel_key = (m.fuel_so or "").strip()
            fuel_dict[fuel_key].append(m)

        for machines_in_fuel in fuel_dict.values():
            machines_in_fuel[0].fuel_rowspan = len(machines_in_fuel)
            for m in machines_in_fuel[1:]:
                m.fuel_rowspan = 0

    return stations[0] if is_single else stations








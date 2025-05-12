from decimal import Decimal
from collections import defaultdict

from app.services.station_services.help_service import (
        maybe_round, 
        round_nested_power_dict,
    )


def group_stations_hierarchy(stations, rounding_digits):
    grouped_data = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(
                    lambda: defaultdict(list)
                )
            )
        )
    )

    # Сначала округляем powers_by_year для каждой станции
    for station in stations:
        if hasattr(station, "powers_by_year") and station.powers_by_year:
            for year, values in station.powers_by_year.items():
                if values is not None:
                    for key in ['p_ust', 'p_ogr', 'p_rasp']:
                        if key in values and values[key] is not None:
                            values[key] = maybe_round(Decimal(values[key]), rounding_digits)

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

    # Округление значений у станций
    for station in stations:
        if hasattr(station, "powers_by_year") and station.powers_by_year:
            for year, values in station.powers_by_year.items():
                if values is not None:
                    for key in ['p_ust', 'p_ogr', 'p_rasp']:
                        if key in values and values[key] is not None:
                            values[key] = maybe_round(Decimal(values[key]), rounding_digits)

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
            energy_unit_id = station.energy_unit.id if station.energy_unit else None
            res_id = res.id

            # Группируем станцию
            grouped_data[est_id][ues_id][res_id][regional_district_id][energy_unit_id].append(station)

            # Агрегация мощностей
            if hasattr(station, "powers_by_year") and station.powers_by_year:
                for year, values in station.powers_by_year.items():
                    if values is None:
                        continue

                    p_ust_value = values.get("p_ust")
                    p_ogr_value = values.get("p_ogr")
                    p_rasp_value = values.get("p_rasp")

                    if p_ust_value is not None:
                        value = Decimal(p_ust_value)
                        p_ust_by_energy_unit[energy_unit_id][year] += value
                        p_ust_by_regional_district[regional_district_id][year] += value
                        p_ust_by_regional_energy_system[res_id][year] += value
                        p_ust_by_union_energy_system[ues_id][year] += value
                        p_ust_by_energy_system_type[est_id][year] += value
                        p_ust_total[year] += value

                    if p_ogr_value is not None:
                        value = Decimal(p_ogr_value)
                        p_ogr_by_energy_unit[energy_unit_id][year] += value
                        p_ogr_by_regional_district[regional_district_id][year] += value
                        p_ogr_by_regional_energy_system[res_id][year] += value
                        p_ogr_by_union_energy_system[ues_id][year] += value
                        p_ogr_by_energy_system_type[est_id][year] += value
                        p_ogr_total[year] += value

                    if p_rasp_value is not None:
                        value = Decimal(p_rasp_value)
                        p_rasp_by_energy_unit[energy_unit_id][year] += value
                        p_rasp_by_regional_district[regional_district_id][year] += value
                        p_rasp_by_regional_energy_system[res_id][year] += value
                        p_rasp_by_union_energy_system[ues_id][year] += value
                        p_rasp_by_energy_system_type[est_id][year] += value
                        p_rasp_total[year] += value

    # Сортировка станций внутри EnergyUnit
    for energy_system_type in grouped_data.values():
        for union_energy_system in energy_system_type.values():
            for regional_energy_system in union_energy_system.values():
                for regional_district in regional_energy_system.values():
                    for energy_unit in regional_district.values():
                        energy_unit.sort(key=lambda station: (
                            station.machines[0].station_type.id if station.machines and station.machines[0].station_type else 0,
                            station.name
                        ))

    # Плоский список станций
    all_stations = []
    for energy_system_type in grouped_data.values():
        for union_energy_system in energy_system_type.values():
            for regional_energy_system in union_energy_system.values():
                for regional_district in regional_energy_system.values():
                    for energy_unit in regional_district.values():
                        all_stations.extend(energy_unit)

    return {
        "grouped_stations": grouped_data,
        "stations": all_stations,
        "aggregated_by_energy_unit": {
            "p_ust": round_nested_power_dict(p_ust_by_energy_unit, rounding_digits),
            "p_ogr": round_nested_power_dict(p_ogr_by_energy_unit, rounding_digits),
            "p_rasp": round_nested_power_dict(p_rasp_by_energy_unit, rounding_digits),
        },
        "aggregated_by_regional_district": {
            "p_ust": round_nested_power_dict(p_ust_by_regional_district, rounding_digits),
            "p_ogr": round_nested_power_dict(p_ogr_by_regional_district, rounding_digits),
            "p_rasp": round_nested_power_dict(p_rasp_by_regional_district, rounding_digits),
        },
        "aggregated_by_regional_energy_system": {
            "p_ust": round_nested_power_dict(p_ust_by_regional_energy_system, rounding_digits),
            "p_ogr": round_nested_power_dict(p_ogr_by_regional_energy_system, rounding_digits),
            "p_rasp": round_nested_power_dict(p_rasp_by_regional_energy_system, rounding_digits),
        },
        "aggregated_by_union_energy_system": {
            "p_ust": round_nested_power_dict(p_ust_by_union_energy_system, rounding_digits),
            "p_ogr": round_nested_power_dict(p_ogr_by_union_energy_system, rounding_digits),
            "p_rasp": round_nested_power_dict(p_rasp_by_union_energy_system, rounding_digits),
        },
        "aggregated_by_energy_system_type": {
            "p_ust": round_nested_power_dict(p_ust_by_energy_system_type, rounding_digits),
            "p_ogr": round_nested_power_dict(p_ogr_by_energy_system_type, rounding_digits),
            "p_rasp": round_nested_power_dict(p_rasp_by_energy_system_type, rounding_digits),
        },
        "aggregated_total": {
            "p_ust": round_nested_power_dict(p_ust_total, rounding_digits),
            "p_ogr": round_nested_power_dict(p_ogr_total, rounding_digits),
            "p_rasp": round_nested_power_dict(p_rasp_total, rounding_digits),
        },
    }


def group_machines_by_group_and_fuel(stations):

    for station in stations:
        # Сортировка агрегатов по номеру, затем по году ввода
        station.machines.sort(
            key=lambda m: (
                int(m.machine_number) if m.machine_number and str(m.machine_number).isdigit() else float('inf'),
                m.date_exploitation if m.date_exploitation else float('inf')
            )
        )

        # Группировка машин по fuel_so (топливо сначала)
        fuel_groups = defaultdict(list)
        for machine in station.machines:
            fuel_groups[machine.fuel_so].append(machine)

        # Теперь внутри каждой группы fuel_so группируем по machine_group
        fuel_sorted_machines = []
        for fuel, fuel_machines in fuel_groups.items():
            # Применяем rowspan для fuel_so
            fuel_machines[0].fuel_rowspan = len(fuel_machines)
            for machine in fuel_machines[1:]:
                machine.fuel_rowspan = 0

            # Группировка внутри fuel_so по machine_group
            group_groups = defaultdict(list)
            for machine in fuel_machines:
                group_groups[machine.machine_group].append(machine)

            # Применяем rowspan для machine_group внутри fuel_so
            for group, group_machines in group_groups.items():
                group_machines[0].group_rowspan = len(group_machines)
                for machine in group_machines[1:]:
                    machine.group_rowspan = 0

                # Добавляем в итоговый список
                fuel_sorted_machines.extend(group_machines)

        # Обновляем порядок машин в станции
        station.machines = fuel_sorted_machines

    return stations



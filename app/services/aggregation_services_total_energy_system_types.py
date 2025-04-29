from collections import defaultdict
from decimal import Decimal

from app.services.help_service import (
        round_nested_power_dict,
    )

# Агрегация по всем типам энергосистем - всего
from collections import defaultdict
from decimal import Decimal

def round_nested_power_dict(data, rounding_digits):
    """Округлить все значения в словаре."""
    if isinstance(data, dict):
        return {k: round_nested_power_dict(v, rounding_digits) for k, v in data.items()}
    elif isinstance(data, Decimal):
        return round(data, rounding_digits)
    else:
        return data

def aggregate_power_by_total_energy_system_type(pagination, rounding_digits, start_year, end_year):
    stations = pagination["stations"]

    p_ust = defaultdict(Decimal)
    p_ogr = defaultdict(Decimal)
    p_rasp = defaultdict(Decimal)

    for station in stations:
        if not station.powers_by_year:
            continue

        for year, powers in station.powers_by_year.items():
            year = int(year)
            if not (start_year <= year <= end_year):
                continue

            p_ust[year] += Decimal(powers.get("p_ust") or 0)
            p_ogr[year] += Decimal(powers.get("p_ogr") or 0)
            p_rasp[year] += Decimal(powers.get("p_rasp") or 0)

    return {
        'aggregated': {
            'p_ust': round_nested_power_dict(p_ust, rounding_digits),
            'p_ogr': round_nested_power_dict(p_ogr, rounding_digits),
            'p_rasp': round_nested_power_dict(p_rasp, rounding_digits),
        }
    }


# Агрегация по типу станции
def aggregate_total_energy_system_types_by_station_types(pagination, rounding_digits, start_year, end_year):
    stations = pagination["stations"]

    p_ust = defaultdict(lambda: defaultdict(Decimal))
    p_ogr = defaultdict(lambda: defaultdict(Decimal))
    p_rasp = defaultdict(lambda: defaultdict(Decimal))

    for station in stations:
        for machine in station.machines:

            station_type_id = None
            if hasattr(machine, "station_type") and machine.station_type:
                station_type_id = machine.station_type.id
            else:
                continue

            powers_by_year = machine.powers_by_year or {}

            for year_raw, powers in powers_by_year.items():
                year = int(year_raw)
                if not (start_year <= year <= end_year):
                    continue

                p_ust[station_type_id][year] += Decimal(powers.get("p_ust") or 0)
                p_ogr[station_type_id][year] += Decimal(powers.get("p_ogr") or 0)
                p_rasp[station_type_id][year] += Decimal(powers.get("p_rasp") or 0)

    return {
        'aggregated': {
            'p_ust': round_nested_power_dict(p_ust, rounding_digits),
            'p_ogr': round_nested_power_dict(p_ogr, rounding_digits),
            'p_rasp': round_nested_power_dict(p_rasp, rounding_digits),
        }
    }


# Агрегация по видам топлива для ТЭС
def aggregate_total_energy_system_types_by_station_types_with_fuel(pagination, rounding_digits, start_year, end_year):
    stations = pagination["stations"]

    p_ust = defaultdict(lambda: defaultdict(Decimal))
    p_ogr = defaultdict(lambda: defaultdict(Decimal))
    p_rasp = defaultdict(lambda: defaultdict(Decimal))

    for station in stations:
        
        for machine in station.machines:
            powers_by_year = machine.powers_by_year or {}

            for year_raw, powers in powers_by_year.items():
                year = int(year_raw)
                if not (start_year <= year <= end_year):
                    continue

                fuel_type_id = None
                if hasattr(machine, "machine_fuels"):
                    for mf in machine.machine_fuels:
                        if mf.year_number == year and mf.fuel and mf.fuel.fuel_type:
                            fuel_type_id = mf.fuel.fuel_type.id
                            break

                if fuel_type_id is None:
                    continue

                p_ust[fuel_type_id][year] += Decimal(powers.get("p_ust") or 0)
                p_ogr[fuel_type_id][year] += Decimal(powers.get("p_ogr") or 0)
                p_rasp[fuel_type_id][year] += Decimal(powers.get("p_rasp") or 0)

    return {
        'aggregated': {
            'p_ust': round_nested_power_dict(p_ust, rounding_digits),
            'p_ogr': round_nested_power_dict(p_ogr, rounding_digits),
            'p_rasp': round_nested_power_dict(p_rasp, rounding_digits),
        }
    }


# Агрегация по типу ТЭС
def aggregate_total_energy_system_types_by_tes_types(pagination, rounding_digits, start_year, end_year):
    stations = pagination["stations"]

    p_ust = defaultdict(lambda: defaultdict(Decimal))
    p_ogr = defaultdict(lambda: defaultdict(Decimal))
    p_rasp = defaultdict(lambda: defaultdict(Decimal))

    for station in stations:
       
        for machine in station.machines:
            for tes_type_link in machine.machine_tes_types:
                tes_type_id = tes_type_link.id_tes_type
                for year, powers in (machine.powers_by_year or {}).items():
                    if start_year <= year <= end_year and tes_type_link.year_number == year:
                        p_ust[tes_type_id][year] += Decimal(powers.get("p_ust", 0) or 0)
                        p_ogr[tes_type_id][year] += Decimal(powers.get("p_ogr", 0) or 0)
                        p_rasp[tes_type_id][year] += Decimal(powers.get("p_rasp", 0) or 0)

    return {
        'aggregated': {
            'p_ust': round_nested_power_dict(p_ust, rounding_digits),
            'p_ogr': round_nested_power_dict(p_ogr, rounding_digits),
            'p_rasp': round_nested_power_dict(p_rasp, rounding_digits),
        }
    }


# Агрегация по видам топлива по типу ТЭС
def aggregate_total_energy_system_types_by_tes_types_with_fuel(pagination, rounding_digits, start_year, end_year):
    stations = pagination["stations"]

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for station in stations:

        for machine in station.machines:
            powers_by_year = machine.powers_by_year or {}

            for year_raw, powers in powers_by_year.items():
                year = int(year_raw)
                if not (start_year <= year <= end_year):
                    continue

                tes_type_id = None
                if hasattr(machine, "machine_tes_types"):
                    for mtt in machine.machine_tes_types:
                        if mtt.year_number == year and mtt.tes_type:
                            tes_type_id = mtt.tes_type.id
                            break

                fuel_type_id = None
                if hasattr(machine, "machine_fuels"):
                    for mf in machine.machine_fuels:
                        if mf.year_number == year and mf.fuel and mf.fuel.fuel_type:
                            fuel_type_id = mf.fuel.fuel_type.id
                            break

                if tes_type_id is None or fuel_type_id is None:
                    continue

                p_ust[tes_type_id][fuel_type_id][year] += Decimal(powers.get("p_ust") or 0)
                p_ogr[tes_type_id][fuel_type_id][year] += Decimal(powers.get("p_ogr") or 0)
                p_rasp[tes_type_id][fuel_type_id][year] += Decimal(powers.get("p_rasp") or 0)

    return {
        'aggregated': {
            'p_ust': round_nested_power_dict(p_ust, rounding_digits),
            'p_ogr': round_nested_power_dict(p_ogr, rounding_digits),
            'p_rasp': round_nested_power_dict(p_rasp, rounding_digits),
        }
    }


# Агрегация по типу машин ТЭС
def aggregate_total_energy_system_types_by_tes_machine_types(pagination, rounding_digits, start_year, end_year):
    stations = pagination["stations"]

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for station in stations:

        for machine in station.machines:
            powers_by_year = machine.powers_by_year or {}

            for year_raw, powers in powers_by_year.items():
                year = int(year_raw)
                if not (start_year <= year <= end_year):
                    continue

                tes_type_id = None
                if hasattr(machine, "machine_tes_types"):
                    for mtt in machine.machine_tes_types:
                        if mtt.year_number == year and mtt.tes_type:
                            tes_type_id = mtt.tes_type.id
                            break

                machine_type_id = None
                if hasattr(machine, "tes_machine_type") and machine.tes_machine_type:
                    machine_type_id = machine.tes_machine_type.id

                if tes_type_id is None or machine_type_id is None:
                    continue

                p_ust[tes_type_id][machine_type_id][year] += Decimal(powers.get("p_ust") or 0)
                p_ogr[tes_type_id][machine_type_id][year] += Decimal(powers.get("p_ogr") or 0)
                p_rasp[tes_type_id][machine_type_id][year] += Decimal(powers.get("p_rasp") or 0)

    return {
        'aggregated': {
            'p_ust': round_nested_power_dict(p_ust, rounding_digits),
            'p_ogr': round_nested_power_dict(p_ogr, rounding_digits),
            'p_rasp': round_nested_power_dict(p_rasp, rounding_digits),
        }
    }


# Пример реализации функции агрегирования по типу топлива и типу машины ТЭС
def aggregate_total_energy_system_types_by_tes_machine_types_with_fuel(pagination, rounding_digits, start_year, end_year):
    stations = pagination["stations"]

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for station in stations:

        for machine in station.machines:
            powers_by_year = machine.powers_by_year or {}

            for year_raw, powers in powers_by_year.items():
                year = int(year_raw)
                if not (start_year <= year <= end_year):
                    continue

                tes_type_id = None
                if hasattr(machine, "machine_tes_types"):
                    for mtt in machine.machine_tes_types:
                        if mtt.year_number == year and mtt.tes_type:
                            tes_type_id = mtt.tes_type.id
                            break

                tes_machine_type_id = None
                if hasattr(machine, "tes_machine_type") and machine.tes_machine_type:
                    tes_machine_type_id = machine.tes_machine_type.id

                fuel_type_id = None
                if hasattr(machine, "machine_fuels"):
                    for mf in machine.machine_fuels:
                        if mf.year_number == year and mf.fuel and mf.fuel.fuel_type:
                            fuel_type_id = mf.fuel.fuel_type.id
                            break

                if tes_type_id is None or tes_machine_type_id is None or fuel_type_id is None:
                    continue

                p_ust[tes_type_id][tes_machine_type_id][fuel_type_id][year] += Decimal(powers.get("p_ust") or 0)
                p_ogr[tes_type_id][tes_machine_type_id][fuel_type_id][year] += Decimal(powers.get("p_ogr") or 0)
                p_rasp[tes_type_id][tes_machine_type_id][fuel_type_id][year] += Decimal(powers.get("p_rasp") or 0)

    return {
        'aggregated': {
            'p_ust': round_nested_power_dict(p_ust, rounding_digits),
            'p_ogr': round_nested_power_dict(p_ogr, rounding_digits),
            'p_rasp': round_nested_power_dict(p_rasp, rounding_digits),
        }
    }





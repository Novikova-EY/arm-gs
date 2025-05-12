from collections import defaultdict
from decimal import Decimal

from app.services.station_services.help_service import (
        round_nested_power_dict,
    )

# Агрегация по энергоузлам - всего
def aggregate_power_by_energy_unit(pagination, rounding_digits, start_year, end_year):
    aggregated_data = pagination["aggregated_by_energy_unit"]

    p_ust_source = aggregated_data.get("p_ust", {})
    p_ogr_source = aggregated_data.get("p_ogr", {})
    p_rasp_source = aggregated_data.get("p_rasp", {})

    p_ust = defaultdict(lambda: defaultdict(Decimal))
    p_ogr = defaultdict(lambda: defaultdict(Decimal))
    p_rasp = defaultdict(lambda: defaultdict(Decimal))

    for energy_unit_id, years_data in p_ust_source.items():
        for year, value in years_data.items():
            if start_year <= year <= end_year:
                p_ust[energy_unit_id][year] = value or Decimal(0)

    for energy_unit_id, years_data in p_ogr_source.items():
        for year, value in years_data.items():
            if start_year <= year <= end_year:
                p_ogr[energy_unit_id][year] = value or Decimal(0)

    for energy_unit_id, years_data in p_rasp_source.items():
        for year, value in years_data.items():
            if start_year <= year <= end_year:
                p_rasp[energy_unit_id][year] = value or Decimal(0)

    return {
        'aggregated': {
            'p_ust': round_nested_power_dict(p_ust, rounding_digits),
            'p_ogr': round_nested_power_dict(p_ogr, rounding_digits),
            'p_rasp': round_nested_power_dict(p_rasp, rounding_digits),
        }
    }


# Агрегация по типу станции
def aggregate_energy_units_by_station_types(pagination, rounding_digits, start_year, end_year):
    stations = pagination["stations"]

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for station in stations:
        energy_unit_id = station.id_energy_unit

        for machine in station.machines:
            station_type_id = machine.station_type.id if hasattr(machine, "station_type") and machine.station_type else None
            if station_type_id is None:
                continue

            powers_by_year = machine.powers_by_year or {}

            for year, powers in powers_by_year.items():
                if start_year <= year <= end_year:
                    p_ust[energy_unit_id][station_type_id][year] += Decimal(powers.get("p_ust") or 0)
                    p_ogr[energy_unit_id][station_type_id][year] += Decimal(powers.get("p_ogr") or 0)
                    p_rasp[energy_unit_id][station_type_id][year] += Decimal(powers.get("p_rasp") or 0)

    return {
        'aggregated': {
            'p_ust': round_nested_power_dict(p_ust, rounding_digits),
            'p_ogr': round_nested_power_dict(p_ogr, rounding_digits),
            'p_rasp': round_nested_power_dict(p_rasp, rounding_digits),
        }
    }


# Агрегация для ТЭС и по типу топлива
def aggregate_energy_units_by_station_types_with_fuel(pagination, rounding_digits, start_year, end_year):
    stations = pagination["stations"]

    def decimal_dict():
        return defaultdict(Decimal)

    p_ust = defaultdict(lambda: defaultdict(decimal_dict))
    p_ogr = defaultdict(lambda: defaultdict(decimal_dict))
    p_rasp = defaultdict(lambda: defaultdict(decimal_dict))

    for station in stations:
        energy_unit_id = station.id_energy_unit
        for machine in station.machines:
            powers_by_year = machine.powers_by_year or {}

            for year_raw, powers in powers_by_year.items():
                year = int(year_raw)
                if not (start_year <= year <= end_year):
                    continue

                # ==== Строгое определение топлива ====
                fuel_type_id = None
                if hasattr(machine, "machine_fuels"):
                    for mf in machine.machine_fuels:
                        if mf.year_number == year and mf.fuel and mf.fuel.fuel_type:
                            fuel_type_id = mf.fuel.fuel_type.id
                            break

                if fuel_type_id is None:
                    continue

                # ==== Агрегация ====
                p_ust[energy_unit_id][fuel_type_id][year] += Decimal(powers.get("p_ust") or 0)
                p_ogr[energy_unit_id][fuel_type_id][year] += Decimal(powers.get("p_ogr") or 0)
                p_rasp[energy_unit_id][fuel_type_id][year] += Decimal(powers.get("p_rasp") or 0)

    return {
        'aggregated': {
            'p_ust': round_nested_power_dict(p_ust, rounding_digits),
            'p_ogr': round_nested_power_dict(p_ogr, rounding_digits),
            'p_rasp': round_nested_power_dict(p_rasp, rounding_digits),
        }
    }


# Агрегация по типу ТЭС
def aggregate_energy_units_by_tes_types(pagination, rounding_digits, start_year, end_year):
    stations = pagination["stations"]

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for station in stations:
        energy_unit_id = station.id_energy_unit

        for machine in station.machines:
            for tes_type_link in machine.machine_tes_types:
                tes_type_id = tes_type_link.id_tes_type
                for year, powers in (machine.powers_by_year or {}).items():
                    if start_year <= year <= end_year and tes_type_link.year_number == year:
                        p_ust[energy_unit_id][tes_type_id][year] += Decimal(powers.get("p_ust", 0) or 0)
                        p_ogr[energy_unit_id][tes_type_id][year] += Decimal(powers.get("p_ogr", 0) or 0)
                        p_rasp[energy_unit_id][tes_type_id][year] += Decimal(powers.get("p_rasp", 0) or 0)

    return {
        'aggregated': {
            'p_ust': round_nested_power_dict(p_ust, rounding_digits),
            'p_ogr': round_nested_power_dict(p_ogr, rounding_digits),
            'p_rasp': round_nested_power_dict(p_rasp, rounding_digits),
        }
    }


# Агрегация по типу ТЭС и по типу топлива
def aggregate_energy_units_by_tes_types_with_fuel(pagination, rounding_digits, start_year, end_year):
    stations = pagination["stations"]

    def decimal_dict():
        return defaultdict(Decimal)

    def fuel_dict():
        return defaultdict(decimal_dict)

    def tes_type_dict():
        return defaultdict(fuel_dict)

    p_ust = defaultdict(tes_type_dict)
    p_ogr = defaultdict(tes_type_dict)
    p_rasp = defaultdict(tes_type_dict)

    for station in stations:
        energy_unit_id = station.id_energy_unit
        for machine in station.machines:
            powers_by_year = machine.powers_by_year or {}

            for year_raw, powers in powers_by_year.items():
                year = int(year_raw)  # обязательно приведение к int!
                if not (start_year <= year <= end_year):
                    continue

                # ==== Строгое определение типа ТЭС ====
                tes_type_id = None
                if hasattr(machine, "machine_tes_types"):
                    for mtt in machine.machine_tes_types:
                        if mtt.year_number == year and mtt.tes_type:
                            tes_type_id = mtt.tes_type.id
                            break

                # ==== Строгое определение топлива ====
                fuel_type_id = None
                if hasattr(machine, "machine_fuels"):
                    for mf in machine.machine_fuels:
                        if mf.year_number == year and mf.fuel and mf.fuel.fuel_type:
                            fuel_type_id = mf.fuel.fuel_type.id
                            break

                # Если нет типа ТЭС или топлива на нужный год — ПРОПУСКАЕМ эту запись
                if tes_type_id is None or fuel_type_id is None:
                    continue

                # ==== Агрегация ====
                p_ust[energy_unit_id][tes_type_id][fuel_type_id][year] += Decimal(powers.get("p_ust") or 0)
                p_ogr[energy_unit_id][tes_type_id][fuel_type_id][year] += Decimal(powers.get("p_ogr") or 0)
                p_rasp[energy_unit_id][tes_type_id][fuel_type_id][year] += Decimal(powers.get("p_rasp") or 0)

    return {
        'aggregated': {
            'p_ust': round_nested_power_dict(p_ust, rounding_digits),
            'p_ogr': round_nested_power_dict(p_ogr, rounding_digits),
            'p_rasp': round_nested_power_dict(p_rasp, rounding_digits),
        }
    }


# Агрегация по типу машин ТЭС
def aggregate_energy_units_by_tes_machine_types(pagination, rounding_digits, start_year, end_year):
    stations = pagination["stations"]

    def decimal_dict():
        return defaultdict(Decimal)

    def machine_type_dict():
        return defaultdict(decimal_dict)

    def tes_type_dict():
        return defaultdict(machine_type_dict)

    p_ust = defaultdict(tes_type_dict)
    p_ogr = defaultdict(tes_type_dict)
    p_rasp = defaultdict(tes_type_dict)

    for station in stations:
        energy_unit_id = station.id_energy_unit
        for machine in station.machines:
            powers_by_year = machine.powers_by_year or {}

            for year_raw, powers in powers_by_year.items():
                year = int(year_raw)
                if not (start_year <= year <= end_year):
                    continue

                # ==== Строгое определение типа ТЭС ====
                tes_type_id = None
                if hasattr(machine, "machine_tes_types"):
                    for mtt in machine.machine_tes_types:
                        if mtt.year_number == year and mtt.tes_type:
                            tes_type_id = mtt.tes_type.id
                            break

                # ==== Строгое определение типа агрегата ====
                machine_type_id = None
                if hasattr(machine, "tes_machine_type") and machine.tes_machine_type:
                    machine_type_id = machine.tes_machine_type.id

                # ==== Проверка полноты связей ====
                if tes_type_id is None or machine_type_id is None:
                    continue

                # ==== Агрегация ====
                p_ust[energy_unit_id][tes_type_id][machine_type_id][year] += Decimal(powers.get("p_ust") or 0)
                p_ogr[energy_unit_id][tes_type_id][machine_type_id][year] += Decimal(powers.get("p_ogr") or 0)
                p_rasp[energy_unit_id][tes_type_id][machine_type_id][year] += Decimal(powers.get("p_rasp") or 0)

    return {
        'aggregated': {
            'p_ust': round_nested_power_dict(p_ust, rounding_digits),
            'p_ogr': round_nested_power_dict(p_ogr, rounding_digits),
            'p_rasp': round_nested_power_dict(p_rasp, rounding_digits),
        }
    }


# Агрегация по типу машины ТЭС и по типу топлива
def aggregate_energy_units_by_tes_machine_types_with_fuel(pagination, rounding_digits, start_year, end_year):
    stations = pagination["stations"]

    def decimal_dict():
        return defaultdict(Decimal)

    def fuel_dict():
        return defaultdict(decimal_dict)

    def machine_type_dict():
        return defaultdict(fuel_dict)

    def tes_type_dict():
        return defaultdict(machine_type_dict)

    p_ust = defaultdict(tes_type_dict)
    p_ogr = defaultdict(tes_type_dict)
    p_rasp = defaultdict(tes_type_dict)

    for station in stations:
        energy_unit_id = station.id_energy_unit
        for machine in station.machines:
            powers_by_year = machine.powers_by_year or {}

            for year_raw, powers in powers_by_year.items():
                year = int(year_raw)
                if not (start_year <= year <= end_year):
                    continue

                # ==== Строгое определение типа ТЭС ====
                tes_type_id = None
                if hasattr(machine, "machine_tes_types"):
                    for mtt in machine.machine_tes_types:
                        if mtt.year_number == year and mtt.tes_type:
                            tes_type_id = mtt.tes_type.id
                            break

                # ==== Строгое определение типа агрегата ====
                tes_machine_type_id = None
                if hasattr(machine, "tes_machine_type") and machine.tes_machine_type:
                    tes_machine_type_id = machine.tes_machine_type.id

                # ==== Строгое определение топлива ====
                fuel_type_id = None
                if hasattr(machine, "machine_fuels"):
                    for mf in machine.machine_fuels:
                        if mf.year_number == year and mf.fuel and mf.fuel.fuel_type:
                            fuel_type_id = mf.fuel.fuel_type.id
                            break

                # ==== Проверка полноты связей ====
                if tes_type_id is None or tes_machine_type_id is None or fuel_type_id is None:
                    continue

                # ==== Агрегация ====
                p_ust[energy_unit_id][tes_type_id][tes_machine_type_id][fuel_type_id][year] += Decimal(powers.get("p_ust") or 0)
                p_ogr[energy_unit_id][tes_type_id][tes_machine_type_id][fuel_type_id][year] += Decimal(powers.get("p_ogr") or 0)
                p_rasp[energy_unit_id][tes_type_id][tes_machine_type_id][fuel_type_id][year] += Decimal(powers.get("p_rasp") or 0)

    return {
        'aggregated': {
            'p_ust': round_nested_power_dict(p_ust, rounding_digits),
            'p_ogr': round_nested_power_dict(p_ogr, rounding_digits),
            'p_rasp': round_nested_power_dict(p_rasp, rounding_digits),
        }
    }





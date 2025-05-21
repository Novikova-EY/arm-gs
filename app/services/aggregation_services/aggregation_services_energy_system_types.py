from collections import defaultdict
from decimal import Decimal

# Агрегация по типам энергосистемам - всего
def aggregate_power_by_energy_system_type(pagination, rounding_digits, start_year, end_year):
    aggregated_data = pagination["aggregated_by_energy_system_type"]

    p_ust_source = aggregated_data.get("p_ust", {})
    p_ogr_source = aggregated_data.get("p_ogr", {})
    p_rasp_source = aggregated_data.get("p_rasp", {})

    p_ust = defaultdict(lambda: defaultdict(Decimal))
    p_ogr = defaultdict(lambda: defaultdict(Decimal))
    p_rasp = defaultdict(lambda: defaultdict(Decimal))

    for energy_system_type_id, years_data in p_ust_source.items():
        for year, value in years_data.items():
            if start_year <= year <= end_year:
                p_ust[energy_system_type_id][year] = value or Decimal(0)

    for energy_system_type_id, years_data in p_ogr_source.items():
        for year, value in years_data.items():
            if start_year <= year <= end_year:
                p_ogr[energy_system_type_id][year] = value or Decimal(0)

    for energy_system_type_id, years_data in p_rasp_source.items():
        for year, value in years_data.items():
            if start_year <= year <= end_year:
                p_rasp[energy_system_type_id][year] = value or Decimal(0)

    return {
        'aggregated': {
            'p_ust': p_ust,
            'p_ogr': p_ogr,
            'p_rasp': p_rasp,
        }
    }

# Агрегация по типу станции
def aggregate_energy_system_types_by_station_types(pagination, rounding_digits, start_year, end_year):
    stations = pagination["stations"]

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for station in stations:
        res = (
            station.regional_district.regional_energy_systems[0]
            if station.regional_district and station.regional_district.regional_energy_systems
            else None
        )

        energy_system_type_id = res.union_energy_system.id_energy_system_type if res and res.union_energy_system else None

        if energy_system_type_id is None:
            continue

        for machine in station.machines:
            # --- Строгое определение типа станции ---
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

                p_ust[energy_system_type_id][station_type_id][year] += Decimal(powers.get("p_ust") or 0)
                p_ogr[energy_system_type_id][station_type_id][year] += Decimal(powers.get("p_ogr") or 0)
                p_rasp[energy_system_type_id][station_type_id][year] += Decimal(powers.get("p_rasp") or 0)

    return {
        'aggregated': {
            'p_ust': p_ust,
            'p_ogr': p_ogr,
            'p_rasp': p_rasp,
        }
    }


# Агрегация по видам топлива для ТЭС
def aggregate_energy_system_types_by_station_types_with_fuel(pagination, rounding_digits, start_year, end_year):
    stations = pagination["stations"]

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for station in stations:
        res = (
            station.regional_district.regional_energy_systems[0]
            if station.regional_district and station.regional_district.regional_energy_systems
            else None
        )

        energy_system_type_id = res.union_energy_system.id_energy_system_type if res and res.union_energy_system else None

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
                p_ust[energy_system_type_id][fuel_type_id][year] += Decimal(powers.get("p_ust") or 0)
                p_ogr[energy_system_type_id][fuel_type_id][year] += Decimal(powers.get("p_ogr") or 0)
                p_rasp[energy_system_type_id][fuel_type_id][year] += Decimal(powers.get("p_rasp") or 0)

    return {
        'aggregated': {
            'p_ust': p_ust,
            'p_ogr': p_ogr,
            'p_rasp': p_rasp,
        }
    }


# Агрегация по типу ТЭС
def aggregate_energy_system_types_by_tes_types(pagination, rounding_digits, start_year, end_year):
    stations = pagination["stations"]

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for station in stations:
        res = (
            station.regional_district.regional_energy_systems[0]
            if station.regional_district and station.regional_district.regional_energy_systems
            else None
        )

        energy_system_type_id = res.union_energy_system.id_energy_system_type if res and res.union_energy_system else None

        for machine in station.machines:
            for tes_type_link in machine.machine_tes_types:
                tes_type_id = tes_type_link.id_tes_type
                for year, powers in (machine.powers_by_year or {}).items():
                    if start_year <= year <= end_year and tes_type_link.year_number == year:
                        p_ust[energy_system_type_id][tes_type_id][year] += Decimal(powers.get("p_ust", 0) or 0)
                        p_ogr[energy_system_type_id][tes_type_id][year] += Decimal(powers.get("p_ogr", 0) or 0)
                        p_rasp[energy_system_type_id][tes_type_id][year] += Decimal(powers.get("p_rasp", 0) or 0)

    return {
        'aggregated': {
            'p_ust': p_ust,
            'p_ogr': p_ogr,
            'p_rasp': p_rasp,
        }
    }


# Агрегация по видам топлива по типу ТЭС
def aggregate_energy_system_types_by_tes_types_with_fuel(pagination, rounding_digits, start_year, end_year):
    stations = pagination["stations"]

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for station in stations:
        res = (
            station.regional_district.regional_energy_systems[0]
            if station.regional_district and station.regional_district.regional_energy_systems
            else None
        )

        energy_system_type_id = res.union_energy_system.id_energy_system_type if res and res.union_energy_system else None

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

                p_ust[energy_system_type_id][tes_type_id][fuel_type_id][year] += Decimal(powers.get("p_ust") or 0)
                p_ogr[energy_system_type_id][tes_type_id][fuel_type_id][year] += Decimal(powers.get("p_ogr") or 0)
                p_rasp[energy_system_type_id][tes_type_id][fuel_type_id][year] += Decimal(powers.get("p_rasp") or 0)

    return {
        'aggregated': {
            'p_ust': p_ust,
            'p_ogr': p_ogr,
            'p_rasp': p_rasp,
        }
    }


# Агрегация по типу машин ТЭС
def aggregate_energy_system_types_by_tes_machine_types(pagination, rounding_digits, start_year, end_year):
    stations = pagination["stations"]

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for station in stations:
        res = (
            station.regional_district.regional_energy_systems[0]
            if station.regional_district and station.regional_district.regional_energy_systems
            else None
        )

        energy_system_type_id = res.union_energy_system.id_energy_system_type if res and res.union_energy_system else None

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
                p_ust[energy_system_type_id][tes_type_id][machine_type_id][year] += Decimal(powers.get("p_ust") or 0)
                p_ogr[energy_system_type_id][tes_type_id][machine_type_id][year] += Decimal(powers.get("p_ogr") or 0)
                p_rasp[energy_system_type_id][tes_type_id][machine_type_id][year] += Decimal(powers.get("p_rasp") or 0)

    return {
        'aggregated': {
            'p_ust': p_ust,
            'p_ogr': p_ogr,
            'p_rasp': p_rasp,
        }
    }


# Пример реализации функции агрегирования по типу топлива и типу машины ТЭС
def aggregate_energy_system_types_by_tes_machine_types_with_fuel(pagination, rounding_digits, start_year, end_year):
    stations = pagination["stations"]

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))

    for station in stations:
        res = (
            station.regional_district.regional_energy_systems[0]
            if station.regional_district and station.regional_district.regional_energy_systems
            else None
        )

        energy_system_type_id = res.union_energy_system.id_energy_system_type if res and res.union_energy_system else None

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
                p_ust[energy_system_type_id][tes_type_id][tes_machine_type_id][fuel_type_id][year] += Decimal(powers.get("p_ust") or 0)
                p_ogr[energy_system_type_id][tes_type_id][tes_machine_type_id][fuel_type_id][year] += Decimal(powers.get("p_ogr") or 0)
                p_rasp[energy_system_type_id][tes_type_id][tes_machine_type_id][fuel_type_id][year] += Decimal(powers.get("p_rasp") or 0)

    return {
        'aggregated': {
            'p_ust': p_ust,
            'p_ogr': p_ogr,
            'p_rasp': p_rasp,
        }
    }





from collections import defaultdict
from decimal import Decimal


def aggregate_changes_by_energy_units(rows):
    p_ust = defaultdict(lambda: defaultdict(Decimal))

    for row in rows:
        eu = row.energy_unit_id
        year = row.year
    
        p_ust[eu][year] += row.p_ust or Decimal(0)

    return {"aggregated": {"p_ust": p_ust}}


def aggregate_changes_energy_units_by_station_types(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for row in rows:
        eu = row.energy_unit_id
        station_type = row.station_type_id
        year = row.year

        p_ust[eu][station_type][year] += row.p_ust or Decimal(0)

    return {"aggregated": {"p_ust": p_ust}}


def aggregate_changes_energy_units_by_station_types_with_fuel(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for row in rows:
        eu = row.energy_unit_id
        station_type = row.station_type_id
        fuel = row.fuel_type_id
        year = row.year

        p_ust[eu][station_type][fuel][year] += row.p_ust or Decimal(0)

    return {"aggregated": {"p_ust": p_ust}}


def aggregate_changes_energy_units_by_tes_types(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for row in rows:
        eu = row.energy_unit_id
        tes_type = row.tes_type_id
        year = row.year

        p_ust[eu][tes_type][year] += row.p_ust or Decimal(0)

    return {"aggregated": {"p_ust": p_ust}}


def aggregate_changes_energy_units_by_tes_types_with_fuel(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for row in rows:
        eu = row.energy_unit_id
        tes_type = row.tes_type_id
        fuel = row.fuel_type_id
        year = row.year

        p_ust[eu][tes_type][fuel][year] += row.p_ust or Decimal(0)

    return {"aggregated": {"p_ust": p_ust}}


def aggregate_changes_energy_units_by_tes_machine_types(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for row in rows:
        eu = row.energy_unit_id
        tes_type = row.tes_type_id
        tes_machine_type = row.tes_machine_type_id
        year = row.year

        p_ust[eu][tes_type][tes_machine_type][year] += row.p_ust or Decimal(0)

    return {"aggregated": {"p_ust": p_ust}}


def aggregate_changes_energy_units_by_tes_machine_types_with_fuel(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))

    for row in rows:
        eu = row.energy_unit_id
        tes_type = row.tes_type_id
        tes_machine_type = row.tes_machine_type_id
        fuel_type = row.fuel_type_id
        year = row.year

        p_ust[eu][tes_type][tes_machine_type][fuel_type][year] += row.p_ust or Decimal(0)

    return {"aggregated": {"p_ust": p_ust}}

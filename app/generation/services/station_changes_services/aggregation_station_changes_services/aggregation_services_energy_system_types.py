from collections import defaultdict
from decimal import Decimal


def aggregate_changes_by_energy_system_types(rows):
    p_ust = defaultdict(lambda: defaultdict(Decimal))

    for row in rows:
        est = row.energy_system_type_id
        year = row.year
    
        p_ust[est][year] += row.p_ust or Decimal(0)

    return {"aggregated": {"p_ust": p_ust}}


def aggregate_changes_energy_system_types_by_station_types(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for row in rows:
        est = row.energy_system_type_id
        station_type = row.station_type_id
        year = row.year

        p_ust[est][station_type][year] += row.p_ust or Decimal(0)

    return {"aggregated": {"p_ust": p_ust}}


def aggregate_changes_energy_system_types_by_station_types_with_fuel(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for row in rows:
        est = row.energy_system_type_id
        station_type = row.station_type_id
        fuel = row.fuel_type_id
        year = row.year

        p_ust[est][station_type][fuel][year] += row.p_ust or Decimal(0)

    return {"aggregated": {"p_ust": p_ust}}


def aggregate_changes_energy_system_types_by_tes_types(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for row in rows:
        est = row.energy_system_type_id
        tes_type = row.tes_type_id
        year = row.year

        p_ust[est][tes_type][year] += row.p_ust or Decimal(0)

    return {"aggregated": {"p_ust": p_ust}}


def aggregate_changes_energy_system_types_by_tes_types_with_fuel(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for row in rows:
        est = row.energy_system_type_id
        tes_type = row.tes_type_id
        fuel = row.fuel_type_id
        year = row.year

        p_ust[est][tes_type][fuel][year] += row.p_ust or Decimal(0)

    return {"aggregated": {"p_ust": p_ust}}


def aggregate_changes_energy_system_types_by_tes_machine_types(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for row in rows:
        est = row.energy_system_type_id
        tes_type = row.tes_type_id
        tes_machine_type = row.tes_machine_type_id
        year = row.year

        p_ust[est][tes_type][tes_machine_type][year] += row.p_ust or Decimal(0)

    return {"aggregated": {"p_ust": p_ust}}


def aggregate_changes_energy_system_types_by_tes_machine_types_with_fuel(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))

    for row in rows:
        est = row.energy_system_type_id
        tes_type = row.tes_type_id
        tes_machine_type = row.tes_machine_type_id
        fuel_type = row.fuel_type_id
        year = row.year

        p_ust[est][tes_type][tes_machine_type][fuel_type][year] += row.p_ust or Decimal(0)

    return {"aggregated": {"p_ust": p_ust}}

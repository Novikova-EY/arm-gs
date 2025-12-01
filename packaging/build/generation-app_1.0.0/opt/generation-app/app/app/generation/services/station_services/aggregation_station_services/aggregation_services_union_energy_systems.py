from collections import defaultdict
from decimal import Decimal


def aggregate_power_by_union_energy_systems(rows):
    p_ust = defaultdict(lambda: defaultdict(Decimal))
    p_ogr = defaultdict(lambda: defaultdict(Decimal))
    p_rasp = defaultdict(lambda: defaultdict(Decimal))

    for row in rows:
        ues = row.union_energy_system_id
        year = row.year
    
        p_ust[ues][year] += row.p_ust or Decimal(0)
        p_ogr[ues][year] += row.p_ogr or Decimal(0)
        p_rasp[ues][year] += row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


def aggregate_union_energy_systems_by_station_types(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for row in rows:
        ues = row.union_energy_system_id
        station_type = row.station_type_id
        year = row.year

        p_ust[ues][station_type][year] += row.p_ust or Decimal(0)
        p_ogr[ues][station_type][year] += row.p_ogr or Decimal(0)
        p_rasp[ues][station_type][year] += row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


def aggregate_union_energy_systems_by_station_types_with_fuel(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for row in rows:
        ues = row.union_energy_system_id
        station_type = row.station_type_id
        fuel = row.fuel_type_id
        year = row.year

        p_ust[ues][station_type][fuel][year] += row.p_ust or Decimal(0)
        p_ogr[ues][station_type][fuel][year] += row.p_ogr or Decimal(0)
        p_rasp[ues][station_type][fuel][year] += row.p_ogr or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


def aggregate_union_energy_systems_by_tes_types(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for row in rows:
        ues = row.union_energy_system_id
        tes_type = row.tes_type_id
        year = row.year

        p_ust[ues][tes_type][year] += row.p_ust or Decimal(0)
        p_ogr[ues][tes_type][year] += row.p_ogr or Decimal(0)
        p_rasp[ues][tes_type][year] += row.p_ogr or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


def aggregate_union_energy_systems_by_tes_types_with_fuel(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for row in rows:
        ues = row.union_energy_system_id
        tes_type = row.tes_type_id
        fuel = row.fuel_type_id
        year = row.year

        p_ust[ues][tes_type][fuel][year] += row.p_ust or Decimal(0)
        p_ogr[ues][tes_type][fuel][year] += row.p_ogr or Decimal(0)
        p_rasp[ues][tes_type][fuel][year] += row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


def aggregate_union_energy_systems_by_tes_machine_types(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for row in rows:
        ues = row.union_energy_system_id
        tes_type = row.tes_type_id
        tes_machine_type = row.tes_machine_type_id
        year = row.year

        p_ust[ues][tes_type][tes_machine_type][year] += row.p_ust or Decimal(0)
        p_ogr[ues][tes_type][tes_machine_type][year] += row.p_ogr or Decimal(0)
        p_rasp[ues][tes_type][tes_machine_type][year] += row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


def aggregate_union_energy_systems_by_tes_machine_types_with_fuel(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))

    for row in rows:
        ues = row.union_energy_system_id
        tes_type = row.tes_type_id
        tes_machine_type = row.tes_machine_type_id
        fuel_type = row.fuel_type_id
        year = row.year

        p_ust[ues][tes_type][tes_machine_type][fuel_type][year] += row.p_ust or Decimal(0)
        p_ogr[ues][tes_type][tes_machine_type][fuel_type][year] += row.p_ogr or Decimal(0)
        p_rasp[ues][tes_type][tes_machine_type][fuel_type][year] += row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}

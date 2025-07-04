from collections import defaultdict
from decimal import Decimal


def aggregate_power_by_regional_districts(rows):
    p_ust = defaultdict(lambda: defaultdict(Decimal))
    p_ogr = defaultdict(lambda: defaultdict(Decimal))
    p_rasp = defaultdict(lambda: defaultdict(Decimal))

    for row in rows:
        rd = row.regional_district_id
        year = row.year
    
        p_ust[rd][year] += row.p_ust or Decimal(0)
        p_ogr[rd][year] += row.p_ogr or Decimal(0)
        p_rasp[rd][year] += row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


def aggregate_regional_districts_by_station_types(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for row in rows:
        rd = row.regional_district_id
        station_type = row.station_type_id
        year = row.year

        p_ust[rd][station_type][year] += row.p_ust or Decimal(0)
        p_ogr[rd][station_type][year] += row.p_ogr or Decimal(0)
        p_rasp[rd][station_type][year] += row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


def aggregate_regional_districts_by_station_types_with_fuel(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for row in rows:
        rd = row.regional_district_id
        station_type = row.station_type_id
        fuel = row.fuel_type_id
        year = row.year

        p_ust[rd][station_type][fuel][year] += row.p_ust or Decimal(0)
        p_ogr[rd][station_type][fuel][year] += row.p_ogr or Decimal(0)
        p_rasp[rd][station_type][fuel][year] += row.p_ogr or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


def aggregate_regional_districts_by_tes_types(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for row in rows:
        rd = row.regional_district_id
        tes_type = row.tes_type_id
        year = row.year

        p_ust[rd][tes_type][year] += row.p_ust or Decimal(0)
        p_ogr[rd][tes_type][year] += row.p_ogr or Decimal(0)
        p_rasp[rd][tes_type][year] += row.p_ogr or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


def aggregate_regional_districts_by_tes_types_with_fuel(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for row in rows:
        rd = row.regional_district_id
        tes_type = row.tes_type_id
        fuel = row.fuel_type_id
        year = row.year

        p_ust[rd][tes_type][fuel][year] += row.p_ust or Decimal(0)
        p_ogr[rd][tes_type][fuel][year] += row.p_ogr or Decimal(0)
        p_rasp[rd][tes_type][fuel][year] += row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


def aggregate_regional_districts_by_tes_machine_types(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for row in rows:
        rd = row.regional_district_id
        tes_type = row.tes_type_id
        tes_machine_type = row.tes_machine_type_id
        year = row.year

        p_ust[rd][tes_type][tes_machine_type][year] += row.p_ust or Decimal(0)
        p_ogr[rd][tes_type][tes_machine_type][year] += row.p_ogr or Decimal(0)
        p_rasp[rd][tes_type][tes_machine_type][year] += row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


def aggregate_regional_districts_by_tes_machine_types_with_fuel(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))

    for row in rows:
        rd = row.regional_district_id
        tes_type = row.tes_type_id
        tes_machine_type = row.tes_machine_type_id
        fuel_type = row.fuel_type_id
        year = row.year

        p_ust[rd][tes_type][tes_machine_type][fuel_type][year] += row.p_ust or Decimal(0)
        p_ogr[rd][tes_type][tes_machine_type][fuel_type][year] += row.p_ogr or Decimal(0)
        p_rasp[rd][tes_type][tes_machine_type][fuel_type][year] += row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}

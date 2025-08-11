from collections import defaultdict
from decimal import Decimal


def aggregate_changes_by_regional_districts(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for row in rows:
        rd = row.regional_district_id
        year = row.year
        events = row.event_type

        if isinstance(events, (set, list, tuple)):
            for event in events:
                p_ust[rd][event][year] += row.p_ust or Decimal(0)
        elif events:
            p_ust[rd][events][year] += row.p_ust or Decimal(0)

    return {"aggregated": {"p_ust": p_ust}}



def aggregate_changes_regional_districts_by_station_types(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for row in rows:
        rd = row.regional_district_id
        station_type = row.station_type_id
        year = row.year
        events = row.event_type

        # поддержка одиночного события и множества событий
        if isinstance(events, (set, list, tuple)):
            for event in events:
                p_ust[rd][station_type][event][year] += row.p_ust or Decimal(0)
        elif events:
            p_ust[rd][station_type][events][year] += row.p_ust or Decimal(0)

    return {"aggregated": {"p_ust": p_ust}}



def aggregate_changes_regional_districts_by_station_types_with_fuel(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))

    for row in rows:
        event = row.event_type
        rd = row.regional_district_id
        station_type = row.station_type_id
        fuel = row.fuel_type_id
        year = row.year

        p_ust[rd][station_type][fuel][event][year] += row.p_ust or Decimal(0)

    return {"aggregated": {"p_ust": p_ust}}


def aggregate_changes_regional_districts_by_tes_types(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for row in rows:
        event = row.event_type
        rd = row.regional_district_id
        tes_type = row.tes_type_id
        year = row.year

        p_ust[rd][tes_type][event][year] += row.p_ust or Decimal(0)

    return {"aggregated": {"p_ust": p_ust}}


def aggregate_changes_regional_districts_by_tes_types_with_fuel(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))

    for row in rows:
        event = row.event_type
        rd = row.regional_district_id
        tes_type = row.tes_type_id
        fuel = row.fuel_type_id
        year = row.year

        p_ust[rd][tes_type][fuel][event][year] += row.p_ust or Decimal(0)

    return {"aggregated": {"p_ust": p_ust}}


def aggregate_changes_regional_districts_by_tes_machine_types(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))

    for row in rows:
        event = row.event_type
        rd = row.regional_district_id
        tes_type = row.tes_type_id
        tes_machine_type = row.tes_machine_type_id
        year = row.year

        p_ust[rd][tes_type][tes_machine_type][event][year] += row.p_ust or Decimal(0)

    return {"aggregated": {"p_ust": p_ust}}


def aggregate_changes_regional_districts_by_tes_machine_types_with_fuel(rows):
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))))

    for row in rows:
        event = row.event_type
        rd = row.regional_district_id
        tes_type = row.tes_type_id
        tes_machine_type = row.tes_machine_type_id
        fuel_type = row.fuel_type_id
        year = row.year

        p_ust[rd][tes_type][tes_machine_type][fuel_type][event][year] += row.p_ust or Decimal(0)

    return {"aggregated": {"p_ust": p_ust}}

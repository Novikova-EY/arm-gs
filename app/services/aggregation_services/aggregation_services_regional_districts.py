from collections import defaultdict
from decimal import Decimal
from sqlalchemy import func, and_
from app.models import (
    db,
    Station, Machine, MachinePower, MachineTesType,
    TesType, TesMachineType, MachineFuel, Fuel, FuelType,
    StationType
)

def dec(): return defaultdict(Decimal)

def aggregate_power_by_regional_districts(start_year, end_year, station_ids):
    from sqlalchemy import func
    from app.models import Station, Machine, MachinePower
    from collections import defaultdict
    from decimal import Decimal

    rows = (
        db.session.query(
            Station.id_regional_district.label("regional_district_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id_station == Station.id)
        .join(MachinePower, MachinePower.id_machine == Machine.id)
        .filter(
            Station.id.in_(station_ids),
            Station.id_regional_district != None,
            MachinePower.year_number.between(start_year, end_year)
        )
        .group_by(
            Station.id_regional_district,
            MachinePower.year_number
        )
        .all()
    )

    # [regional_district_id][year] -> Decimal
    p_ust = defaultdict(lambda: defaultdict(Decimal))
    p_ogr = defaultdict(lambda: defaultdict(Decimal))
    p_rasp = defaultdict(lambda: defaultdict(Decimal))

    for row in rows:
        rd = row.regional_district_id
        year = row.year
        p_ust[rd][year] = row.p_ust or Decimal(0)
        p_ogr[rd][year] = row.p_ogr or Decimal(0)
        p_rasp[rd][year] = row.p_rasp or Decimal(0)

    return {
        "aggregated": {
            "p_ust": p_ust,
            "p_ogr": p_ogr,
            "p_rasp": p_rasp,
        }
    }


def aggregate_regional_districts_by_station_types(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            Station.id_regional_district,
            StationType.id,
            MachinePower.year_number,
            func.sum(MachinePower.p_ust),
            func.sum(MachinePower.p_ogr),
            func.sum(MachinePower.p_rasp),
        )
        .select_from(MachinePower)
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(Station, Station.id == Machine.id_station)
        .join(StationType, StationType.id == Machine.id_station_type)
        .filter(
            Station.id.in_(station_ids),
            Station.id_regional_district != None,
            MachinePower.year_number.between(start_year, end_year),
        )
        .group_by(
            Station.id_regional_district,
            StationType.id,
            MachinePower.year_number,
        )
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for r in rows:
        regional_district_id, station_type_id, year = r[0], r[1], r[2]
        p_ust[regional_district_id][station_type_id][year] = r[3] or Decimal(0)
        p_ogr[regional_district_id][station_type_id][year] = r[4] or Decimal(0)
        p_rasp[regional_district_id][station_type_id][year] = r[5] or Decimal(0)

    return {
        "aggregated": {
            "p_ust": p_ust,
            "p_ogr": p_ogr,
            "p_rasp": p_rasp,
        }
    }


def aggregate_regional_districts_by_station_types_with_fuel(start_year, end_year, station_ids):
    from sqlalchemy import func, and_
    from app.models import (
        Station, Machine, MachinePower, MachineFuel, Fuel
    )

    rows = (
        db.session.query(
            Station.id_regional_district.label("regional_district_id"),
            Fuel.id_fuel_type.label("fuel_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id_station == Station.id)
        .join(MachinePower, MachinePower.id_machine == Machine.id)
        .join(MachineFuel, and_(
            MachineFuel.id_machine == Machine.id,
            MachineFuel.year_number == MachinePower.year_number
        ))
        .join(Fuel, Fuel.id == MachineFuel.id_fuel)
        .filter(
            MachinePower.year_number.between(start_year, end_year),
            Station.id.in_(station_ids)
        )
        .group_by(
            Station.id_regional_district,
            Fuel.id_fuel_type,
            MachinePower.year_number
        )
        .all()
    )

    # Преобразуем в нужную вложенную структуру
    from collections import defaultdict
    from decimal import Decimal

    def dec(): return defaultdict(Decimal)
    p_ust = defaultdict(lambda: defaultdict(dec))
    p_ogr = defaultdict(lambda: defaultdict(dec))
    p_rasp = defaultdict(lambda: defaultdict(dec))

    for row in rows:
        rd = row.regional_district_id
        fuel = row.fuel_type_id
        year = row.year

        p_ust[rd][fuel][year] = row.p_ust or Decimal(0)
        p_ogr[rd][fuel][year] = row.p_ogr or Decimal(0)
        p_rasp[rd][fuel][year] = row.p_rasp or Decimal(0)

    return {
        "aggregated": {
            "p_ust": p_ust,
            "p_ogr": p_ogr,
            "p_rasp": p_rasp,
        }
    }


def aggregate_regional_districts_by_tes_types(start_year, end_year, station_ids):
    from sqlalchemy import func, and_
    from app.models import (
        Station, Machine, MachinePower, MachineTesType, TesType
    )
    from collections import defaultdict
    from decimal import Decimal

    rows = (
        db.session.query(
            Station.id_regional_district.label("regional_district_id"),
            TesType.id.label("tes_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id_station == Station.id)
        .join(MachinePower, MachinePower.id_machine == Machine.id)
        .join(MachineTesType, and_(
            MachineTesType.id_machine == Machine.id,
            MachineTesType.year_number == MachinePower.year_number
        ))
        .join(TesType, TesType.id == MachineTesType.id_tes_type)
        .filter(
            MachinePower.year_number.between(start_year, end_year),
            Station.id.in_(station_ids),
            Station.id_regional_district != None
        )
        .group_by(
            Station.id_regional_district,
            TesType.id,
            MachinePower.year_number
        )
        .all()
    )

    # Преобразуем в нужную структуру [regional_district_id][tes_type_id][year]
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for row in rows:
        rd = row.regional_district_id
        tt = row.tes_type_id
        year = row.year

        p_ust[rd][tt][year] = row.p_ust or Decimal(0)
        p_ogr[rd][tt][year] = row.p_ogr or Decimal(0)
        p_rasp[rd][tt][year] = row.p_rasp or Decimal(0)

    return {
        "aggregated": {
            "p_ust": p_ust,
            "p_ogr": p_ogr,
            "p_rasp": p_rasp,
        }
    }


def aggregate_regional_districts_by_tes_types_with_fuel(start_year, end_year, station_ids):
    from sqlalchemy import func, and_
    from app.models import (
        Station, Machine, MachinePower, MachineTesType,
        MachineFuel, Fuel, TesType
    )
    from collections import defaultdict
    from decimal import Decimal

    rows = (
        db.session.query(
            Station.id_regional_district.label("regional_district_id"),
            TesType.id.label("tes_type_id"),
            Fuel.id_fuel_type.label("fuel_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id_station == Station.id)
        .join(MachinePower, MachinePower.id_machine == Machine.id)
        .join(MachineTesType, and_(
            MachineTesType.id_machine == Machine.id,
            MachineTesType.year_number == MachinePower.year_number
        ))
        .join(TesType, TesType.id == MachineTesType.id_tes_type)
        .join(MachineFuel, and_(
            MachineFuel.id_machine == Machine.id,
            MachineFuel.year_number == MachinePower.year_number
        ))
        .join(Fuel, Fuel.id == MachineFuel.id_fuel)
        .filter(
            Station.id.in_(station_ids),
            Station.id_regional_district != None,
            MachinePower.year_number.between(start_year, end_year)
        )
        .group_by(
            Station.id_regional_district,
            TesType.id,
            Fuel.id_fuel_type,
            MachinePower.year_number
        )
        .all()
    )

    # Структура: [субъект][тип ТЭС][тип топлива][год]
    def dec(): return defaultdict(Decimal)
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(dec)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(dec)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(dec)))

    for row in rows:
        rd = row.regional_district_id
        tt = row.tes_type_id
        fuel = row.fuel_type_id
        year = row.year

        p_ust[rd][tt][fuel][year] = row.p_ust or Decimal(0)
        p_ogr[rd][tt][fuel][year] = row.p_ogr or Decimal(0)
        p_rasp[rd][tt][fuel][year] = row.p_rasp or Decimal(0)

    return {
        "aggregated": {
            "p_ust": p_ust,
            "p_ogr": p_ogr,
            "p_rasp": p_rasp,
        }
    }


def aggregate_regional_districts_by_tes_machine_types(start_year, end_year, station_ids):
    from sqlalchemy import func, and_
    from app.models import (
        Station, Machine, MachinePower, MachineTesType,
        TesType, TesMachineType
    )
    from collections import defaultdict
    from decimal import Decimal

    rows = (
        db.session.query(
            Station.id_regional_district.label("regional_district_id"),
            TesType.id.label("tes_type_id"),
            TesMachineType.id.label("tes_machine_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id_station == Station.id)
        .join(MachinePower, MachinePower.id_machine == Machine.id)
        .join(MachineTesType, and_(
            MachineTesType.id_machine == Machine.id,
            MachineTesType.year_number == MachinePower.year_number
        ))
        .join(TesType, TesType.id == MachineTesType.id_tes_type)
        .join(TesMachineType, TesMachineType.id == Machine.id_tes_machine_type)
        .filter(
            Station.id.in_(station_ids),
            Station.id_regional_district != None,
            MachinePower.year_number.between(start_year, end_year)
        )
        .group_by(
            Station.id_regional_district,
            TesType.id,
            TesMachineType.id,
            MachinePower.year_number
        )
        .all()
    )

    # Структура: [субъект][тип ТЭС][тип агрегата][год]
    def dec(): return defaultdict(Decimal)
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(dec)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(dec)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(dec)))

    for row in rows:
        rd = row.regional_district_id
        tes_type_id = row.tes_type_id
        tmt_id = row.tes_machine_type_id
        year = row.year

        p_ust[rd][tes_type_id][tmt_id][year] = row.p_ust or Decimal(0)
        p_ogr[rd][tes_type_id][tmt_id][year] = row.p_ogr or Decimal(0)
        p_rasp[rd][tes_type_id][tmt_id][year] = row.p_rasp or Decimal(0)

    return {
        "aggregated": {
            "p_ust": p_ust,
            "p_ogr": p_ogr,
            "p_rasp": p_rasp,
        }
    }


def aggregate_regional_districts_by_tes_machine_types_with_fuel(start_year, end_year, station_ids):
    from sqlalchemy import func, and_
    from app.models import (
        Station, Machine, MachinePower, MachineTesType,
        TesType, TesMachineType, MachineFuel, Fuel, FuelType
    )
    from collections import defaultdict
    from decimal import Decimal

    # Основной SQL-запрос
    rows = (
        db.session.query(
            Station.id_regional_district.label("regional_district_id"),
            TesType.id.label("tes_type_id"),
            TesMachineType.id.label("tes_machine_type_id"),
            FuelType.id.label("fuel_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id_station == Station.id)
        .join(MachinePower, MachinePower.id_machine == Machine.id)
        .join(MachineTesType, and_(
            MachineTesType.id_machine == Machine.id,
            MachineTesType.year_number == MachinePower.year_number
        ))
        .join(TesType, TesType.id == MachineTesType.id_tes_type)
        .join(TesMachineType, TesMachineType.id == Machine.id_tes_machine_type)
        .join(MachineFuel, and_(
            MachineFuel.id_machine == Machine.id,
            MachineFuel.year_number == MachinePower.year_number
        ))
        .join(Fuel, Fuel.id == MachineFuel.id_fuel)
        .join(FuelType, FuelType.id == Fuel.id_fuel_type)
        .filter(
            Station.id.in_(station_ids),
            Station.id_regional_district != None,
            MachinePower.year_number.between(start_year, end_year)
        )
        .group_by(
            Station.id_regional_district,
            TesType.id,
            TesMachineType.id,
            FuelType.id,
            MachinePower.year_number
        )
        .all()
    )

    # Преобразуем результат: [region][tes_type][tes_machine_type][fuel_type][year]
    def dec(): return defaultdict(Decimal)
    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dec))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dec))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dec))))

    for row in rows:
        rd = row.regional_district_id
        tes_type = row.tes_type_id
        machine_type = row.tes_machine_type_id
        fuel_type = row.fuel_type_id
        year = row.year

        p_ust[rd][tes_type][machine_type][fuel_type][year] = row.p_ust or Decimal(0)
        p_ogr[rd][tes_type][machine_type][fuel_type][year] = row.p_ogr or Decimal(0)
        p_rasp[rd][tes_type][machine_type][fuel_type][year] = row.p_rasp or Decimal(0)

    return {
        "aggregated": {
            "p_ust": p_ust,
            "p_ogr": p_ogr,
            "p_rasp": p_rasp,
        }
    }





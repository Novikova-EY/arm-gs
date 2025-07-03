from collections import defaultdict
from decimal import Decimal
from sqlalchemy import func, and_
from app.models import (
    db,
    Station, Machine, MachinePower, MachineTesType,
    TesType, TesMachineType, MachineFuel, Fuel, FuelType,
    StationType
)


# 1. Всего по типам энергосистем (по годам)
def aggregate_power_by_total_energy_system_types(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(Station, Station.id == Machine.id_station)
        .filter(
            Station.id.in_(station_ids),
            MachinePower.year_number.between(start_year, end_year)
        )
        .group_by(MachinePower.year_number)
        .all()
    )

    p_ust = defaultdict(Decimal)
    p_ogr = defaultdict(Decimal)
    p_rasp = defaultdict(Decimal)

    for row in rows:
        year = row.year
        p_ust[year] = row.p_ust or Decimal(0)
        p_ogr[year] = row.p_ogr or Decimal(0)
        p_rasp[year] = row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


# 2. По типам станций

def aggregate_total_energy_system_types_by_station_types(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            Machine.id_station_type.label("station_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .select_from(MachinePower)
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(Station, Station.id == Machine.id_station)
        .filter(
            Station.id.in_(station_ids),
            MachinePower.year_number.between(start_year, end_year)
        )
        .group_by(Machine.id_station_type, MachinePower.year_number)
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(Decimal))
    p_ogr = defaultdict(lambda: defaultdict(Decimal))
    p_rasp = defaultdict(lambda: defaultdict(Decimal))

    for row in rows:
        st_id, year = row.station_type_id, row.year
        p_ust[st_id][year] = row.p_ust or Decimal(0)
        p_ogr[st_id][year] = row.p_ogr or Decimal(0)
        p_rasp[st_id][year] = row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


# 3. По типам станций с топливом

def aggregate_total_energy_system_types_by_station_types_with_fuel(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            FuelType.id.label("fuel_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(Station, Station.id == Machine.id_station)
        .join(MachineFuel, and_(
            MachineFuel.id_machine == Machine.id,
            MachineFuel.year_number == MachinePower.year_number
        ))
        .join(Fuel, Fuel.id == MachineFuel.id_fuel)
        .join(FuelType, Fuel.id_fuel_type == FuelType.id)
        .filter(
            Station.id.in_(station_ids),
            MachinePower.year_number.between(start_year, end_year)
        )
        .group_by(FuelType.id, MachinePower.year_number)
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(Decimal))
    p_ogr = defaultdict(lambda: defaultdict(Decimal))
    p_rasp = defaultdict(lambda: defaultdict(Decimal))

    for row in rows:
        fuel_id, year = row.fuel_type_id, row.year
        p_ust[fuel_id][year] = row.p_ust or Decimal(0)
        p_ogr[fuel_id][year] = row.p_ogr or Decimal(0)
        p_rasp[fuel_id][year] = row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


# 4. По типам ТЭС

def aggregate_total_energy_system_types_by_tes_types(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            TesType.id.label("tes_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(Station, Station.id == Machine.id_station)
        .join(MachineTesType, and_(
            MachineTesType.id_machine == Machine.id,
            MachineTesType.year_number == MachinePower.year_number
        ))
        .join(TesType, TesType.id == MachineTesType.id_tes_type)
        .filter(
            Station.id.in_(station_ids),
            MachinePower.year_number.between(start_year, end_year)
        )
        .group_by(TesType.id, MachinePower.year_number)
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(Decimal))
    p_ogr = defaultdict(lambda: defaultdict(Decimal))
    p_rasp = defaultdict(lambda: defaultdict(Decimal))

    for row in rows:
        tes_id, year = row.tes_type_id, row.year
        p_ust[tes_id][year] = row.p_ust or Decimal(0)
        p_ogr[tes_id][year] = row.p_ogr or Decimal(0)
        p_rasp[tes_id][year] = row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


# 5. По ТЭС и топливу

def aggregate_total_energy_system_types_by_tes_types_with_fuel(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            TesType.id.label("tes_type_id"),
            FuelType.id.label("fuel_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(Station, Station.id == Machine.id_station)
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
        .join(FuelType, FuelType.id == Fuel.id_fuel_type)
        .filter(
            Station.id.in_(station_ids),
            MachinePower.year_number.between(start_year, end_year)
        )
        .group_by(TesType.id, FuelType.id, MachinePower.year_number)
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for row in rows:
        tes_id, fuel_id, year = row.tes_type_id, row.fuel_type_id, row.year
        p_ust[tes_id][fuel_id][year] = row.p_ust or Decimal(0)
        p_ogr[tes_id][fuel_id][year] = row.p_ogr or Decimal(0)
        p_rasp[tes_id][fuel_id][year] = row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


# 6. По типам машин ТЭС

def aggregate_total_energy_system_types_by_tes_machine_types(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            TesType.id.label("tes_type_id"),
            TesMachineType.id.label("tes_machine_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(Station, Station.id == Machine.id_station)
        .join(MachineTesType, and_(
            MachineTesType.id_machine == Machine.id,
            MachineTesType.year_number == MachinePower.year_number
        ))
        .join(TesType, TesType.id == MachineTesType.id_tes_type)
        .join(TesMachineType, TesMachineType.id == Machine.id_tes_machine_type)
        .filter(
            Station.id.in_(station_ids),
            MachinePower.year_number.between(start_year, end_year)
        )
        .group_by(TesType.id, TesMachineType.id, MachinePower.year_number)
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for row in rows:
        tes_id, machine_type_id, year = row.tes_type_id, row.tes_machine_type_id, row.year
        p_ust[tes_id][machine_type_id][year] = row.p_ust or Decimal(0)
        p_ogr[tes_id][machine_type_id][year] = row.p_ogr or Decimal(0)
        p_rasp[tes_id][machine_type_id][year] = row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


# 7. По типам машин ТЭС с топливом

def aggregate_total_energy_system_types_by_tes_machine_types_with_fuel(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            TesType.id.label("tes_type_id"),
            TesMachineType.id.label("tes_machine_type_id"),
            FuelType.id.label("fuel_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(Station, Station.id == Machine.id_station)
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
            MachinePower.year_number.between(start_year, end_year)
        )
        .group_by(TesType.id, TesMachineType.id, FuelType.id, MachinePower.year_number)
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for row in rows:
        tes_id, machine_type_id, fuel_id, year = row.tes_type_id, row.tes_machine_type_id, row.fuel_type_id, row.year
        p_ust[tes_id][machine_type_id][fuel_id][year] = row.p_ust or Decimal(0)
        p_ogr[tes_id][machine_type_id][fuel_id][year] = row.p_ogr or Decimal(0)
        p_rasp[tes_id][machine_type_id][fuel_id][year] = row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}
from collections import defaultdict
from decimal import Decimal
from sqlalchemy import func, and_
from app.models import (
    db,
    Station, Machine, MachinePower, MachineTesType,
    TesType, TesMachineType, MachineFuel, Fuel, FuelType,
    StationType
)


def dec():
    return defaultdict(Decimal)


# 1. Энергоузлы — всего

def aggregate_power_by_energy_units(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            Station.id_energy_unit,
            MachinePower.year_number,
            func.sum(MachinePower.p_ust),
            func.sum(MachinePower.p_ogr),
            func.sum(MachinePower.p_rasp),
        )
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(Station, Station.id == Machine.id_station)
        .filter(Station.id.in_(station_ids), MachinePower.year_number.between(start_year, end_year))
        .group_by(Station.id_energy_unit, MachinePower.year_number)
        .all()
    )

    p_ust, p_ogr, p_rasp = defaultdict(dec), defaultdict(dec), defaultdict(dec)

    for eu_id, year, rust, rogr, rrasp in rows:
        p_ust[eu_id][year] = rust or Decimal(0)
        p_ogr[eu_id][year] = rogr or Decimal(0)
        p_rasp[eu_id][year] = rrasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


# 2. По типам станций

def aggregate_energy_units_by_station_types(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            Station.id_energy_unit,
            StationType.id,
            MachinePower.year_number,
            func.sum(MachinePower.p_ust),
            func.sum(MachinePower.p_ogr),
            func.sum(MachinePower.p_rasp),
        )
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(Station, Station.id == Machine.id_station)
        .join(StationType, StationType.id == Machine.id_station_type)
        .filter(Station.id.in_(station_ids), MachinePower.year_number.between(start_year, end_year))
        .group_by(Station.id_energy_unit, StationType.id, MachinePower.year_number)
        .all()
    )

    p_ust, p_ogr, p_rasp = defaultdict(lambda: defaultdict(dec)), defaultdict(lambda: defaultdict(dec)), defaultdict(lambda: defaultdict(dec))

    for eu_id, st_type_id, year, rust, rogr, rrasp in rows:
        key = (st_type_id,)
        p_ust[eu_id][key][year] = rust or Decimal(0)
        p_ogr[eu_id][key][year] = rogr or Decimal(0)
        p_rasp[eu_id][key][year] = rrasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


# 3. По типам станций с топливом

def aggregate_energy_units_by_station_types_with_fuel(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            Station.id_energy_unit,
            StationType.id,
            FuelType.id,
            MachinePower.year_number,
            func.sum(MachinePower.p_ust),
            func.sum(MachinePower.p_ogr),
            func.sum(MachinePower.p_rasp),
        )
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(Station, Station.id == Machine.id_station)
        .join(StationType, StationType.id == Machine.id_station_type)
        .join(MachineFuel, and_(MachineFuel.id_machine == Machine.id, MachineFuel.year_number == MachinePower.year_number))
        .join(Fuel, Fuel.id == MachineFuel.id_fuel)
        .join(FuelType, FuelType.id == Fuel.id_fuel_type)
        .filter(Station.id.in_(station_ids), MachinePower.year_number.between(start_year, end_year))
        .group_by(Station.id_energy_unit, StationType.id, FuelType.id, MachinePower.year_number)
        .all()
    )

    p_ust, p_ogr, p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(dec))), defaultdict(lambda: defaultdict(lambda: defaultdict(dec))), defaultdict(lambda: defaultdict(lambda: defaultdict(dec)))

    for eu_id, st_type_id, fuel_type_id, year, rust, rogr, rrasp in rows:
        key = (st_type_id, fuel_type_id)
        p_ust[eu_id][key][year] = rust or Decimal(0)
        p_ogr[eu_id][key][year] = rogr or Decimal(0)
        p_rasp[eu_id][key][year] = rrasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


# 4. По типам ТЭС

def aggregate_energy_units_by_tes_types(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            Station.id_energy_unit,
            TesType.id,
            MachinePower.year_number,
            func.sum(MachinePower.p_ust),
            func.sum(MachinePower.p_ogr),
            func.sum(MachinePower.p_rasp),
        )
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(Station, Station.id == Machine.id_station)
        .join(MachineTesType, and_(MachineTesType.id_machine == Machine.id, MachineTesType.year_number == MachinePower.year_number))
        .join(TesType, TesType.id == MachineTesType.id_tes_type)
        .filter(Station.id.in_(station_ids), MachinePower.year_number.between(start_year, end_year))
        .group_by(Station.id_energy_unit, TesType.id, MachinePower.year_number)
        .all()
    )

    p_ust, p_ogr, p_rasp = defaultdict(lambda: defaultdict(dec)), defaultdict(lambda: defaultdict(dec)), defaultdict(lambda: defaultdict(dec))

    for eu_id, tes_type_id, year, rust, rogr, rrasp in rows:
        key = (tes_type_id,)
        p_ust[eu_id][key][year] = rust or Decimal(0)
        p_ogr[eu_id][key][year] = rogr or Decimal(0)
        p_rasp[eu_id][key][year] = rrasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


# 5. По типам ТЭС с топливом

def aggregate_energy_units_by_tes_types_with_fuel(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            Station.id_energy_unit,
            TesType.id,
            FuelType.id,
            MachinePower.year_number,
            func.sum(MachinePower.p_ust),
            func.sum(MachinePower.p_ogr),
            func.sum(MachinePower.p_rasp),
        )
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(Station, Station.id == Machine.id_station)
        .join(MachineTesType, and_(MachineTesType.id_machine == Machine.id, MachineTesType.year_number == MachinePower.year_number))
        .join(TesType, TesType.id == MachineTesType.id_tes_type)
        .join(MachineFuel, and_(MachineFuel.id_machine == Machine.id, MachineFuel.year_number == MachinePower.year_number))
        .join(Fuel, Fuel.id == MachineFuel.id_fuel)
        .join(FuelType, FuelType.id == Fuel.id_fuel_type)
        .filter(Station.id.in_(station_ids), MachinePower.year_number.between(start_year, end_year))
        .group_by(Station.id_energy_unit, TesType.id, FuelType.id, MachinePower.year_number)
        .all()
    )

    p_ust, p_ogr, p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(dec))), defaultdict(lambda: defaultdict(lambda: defaultdict(dec))), defaultdict(lambda: defaultdict(lambda: defaultdict(dec)))

    for eu_id, tes_type_id, fuel_type_id, year, rust, rogr, rrasp in rows:
        key = (tes_type_id, fuel_type_id)
        p_ust[eu_id][key][year] = rust or Decimal(0)
        p_ogr[eu_id][key][year] = rogr or Decimal(0)
        p_rasp[eu_id][key][year] = rrasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


# 6. По типам машин ТЭС

def aggregate_energy_units_by_tes_machine_types(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            Station.id_energy_unit,
            TesType.id,
            TesMachineType.id,
            MachinePower.year_number,
            func.sum(MachinePower.p_ust),
            func.sum(MachinePower.p_ogr),
            func.sum(MachinePower.p_rasp),
        )
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(Station, Station.id == Machine.id_station)
        .join(MachineTesType, and_(MachineTesType.id_machine == Machine.id, MachineTesType.year_number == MachinePower.year_number))
        .join(TesType)
        .join(TesMachineType, TesMachineType.id == Machine.id_tes_machine_type)
        .filter(Station.id.in_(station_ids), MachinePower.year_number.between(start_year, end_year))
        .group_by(Station.id_energy_unit, TesType.id, TesMachineType.id, MachinePower.year_number)
        .all()
    )

    p_ust, p_ogr, p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(dec))), defaultdict(lambda: defaultdict(lambda: defaultdict(dec))), defaultdict(lambda: defaultdict(lambda: defaultdict(dec)))

    for eu_id, tes_type_id, tm_type_id, year, rust, rogr, rrasp in rows:
        key = (tes_type_id, tm_type_id)
        p_ust[eu_id][key][year] = rust or Decimal(0)
        p_ogr[eu_id][key][year] = rogr or Decimal(0)
        p_rasp[eu_id][key][year] = rrasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


# 7. По типам машин ТЭС с топливом

def aggregate_energy_units_by_tes_machine_types_with_fuel(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            Station.id_energy_unit,
            TesType.id,
            TesMachineType.id,
            FuelType.id,
            MachinePower.year_number,
            func.sum(MachinePower.p_ust),
            func.sum(MachinePower.p_ogr),
            func.sum(MachinePower.p_rasp),
        )
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(Station, Station.id == Machine.id_station)
        .join(MachineTesType, and_(MachineTesType.id_machine == Machine.id, MachineTesType.year_number == MachinePower.year_number))
        .join(TesType)
        .join(TesMachineType, TesMachineType.id == Machine.id_tes_machine_type)
        .join(MachineFuel, and_(MachineFuel.id_machine == Machine.id, MachineFuel.year_number == MachinePower.year_number))
        .join(Fuel, Fuel.id == MachineFuel.id_fuel)
        .join(FuelType, FuelType.id == Fuel.id_fuel_type)
        .filter(Station.id.in_(station_ids), MachinePower.year_number.between(start_year, end_year))
        .group_by(Station.id_energy_unit, TesType.id, TesMachineType.id, FuelType.id, MachinePower.year_number)
        .all()
    )

    p_ust, p_ogr, p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dec)))), defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dec)))), defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dec))))

    for eu_id, tes_type_id, tm_type_id, fuel_type_id, year, rust, rogr, rrasp in rows:
        key = (tes_type_id, tm_type_id, fuel_type_id)
        p_ust[eu_id][key][year] = rust or Decimal(0)
        p_ogr[eu_id][key][year] = rogr or Decimal(0)
        p_rasp[eu_id][key][year] = rrasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}

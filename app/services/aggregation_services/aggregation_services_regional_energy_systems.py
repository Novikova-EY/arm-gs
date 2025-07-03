from collections import defaultdict
from decimal import Decimal
from sqlalchemy import func, and_
from app.models import (
    db,
    Station, Machine, MachinePower, MachineTesType,
    TesType, TesMachineType, MachineFuel, Fuel, FuelType,
    RegionalDistrict, RegionalEnergySystem, StationType
)


def dec():
    return defaultdict(Decimal)


# 1. Агрегация: Всего по региональной энергосистеме

def aggregate_power_by_regional_energy_systems(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            RegionalEnergySystem.id,
            MachinePower.year_number,
            func.sum(MachinePower.p_ust),
            func.sum(MachinePower.p_ogr),
            func.sum(MachinePower.p_rasp),
        )
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(Station, Station.id == Machine.id_station)
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .filter(Station.id.in_(station_ids), MachinePower.year_number.between(start_year, end_year))
        .group_by(RegionalEnergySystem.id, MachinePower.year_number)
        .all()
    )

    p_ust, p_ogr, p_rasp = defaultdict(dec), defaultdict(dec), defaultdict(dec)

    for res_id, year, rust, rogr, rrasp in rows:
        p_ust[res_id][year] = rust or Decimal(0)
        p_ogr[res_id][year] = rogr or Decimal(0)
        p_rasp[res_id][year] = rrasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


# 2. Агрегация: По типам станций

def aggregate_regional_energy_systems_by_station_types(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            RegionalEnergySystem.id.label("regional_energy_system_id"),
            Machine.id_station_type.label("station_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .select_from(MachinePower)
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(Station, Station.id == Machine.id_station)
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .filter(
            Station.id.in_(station_ids),
            MachinePower.year_number.between(start_year, end_year)
        )
        .group_by(
            RegionalEnergySystem.id,
            Machine.id_station_type,
            MachinePower.year_number
        )
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for row in rows:
        res_id, station_type_id, year = row.regional_energy_system_id, row.station_type_id, row.year
        p_ust[res_id][station_type_id][year] = row.p_ust or Decimal(0)
        p_ogr[res_id][station_type_id][year] = row.p_ogr or Decimal(0)
        p_rasp[res_id][station_type_id][year] = row.p_rasp or Decimal(0)

    return {
        "aggregated": {
            "p_ust": p_ust,
            "p_ogr": p_ogr,
            "p_rasp": p_rasp,
        }
    }


# 3. По типам станций с топливом

def aggregate_regional_energy_systems_by_station_types_with_fuel(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            RegionalEnergySystem.id.label("regional_energy_system_id"),
            Machine.id_station_type.label("station_type_id"),
            FuelType.id.label("fuel_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .select_from(MachinePower)
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(Station, Station.id == Machine.id_station)
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
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
        .group_by(
            RegionalEnergySystem.id,
            Machine.id_station_type,
            FuelType.id,
            MachinePower.year_number
        )
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for row in rows:
        res_id, station_type_id, fuel_type_id, year = row.regional_energy_system_id, row.station_type_id, row.fuel_type_id, row.year
        p_ust[res_id][station_type_id][fuel_type_id][year] = row.p_ust or Decimal(0)
        p_ogr[res_id][station_type_id][fuel_type_id][year] = row.p_ogr or Decimal(0)
        p_rasp[res_id][station_type_id][fuel_type_id][year] = row.p_rasp or Decimal(0)

    return {
        "aggregated": {
            "p_ust": p_ust,
            "p_ogr": p_ogr,
            "p_rasp": p_rasp,
        }
    }



# 3. Агрегация: По типам ТЭС

def aggregate_regional_energy_systems_by_tes_types(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            RegionalEnergySystem.id,
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
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .filter(Station.id.in_(station_ids), MachinePower.year_number.between(start_year, end_year))
        .group_by(RegionalEnergySystem.id, TesType.id, MachinePower.year_number)
        .all()
    )

    p_ust, p_ogr, p_rasp = defaultdict(lambda: defaultdict(dec)), defaultdict(lambda: defaultdict(dec)), defaultdict(lambda: defaultdict(dec))

    for res_id, tes_type_id, year, rust, rogr, rrasp in rows:
        p_ust[res_id][tes_type_id][year] = rust or Decimal(0)
        p_ogr[res_id][tes_type_id][year] = rogr or Decimal(0)
        p_rasp[res_id][tes_type_id][year] = rrasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


# 4. Агрегация: ТЭС + топливо

def aggregate_regional_energy_systems_by_tes_types_with_fuel(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            RegionalEnergySystem.id,
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
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .filter(Station.id.in_(station_ids), MachinePower.year_number.between(start_year, end_year))
        .group_by(RegionalEnergySystem.id, TesType.id, FuelType.id, MachinePower.year_number)
        .all()
    )

    p_ust, p_ogr, p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(dec))), defaultdict(lambda: defaultdict(lambda: defaultdict(dec))), defaultdict(lambda: defaultdict(lambda: defaultdict(dec)))

    for res_id, tes_type_id, fuel_type_id, year, rust, rogr, rrasp in rows:
        p_ust[res_id][tes_type_id][fuel_type_id][year] = rust or Decimal(0)
        p_ogr[res_id][tes_type_id][fuel_type_id][year] = rogr or Decimal(0)
        p_rasp[res_id][tes_type_id][fuel_type_id][year] = rrasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


# 5. Агрегация: ТЭС + тип машины

def aggregate_regional_energy_systems_by_tes_machine_types(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            RegionalEnergySystem.id,
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
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .filter(Station.id.in_(station_ids), MachinePower.year_number.between(start_year, end_year))
        .group_by(RegionalEnergySystem.id, TesType.id, TesMachineType.id, MachinePower.year_number)
        .all()
    )

    p_ust, p_ogr, p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(dec))), defaultdict(lambda: defaultdict(lambda: defaultdict(dec))), defaultdict(lambda: defaultdict(lambda: defaultdict(dec)))

    for res_id, tes_type_id, tm_type_id, year, rust, rogr, rrasp in rows:
        p_ust[res_id][tes_type_id][tm_type_id][year] = rust or Decimal(0)
        p_ogr[res_id][tes_type_id][tm_type_id][year] = rogr or Decimal(0)
        p_rasp[res_id][tes_type_id][tm_type_id][year] = rrasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}


# 6. Агрегация: ТЭС + тип машины + топливо

def aggregate_regional_energy_systems_by_tes_machine_types_with_fuel(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            RegionalEnergySystem.id,
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
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .filter(Station.id.in_(station_ids), MachinePower.year_number.between(start_year, end_year))
        .group_by(RegionalEnergySystem.id, TesType.id, TesMachineType.id, FuelType.id, MachinePower.year_number)
        .all()
    )

    p_ust, p_ogr, p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dec)))), defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dec)))), defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dec))))

    for res_id, tes_type_id, tm_type_id, fuel_type_id, year, rust, rogr, rrasp in rows:
        p_ust[res_id][tes_type_id][tm_type_id][fuel_type_id][year] = rust or Decimal(0)
        p_ogr[res_id][tes_type_id][tm_type_id][fuel_type_id][year] = rogr or Decimal(0)
        p_rasp[res_id][tes_type_id][tm_type_id][fuel_type_id][year] = rrasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}

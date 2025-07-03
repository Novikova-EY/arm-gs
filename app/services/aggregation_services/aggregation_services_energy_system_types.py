from collections import defaultdict
from decimal import Decimal
from sqlalchemy import func, and_
from app.models import (
    db,
    Station, Machine, MachinePower, MachineTesType,
    TesType, TesMachineType, MachineFuel, Fuel, FuelType,
    RegionalDistrict, RegionalEnergySystem, UnionEnergySystem, EnergySystemType,
    StationType
)

def dec(): return defaultdict(Decimal)

def aggregate_power_by_energy_system_types(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            EnergySystemType.id.label("energy_system_type_id"),
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
        .join(RegionalEnergySystem.union_energy_system)
        .join(UnionEnergySystem.energy_system_type)
        .filter(
            Station.id.in_(station_ids),
            MachinePower.year_number.between(start_year, end_year),
        )
        .group_by(EnergySystemType.id, MachinePower.year_number)
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(Decimal))
    p_ogr = defaultdict(lambda: defaultdict(Decimal))
    p_rasp = defaultdict(lambda: defaultdict(Decimal))

    for row in rows:
        est_id, year = row.energy_system_type_id, row.year
        p_ust[est_id][year] = row.p_ust or Decimal(0)
        p_ogr[est_id][year] = row.p_ogr or Decimal(0)
        p_rasp[est_id][year] = row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}



def aggregate_energy_system_types_by_station_types(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            EnergySystemType.id.label("energy_system_type_id"),
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
        .join(RegionalEnergySystem.union_energy_system)
        .join(UnionEnergySystem.energy_system_type)
        .filter(
            Station.id.in_(station_ids),
            MachinePower.year_number.between(start_year, end_year),
        )
        .group_by(EnergySystemType.id, Machine.id_station_type, MachinePower.year_number)
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for row in rows:
        est_id, st_id, year = row.energy_system_type_id, row.station_type_id, row.year
        p_ust[est_id][st_id][year] = row.p_ust or Decimal(0)
        p_ogr[est_id][st_id][year] = row.p_ogr or Decimal(0)
        p_rasp[est_id][st_id][year] = row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}



def aggregate_energy_system_types_by_station_types_with_fuel(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            EnergySystemType.id.label("energy_system_type_id"),
            Machine.id_station_type.label("station_type_id"),
            FuelType.id.label("fuel_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .select_from(MachinePower)
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(MachineFuel, and_(MachineFuel.id_machine == Machine.id, MachineFuel.year_number == MachinePower.year_number))
        .join(Fuel, Fuel.id == MachineFuel.id_fuel)
        .join(FuelType, Fuel.id_fuel_type == FuelType.id)
        .join(Station, Station.id == Machine.id_station)
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .join(RegionalEnergySystem.union_energy_system)
        .join(UnionEnergySystem.energy_system_type)
        .filter(
            Station.id.in_(station_ids),
            MachinePower.year_number.between(start_year, end_year),
        )
        .group_by(EnergySystemType.id, Machine.id_station_type, FuelType.id, MachinePower.year_number)
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for row in rows:
        est_id, st_id, fuel_id, year = row.energy_system_type_id, row.station_type_id, row.fuel_type_id, row.year
        p_ust[est_id][st_id][fuel_id][year] = row.p_ust or Decimal(0)
        p_ogr[est_id][st_id][fuel_id][year] = row.p_ogr or Decimal(0)
        p_rasp[est_id][st_id][fuel_id][year] = row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}



def aggregate_energy_system_types_by_tes_types(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            EnergySystemType.id.label("energy_system_type_id"),
            TesType.id.label("tes_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .select_from(MachinePower)
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(MachineTesType, and_(
            MachineTesType.id_machine == Machine.id,
            MachineTesType.year_number == MachinePower.year_number
        ))
        .join(TesType, TesType.id == MachineTesType.id_tes_type)
        .join(Station, Station.id == Machine.id_station)
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .join(RegionalEnergySystem.union_energy_system)
        .join(UnionEnergySystem.energy_system_type)
        .filter(
            Station.id.in_(station_ids),
            MachinePower.year_number.between(start_year, end_year),
        )
        .group_by(EnergySystemType.id, TesType.id, MachinePower.year_number)
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for row in rows:
        est_id, tes_id, year = row.energy_system_type_id, row.tes_type_id, row.year
        p_ust[est_id][tes_id][year] = row.p_ust or Decimal(0)
        p_ogr[est_id][tes_id][year] = row.p_ogr or Decimal(0)
        p_rasp[est_id][tes_id][year] = row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}



def aggregate_energy_system_types_by_tes_types_with_fuel(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            EnergySystemType.id.label("energy_system_type_id"),
            TesType.id.label("tes_type_id"),
            FuelType.id.label("fuel_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .select_from(MachinePower)
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(MachineTesType, and_(
            MachineTesType.id_machine == Machine.id,
            MachineTesType.year_number == MachinePower.year_number
        ))
        .join(TesType, TesType.id == MachineTesType.id_tes_type)
        .join(Station, Station.id == Machine.id_station)
        .join(MachineFuel, and_(
            MachineFuel.id_machine == Machine.id,
            MachineFuel.year_number == MachinePower.year_number
        ))
        .join(Fuel, Fuel.id == MachineFuel.id_fuel)
        .join(FuelType, FuelType.id == Fuel.id_fuel_type)
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .join(RegionalEnergySystem.union_energy_system)
        .join(UnionEnergySystem.energy_system_type)
        .filter(Station.id.in_(station_ids), MachinePower.year_number.between(start_year, end_year))
        .group_by(EnergySystemType.id, TesType.id, FuelType.id, MachinePower.year_number)
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for row in rows:
        est_id, tes_id, fuel_id, year = row.energy_system_type_id, row.tes_type_id, row.fuel_type_id, row.year
        p_ust[est_id][tes_id][fuel_id][year] = row.p_ust or Decimal(0)
        p_ogr[est_id][tes_id][fuel_id][year] = row.p_ogr or Decimal(0)
        p_rasp[est_id][tes_id][fuel_id][year] = row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}



def aggregate_energy_system_types_by_tes_machine_types(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            EnergySystemType.id.label("energy_system_type_id"),
            TesType.id.label("tes_type_id"),
            TesMachineType.id.label("tes_machine_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .select_from(MachinePower)
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(Station, Station.id == Machine.id_station)
        .join(MachineTesType, and_(MachineTesType.id_machine == Machine.id, MachineTesType.year_number == MachinePower.year_number))
        .join(TesType, TesType.id == MachineTesType.id_tes_type)
        .join(TesMachineType, TesMachineType.id == Machine.id_tes_machine_type)
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .join(RegionalEnergySystem.union_energy_system)
        .join(UnionEnergySystem.energy_system_type)
        .filter(Station.id.in_(station_ids), MachinePower.year_number.between(start_year, end_year))
        .group_by(EnergySystemType.id, TesType.id, TesMachineType.id, MachinePower.year_number)
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for row in rows:
        est_id, tes_id, machine_type_id, year = row.energy_system_type_id, row.tes_type_id, row.tes_machine_type_id, row.year
        p_ust[est_id][tes_id][machine_type_id][year] = row.p_ust or Decimal(0)
        p_ogr[est_id][tes_id][machine_type_id][year] = row.p_ogr or Decimal(0)
        p_rasp[est_id][tes_id][machine_type_id][year] = row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}



def aggregate_energy_system_types_by_tes_machine_types_with_fuel(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            EnergySystemType.id.label("energy_system_type_id"),
            TesType.id.label("tes_type_id"),
            TesMachineType.id.label("tes_machine_type_id"),
            FuelType.id.label("fuel_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .select_from(MachinePower)
        .join(Machine, Machine.id == MachinePower.id_machine)
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
        .join(Station, Station.id == Machine.id_station)
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .join(RegionalEnergySystem.union_energy_system)
        .join(UnionEnergySystem.energy_system_type)
        .filter(Station.id.in_(station_ids), MachinePower.year_number.between(start_year, end_year))
        .group_by(EnergySystemType.id, TesType.id, TesMachineType.id, FuelType.id, MachinePower.year_number)
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))

    for row in rows:
        est_id, tes_id, machine_type_id, fuel_id, year = row.energy_system_type_id, row.tes_type_id, row.tes_machine_type_id, row.fuel_type_id, row.year
        p_ust[est_id][tes_id][machine_type_id][fuel_id][year] = row.p_ust or Decimal(0)
        p_ogr[est_id][tes_id][machine_type_id][fuel_id][year] = row.p_ogr or Decimal(0)
        p_rasp[est_id][tes_id][machine_type_id][fuel_id][year] = row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}

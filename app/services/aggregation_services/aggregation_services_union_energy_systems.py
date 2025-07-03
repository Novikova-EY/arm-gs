from collections import defaultdict
from decimal import Decimal
from sqlalchemy import func, and_
from app.models import (
    db,
    Station, Machine, MachinePower, MachineTesType,
    TesType, TesMachineType, MachineFuel, Fuel, FuelType,
    RegionalDistrict, RegionalEnergySystem, UnionEnergySystem,
    StationType
)

def dec(): return defaultdict(Decimal)


def aggregate_power_by_union_energy_systems(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            RegionalEnergySystem.id_union_energy_system.label("union_energy_system_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(Station, Station.id == Machine.id_station)
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .filter(
            Station.id.in_(station_ids),
            MachinePower.year_number.between(start_year, end_year),
        )
        .group_by(RegionalEnergySystem.id_union_energy_system, MachinePower.year_number)
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(Decimal))
    p_ogr = defaultdict(lambda: defaultdict(Decimal))
    p_rasp = defaultdict(lambda: defaultdict(Decimal))

    for row in rows:
        ues, year = row.union_energy_system_id, row.year
        p_ust[ues][year] = row.p_ust or Decimal(0)
        p_ogr[ues][year] = row.p_ogr or Decimal(0)
        p_rasp[ues][year] = row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}



def aggregate_union_energy_systems_by_station_types(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            RegionalEnergySystem.id_union_energy_system.label("union_energy_system_id"),
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
            MachinePower.year_number.between(start_year, end_year),
        )
        .group_by(RegionalEnergySystem.id_union_energy_system, Machine.id_station_type, MachinePower.year_number)
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for row in rows:
        ues, st, year = row.union_energy_system_id, row.station_type_id, row.year
        p_ust[ues][st][year] = row.p_ust or Decimal(0)
        p_ogr[ues][st][year] = row.p_ogr or Decimal(0)
        p_rasp[ues][st][year] = row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}




def aggregate_union_energy_systems_by_station_types_with_fuel(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            RegionalEnergySystem.id_union_energy_system.label("union_energy_system_id"),
            Machine.id_station_type.label("station_type_id"),
            FuelType.id.label("fuel_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(MachineFuel, and_(MachineFuel.id_machine == Machine.id, MachineFuel.year_number == MachinePower.year_number))
        .join(Fuel, Fuel.id == MachineFuel.id_fuel)
        .join(FuelType, Fuel.id_fuel_type == FuelType.id)
        .join(Station, Station.id == Machine.id_station)
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .filter(
            Station.id.in_(station_ids),
            MachinePower.year_number.between(start_year, end_year),
        )
        .group_by(RegionalEnergySystem.id_union_energy_system, Machine.id_station_type, FuelType.id, MachinePower.year_number)
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for row in rows:
        ues, st, fuel, year = row.union_energy_system_id, row.station_type_id, row.fuel_type_id, row.year
        p_ust[ues][st][fuel][year] = row.p_ust or Decimal(0)
        p_ogr[ues][st][fuel][year] = row.p_ogr or Decimal(0)
        p_rasp[ues][st][fuel][year] = row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}



def aggregate_union_energy_systems_by_tes_types(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            RegionalEnergySystem.id_union_energy_system.label("union_energy_system_id"),
            TesType.id.label("tes_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(MachineTesType, and_(MachineTesType.id_machine == Machine.id, MachineTesType.year_number == MachinePower.year_number))
        .join(TesType, TesType.id == MachineTesType.id_tes_type)
        .join(Station, Station.id == Machine.id_station)
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .filter(Station.id.in_(station_ids), MachinePower.year_number.between(start_year, end_year))
        .group_by(RegionalEnergySystem.id_union_energy_system, TesType.id, MachinePower.year_number)
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for row in rows:
        ues, tes, year = row.union_energy_system_id, row.tes_type_id, row.year
        p_ust[ues][tes][year] = row.p_ust or Decimal(0)
        p_ogr[ues][tes][year] = row.p_ogr or Decimal(0)
        p_rasp[ues][tes][year] = row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}



def aggregate_union_energy_systems_by_tes_types_with_fuel(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            RegionalEnergySystem.id_union_energy_system.label("union_energy_system_id"),
            TesType.id.label("tes_type_id"),
            FuelType.id.label("fuel_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(MachineTesType, and_(MachineTesType.id_machine == Machine.id, MachineTesType.year_number == MachinePower.year_number))
        .join(TesType, TesType.id == MachineTesType.id_tes_type)
        .join(MachineFuel, and_(MachineFuel.id_machine == Machine.id, MachineFuel.year_number == MachinePower.year_number))
        .join(Fuel, Fuel.id == MachineFuel.id_fuel)
        .join(FuelType, Fuel.id_fuel_type == FuelType.id)
        .join(Station, Station.id == Machine.id_station)
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .filter(Station.id.in_(station_ids), MachinePower.year_number.between(start_year, end_year))
        .group_by(RegionalEnergySystem.id_union_energy_system, TesType.id, FuelType.id, MachinePower.year_number)
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for row in rows:
        ues, tes, fuel, year = row.union_energy_system_id, row.tes_type_id, row.fuel_type_id, row.year
        p_ust[ues][tes][fuel][year] = row.p_ust or Decimal(0)
        p_ogr[ues][tes][fuel][year] = row.p_ogr or Decimal(0)
        p_rasp[ues][tes][fuel][year] = row.p_rasp or Decimal(0)

    return {"aggregated": {"p_ust": p_ust, "p_ogr": p_ogr, "p_rasp": p_rasp}}



def aggregate_union_energy_systems_by_tes_machine_types(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            RegionalEnergySystem.id_union_energy_system.label("union_energy_system_id"),
            TesType.id.label("tes_type_id"),
            TesMachineType.id.label("tes_machine_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(MachineTesType, and_(MachineTesType.id_machine == Machine.id, MachineTesType.year_number == MachinePower.year_number))
        .join(TesType, TesType.id == MachineTesType.id_tes_type)
        .join(TesMachineType, TesMachineType.id == Machine.id_tes_machine_type)
        .join(Station, Station.id == Machine.id_station)
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .filter(Station.id.in_(station_ids), MachinePower.year_number.between(start_year, end_year))
        .group_by(RegionalEnergySystem.id_union_energy_system, TesType.id, TesMachineType.id, MachinePower.year_number)
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for row in rows:
        ues, tes, machine_type, year = row.union_energy_system_id, row.tes_type_id, row.tes_machine_type_id, row.year
        p_ust[ues][tes][machine_type][year] = row.p_ust or Decimal(0)
        p_ogr[ues][tes][machine_type][year] = row.p_ogr or Decimal(0)
        p_rasp[ues][tes][machine_type][year] = row.p_rasp or Decimal(0)

    return {
        "aggregated": {
            "p_ust": p_ust,
            "p_ogr": p_ogr,
            "p_rasp": p_rasp,
        }
    }



def aggregate_union_energy_systems_by_tes_machine_types_with_fuel(start_year, end_year, station_ids):
    rows = (
        db.session.query(
            RegionalEnergySystem.id_union_energy_system.label("union_energy_system_id"),
            TesType.id.label("tes_type_id"),
            TesMachineType.id.label("tes_machine_type_id"),
            FuelType.id.label("fuel_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(MachineTesType, and_(MachineTesType.id_machine == Machine.id, MachineTesType.year_number == MachinePower.year_number))
        .join(TesType, TesType.id == MachineTesType.id_tes_type)
        .join(TesMachineType, TesMachineType.id == Machine.id_tes_machine_type)
        .join(MachineFuel, and_(MachineFuel.id_machine == Machine.id, MachineFuel.year_number == MachinePower.year_number))
        .join(Fuel, Fuel.id == MachineFuel.id_fuel)
        .join(FuelType, FuelType.id == Fuel.id_fuel_type)
        .join(Station, Station.id == Machine.id_station)
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .filter(Station.id.in_(station_ids), MachinePower.year_number.between(start_year, end_year))
        .group_by(RegionalEnergySystem.id_union_energy_system, TesType.id, TesMachineType.id, FuelType.id, MachinePower.year_number)
        .all()
    )

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))

    for row in rows:
        ues, tes, machine_type, fuel, year = row.union_energy_system_id, row.tes_type_id, row.tes_machine_type_id, row.fuel_type_id, row.year
        p_ust[ues][tes][machine_type][fuel][year] = row.p_ust or Decimal(0)
        p_ogr[ues][tes][machine_type][fuel][year] = row.p_ogr or Decimal(0)
        p_rasp[ues][tes][machine_type][fuel][year] = row.p_rasp or Decimal(0)

    return {
        "aggregated": {
            "p_ust": p_ust,
            "p_ogr": p_ogr,
            "p_rasp": p_rasp,
        }
    }


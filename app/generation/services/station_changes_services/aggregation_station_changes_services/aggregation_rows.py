from sqlalchemy import func, and_
from app.extensions import db
from types import SimpleNamespace
from decimal import Decimal
from app.generation.models.station.station_model import Station
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.machine.machine_tes_type_model import MachineTesType
from app.generation.models.machine.machine_fuel_model import MachineFuel
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.refdata_for_stations.machine.tes_type_model import TesType
from app.refdata.models.refdata_for_stations.machine.tes_machine_type_model import TesMachineType
from app.refdata.models.fuels.fuel_type_model import FuelType
from app.refdata.models.fuels.fuel_model import Fuel


def get_tes_type_id(machine, year):
    for rel in machine.machine_tes_types:
        if rel.year_number == year and rel.tes_type:
            return rel.tes_type.id
    return None


def get_fuel_type_id(machine, year):
    for rel in machine.machine_fuels:
        if rel.year_number == year and rel.fuel and rel.fuel.fuel_type:
            return rel.fuel.fuel_type.id
    return None


def get_res_id(machine):
    rd = getattr(machine.machine_station, "regional_district", None)
    if rd and rd.regional_energy_systems:
        return rd.regional_energy_systems[0].id
    return None


def get_ues_id(machine):
    res_list = getattr(machine.machine_station.regional_district, "regional_energy_systems", [])
    for res in res_list:
        if res.union_energy_system:
            return res.union_energy_system.id
    return None


def get_energy_system_type_id(machine):
    res_list = getattr(machine.machine_station.regional_district, "regional_energy_systems", [])
    for res in res_list:
        if res.union_energy_system and res.union_energy_system.energy_system_type:
            return res.union_energy_system.energy_system_type.id
    return None


def get_full_aggregation_rows(machines):
    rows = []

    for m in machines:
        if not m.event_types:
            continue

        station = m.machine_station
        regional_district = station.regional_district if station else None

        for p in m.powers_by_year:
            year = p["year"]
            p_ust = Decimal(p["p_ust"])

            rows.append(SimpleNamespace(
                energy_system_type_id=get_energy_system_type_id(m),
                union_energy_system_id=get_ues_id(m),
                regional_energy_system_id=get_res_id(m),
                regional_district_id=regional_district.id if regional_district else None,
                energy_unit_id=station.id_energy_unit if station else None,
                station_type_id=m.id_station_type,
                tes_type_id=get_tes_type_id(m, year),
                tes_machine_type_id=m.id_tes_machine_type,
                fuel_type_id=get_fuel_type_id(m, year),
                year=year,
                p_ust=p_ust,
                event_type=m.event_types,
            ))

    return rows


def get_full_aggregation_rows_old(start_year, end_year, station_ids, machine_ids=None):
    query = (
        db.session.query(
            EnergySystemType.id.label("energy_system_type_id"),
            UnionEnergySystem.id.label("union_energy_system_id"),
            RegionalEnergySystem.id.label("regional_energy_system_id"),
            RegionalDistrict.id.label("regional_district_id"),
            Station.id_energy_unit.label("energy_unit_id"),
            Machine.id_station_type.label("station_type_id"),
            TesType.id.label("tes_type_id"),
            TesMachineType.id.label("tes_machine_type_id"),
            FuelType.id.label("fuel_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
        )
        .select_from(MachinePower)
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(Station, Station.id == Machine.id_station)
        .outerjoin(MachineTesType, MachineTesType.id_machine == Machine.id)
        .outerjoin(TesType, TesType.id == MachineTesType.id_tes_type)
        .outerjoin(TesMachineType, TesMachineType.id == Machine.id_tes_machine_type)
        .outerjoin(MachineFuel, MachineFuel.id_machine == Machine.id)
        .outerjoin(Fuel, Fuel.id == MachineFuel.id_fuel)
        .outerjoin(FuelType, FuelType.id == Fuel.id_fuel_type)
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .join(RegionalEnergySystem.union_energy_system)
        .join(UnionEnergySystem.energy_system_type)
        .filter(
            Station.id.in_(station_ids),
            MachinePower.year_number.between(start_year, end_year)
        )
    )

    if machine_ids:
        query = query.filter(Machine.id.in_(machine_ids))

    query = query.group_by(
        EnergySystemType.id,
        UnionEnergySystem.id,
        RegionalEnergySystem.id,
        RegionalDistrict.id,
        Station.id_energy_unit,
        Machine.id_station_type,
        TesType.id,
        TesMachineType.id,
        FuelType.id,
        MachinePower.year_number
    )

    return query.all()


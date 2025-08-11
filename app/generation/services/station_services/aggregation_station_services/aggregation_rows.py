from sqlalchemy import func, and_
from app.extensions import db
from app.logs.models.logs_models import *
from app.refdata.models.energy_systems_models import *
from app.refdata.models.territories_models import *
from app.refdata.models.fuels_models import *
from app.refdata.models.gen_companies_models import *
from app.refdata.models.stations_refdata_models import *
from app.generation.models.stations_models import *
from app.generation.models.machines_models import *
from app.generation.models.pgu_machines_models import *
from app.generation.models.boilers_models import *

def get_full_aggregation_rows(start_year, end_year, station_ids):
    rows = (
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
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .select_from(MachinePower)
        .join(Machine, Machine.id == MachinePower.id_machine)
        .join(Station, Station.id == Machine.id_station)
        .outerjoin(MachineTesType, and_(
            MachineTesType.id_machine == Machine.id,
            MachineTesType.year_number == MachinePower.year_number
        ))
        .outerjoin(TesType, TesType.id == MachineTesType.id_tes_type)
        .outerjoin(TesMachineType, TesMachineType.id == Machine.id_tes_machine_type)
        .outerjoin(MachineFuel, and_(
            MachineFuel.id_machine == Machine.id,
            MachineFuel.year_number == MachinePower.year_number
        ))
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
        .group_by(
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
        .all()
    )
    return rows

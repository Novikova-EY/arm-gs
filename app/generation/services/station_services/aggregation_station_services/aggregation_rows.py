from sqlalchemy import func, and_
from app.extensions import db
from app.generation.models.station.station_model import Station
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.machine.machine_fuel_model import MachineFuel
from app.generation.models.machine.machine_tes_type_model import MachineTesType
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.refdata.models.fuels.fuel_model import Fuel
from app.refdata.models.fuels.fuel_type_model import FuelType
from app.refdata.models.refdata_for_stations.machine.tes_machine_type_model import TesMachineType
from app.refdata.models.refdata_for_stations.machine.tes_type_model import TesType
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.generation.services.station_services.aggregation_cache import cache_aggregation


@cache_aggregation
def get_full_aggregation_rows(start_year, end_year, station_ids, filters=None):
    if filters is None:
        filters = {}
    
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
    )
    
    # Применяем фильтры по машинам
    if filters.get("tes_type_filter"):
        query = query.filter(TesType.id.in_(filters["tes_type_filter"]))
    
    if filters.get("tes_machine_type_filter"):
        query = query.filter(Machine.id_tes_machine_type.in_(filters["tes_machine_type_filter"]))
    
    if filters.get("fuel_type_filter"):
        query = query.filter(FuelType.id.in_(filters["fuel_type_filter"]))
    
    if filters.get("condition_type_filter"):
        query = query.filter(Machine.id_condition_type == filters["condition_type_filter"])
    
    if filters.get("date_exploitation_filter"):
        query = query.filter(Machine.date_exploitation.in_(filters["date_exploitation_filter"]))
    
    if filters.get("date_decompressing_expected_filter"):
        query = query.filter(Machine.date_decompressing_expected.in_(filters["date_decompressing_expected_filter"]))
    
    if filters.get("date_modernization_expected_filter"):
        query = query.filter(Machine.date_modernization_expected.in_(filters["date_modernization_expected_filter"]))
    
    # Применяем фильтры по станции
    if filters.get("station_type_filter"):
        query = query.filter(Station.id_station_type.in_(filters["station_type_filter"]))
    
    if filters.get("station_name_filter"):
        query = query.filter(Station.name.ilike(f"%{filters['station_name_filter']}%"))
    
    # Фильтр по компании - требует join с GenCompany
    if filters.get("gen_company_filter"):
        from app.refdata.models.gen_companies.gen_company_model import GenCompany
        query = query.join(Machine.gen_company).filter(
            GenCompany.name.ilike(f"%{filters['gen_company_filter']}%")
        )
    
    rows = query.group_by(
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
    ).all()
    
    return rows

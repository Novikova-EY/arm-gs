from sqlalchemy import func, and_, literal, case, or_
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
from app.common.services.get_services.stations.tes_type_get_services import (
    get_unknown_tes_type_id,
)
from app.common.services.database_version_filter import filter_by_db_version


@cache_aggregation
def get_full_aggregation_rows(start_year, end_year, station_ids, filters=None):
    if filters is None:
        filters = {}

    unknown_tes_type_id = get_unknown_tes_type_id()
    unknown_literal = literal(unknown_tes_type_id)
    tes_type_base_expr = case(
        (TesType.id == 0, unknown_literal),
        else_=func.coalesce(TesType.id, unknown_literal),
    )

    def _labeled_tes_type_expr():
        return tes_type_base_expr.label("tes_type_id")

    # ---------------- Обычные агрегаты (машины) ----------------
    # Разделяем выборку на 2 части:
    # 1) Станции с прямой связью с РЭС (Station.id_regional_energy_system IS NOT NULL)
    # 2) Остальные станции — через субъект РФ, как в старой логике

    # 1) Прямая связь станции с РЭС
    query_direct = (
        db.session.query(
            EnergySystemType.id.label("energy_system_type_id"),
            UnionEnergySystem.id.label("union_energy_system_id"),
            RegionalEnergySystem.id.label("regional_energy_system_id"),
            RegionalDistrict.id.label("regional_district_id"),
            Station.id_energy_unit.label("energy_unit_id"),
            Station.id_station_type.label("station_type_id"),
            _labeled_tes_type_expr(),
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
        # Территориальная иерархия (субъект РФ можем взять, если есть)
        .outerjoin(Station.regional_district)
        # Иерархия РЭС/ОЭС/типов энергосистем по прямой связи
        .join(RegionalEnergySystem, RegionalEnergySystem.id == Station.id_regional_energy_system)
        .join(UnionEnergySystem, UnionEnergySystem.id == RegionalEnergySystem.id_union_energy_system)
        .join(EnergySystemType, EnergySystemType.id == UnionEnergySystem.id_energy_system_type)
        .filter(
            Station.id.in_(station_ids),
            Station.id_regional_energy_system.isnot(None),
            MachinePower.year_number.between(start_year, end_year),
        )
    )

    # Фильтрация по текущей версии БД
    query_direct = filter_by_db_version(query_direct, Station)
    query_direct = filter_by_db_version(query_direct, RegionalDistrict)
    query_direct = filter_by_db_version(query_direct, RegionalEnergySystem)
    query_direct = filter_by_db_version(query_direct, UnionEnergySystem)
    query_direct = filter_by_db_version(query_direct, EnergySystemType)

    # 2) Связь через субъект РФ (fallback для станций без прямой РЭС)
    query_via_district = (
        db.session.query(
            EnergySystemType.id.label("energy_system_type_id"),
            UnionEnergySystem.id.label("union_energy_system_id"),
            RegionalEnergySystem.id.label("regional_energy_system_id"),
            RegionalDistrict.id.label("regional_district_id"),
            Station.id_energy_unit.label("energy_unit_id"),
            Station.id_station_type.label("station_type_id"),
            _labeled_tes_type_expr(),
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
        # Старый путь: через субъект РФ и M2M связь с РЭС
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .join(RegionalEnergySystem.union_energy_system)
        .join(UnionEnergySystem.energy_system_type)
        .filter(
            Station.id.in_(station_ids),
            Station.id_regional_energy_system.is_(None),
            MachinePower.year_number.between(start_year, end_year),
        )
    )

    # Фильтрация по текущей версии БД
    query_via_district = filter_by_db_version(query_via_district, Station)
    query_via_district = filter_by_db_version(query_via_district, RegionalDistrict)
    query_via_district = filter_by_db_version(query_via_district, RegionalEnergySystem)
    query_via_district = filter_by_db_version(query_via_district, UnionEnergySystem)
    query_via_district = filter_by_db_version(query_via_district, EnergySystemType)

    # Общие фильтры по машинам (для обеих частей)
    if filters.get("tes_type_filter"):
        query_direct = query_direct.filter(TesType.id.in_(filters["tes_type_filter"]))
        query_via_district = query_via_district.filter(TesType.id.in_(filters["tes_type_filter"]))

    if filters.get("tes_machine_type_filter"):
        query_direct = query_direct.filter(Machine.id_tes_machine_type.in_(filters["tes_machine_type_filter"]))
        query_via_district = query_via_district.filter(Machine.id_tes_machine_type.in_(filters["tes_machine_type_filter"]))

    if filters.get("fuel_type_filter"):
        query_direct = query_direct.filter(FuelType.id.in_(filters["fuel_type_filter"]))
        query_via_district = query_via_district.filter(FuelType.id.in_(filters["fuel_type_filter"]))

    if filters.get("condition_type_filter"):
        query_direct = query_direct.filter(Machine.id_condition_type == filters["condition_type_filter"])
        query_via_district = query_via_district.filter(Machine.id_condition_type == filters["condition_type_filter"])

    if filters.get("date_exploitation_filter"):
        query_direct = query_direct.filter(
            or_(
                Machine.date_exploitation.in_(filters["date_exploitation_filter"]),
                Machine.date_exploitation_expected.in_(filters["date_exploitation_filter"]),
            )
        )
        query_via_district = query_via_district.filter(
            or_(
                Machine.date_exploitation.in_(filters["date_exploitation_filter"]),
                Machine.date_exploitation_expected.in_(filters["date_exploitation_filter"]),
            )
        )

    if filters.get("date_decompressing_expected_filter"):
        query_direct = query_direct.filter(Machine.date_decompressing_expected.in_(filters["date_decompressing_expected_filter"]))
        query_via_district = query_via_district.filter(Machine.date_decompressing_expected.in_(filters["date_decompressing_expected_filter"]))

    if filters.get("date_modernization_expected_filter"):
        query_direct = query_direct.filter(Machine.date_modernization_expected.in_(filters["date_modernization_expected_filter"]))
        query_via_district = query_via_district.filter(Machine.date_modernization_expected.in_(filters["date_modernization_expected_filter"]))

    # Применяем фильтры по станции
    if filters.get("station_type_filter"):
        query_direct = query_direct.filter(Station.id_station_type.in_(filters["station_type_filter"]))
        query_via_district = query_via_district.filter(Station.id_station_type.in_(filters["station_type_filter"]))

    if filters.get("station_name_filter"):
        name_filter = f"%{filters['station_name_filter']}%"
        query_direct = query_direct.filter(Station.name.ilike(name_filter))
        query_via_district = query_via_district.filter(Station.name.ilike(name_filter))

    # Фильтр по компании - требует join с GenCompany
    if filters.get("gen_company_filter"):
        from app.refdata.models.gen_companies.gen_company_model import GenCompany
        name_filter = f"%{filters['gen_company_filter']}%"
        query_direct = query_direct.join(Machine.gen_company).filter(GenCompany.name.ilike(name_filter))
        query_via_district = query_via_district.join(Machine.gen_company).filter(GenCompany.name.ilike(name_filter))

    rows_regular_direct = query_direct.group_by(
        EnergySystemType.id,
        UnionEnergySystem.id,
        RegionalEnergySystem.id,
        RegionalDistrict.id,
        Station.id_energy_unit,
        Station.id_station_type,
        tes_type_base_expr,
        TesMachineType.id,
        FuelType.id,
        MachinePower.year_number,
    ).all()

    rows_regular_via = query_via_district.group_by(
        EnergySystemType.id,
        UnionEnergySystem.id,
        RegionalEnergySystem.id,
        RegionalDistrict.id,
        Station.id_energy_unit,
        Station.id_station_type,
        tes_type_base_expr,
        TesMachineType.id,
        FuelType.id,
        MachinePower.year_number,
    ).all()

    rows_regular = rows_regular_direct + rows_regular_via

    # ПГУ агрегаты (компоненты ПГУ)
    # Берём мощности из PGUMachinePower и маппим измерения через родительскую машину/станцию.
    from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
    from app.generation.models.pgu_machine.pgu_machine_power_model import PGUMachinePower

    # ---------------- ПГУ агрегаты (компоненты ПГУ) ----------------
    # Аналогично делим на прямую связь с РЭС и fallback через субъект.
    from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
    from app.generation.models.pgu_machine.pgu_machine_power_model import PGUMachinePower

    # 1) Прямая связь станции с РЭС для ПГУ
    pgu_query_direct = (
        db.session.query(
            EnergySystemType.id.label("energy_system_type_id"),
            UnionEnergySystem.id.label("union_energy_system_id"),
            RegionalEnergySystem.id.label("regional_energy_system_id"),
            RegionalDistrict.id.label("regional_district_id"),
            Station.id_energy_unit.label("energy_unit_id"),
            Station.id_station_type.label("station_type_id"),
            _labeled_tes_type_expr(),
            TesMachineType.id.label("tes_machine_type_id"),
            FuelType.id.label("fuel_type_id"),
            PGUMachinePower.year_number.label("year"),
            func.sum(PGUMachinePower.p_ust).label("p_ust"),
            func.sum(literal(0)).label("p_ogr"),
            func.sum(literal(0)).label("p_rasp"),
        )
        .select_from(PGUMachinePower)
        .join(PGUMachine, PGUMachine.id == PGUMachinePower.id_pgu_machine)
        # Родительская обычная машина, чтобы дотянуться до станции и связей
        .join(Machine, Machine.id == PGUMachine.id_parent_machine)
        .join(Station, Station.id == Machine.id_station)
        .outerjoin(MachineTesType, and_(
            MachineTesType.id_machine == Machine.id,
            MachineTesType.year_number == PGUMachinePower.year_number
        ))
        .outerjoin(TesType, TesType.id == MachineTesType.id_tes_type)
        .outerjoin(TesMachineType, TesMachineType.id == PGUMachine.id_tes_machine_type)
        .outerjoin(MachineFuel, and_(
            MachineFuel.id_machine == Machine.id,
            MachineFuel.year_number == PGUMachinePower.year_number
        ))
        .outerjoin(Fuel, Fuel.id == MachineFuel.id_fuel)
        .outerjoin(FuelType, FuelType.id == Fuel.id_fuel_type)
        .outerjoin(Station.regional_district)
        .join(RegionalEnergySystem, RegionalEnergySystem.id == Station.id_regional_energy_system)
        .join(UnionEnergySystem, UnionEnergySystem.id == RegionalEnergySystem.id_union_energy_system)
        .join(EnergySystemType, EnergySystemType.id == UnionEnergySystem.id_energy_system_type)
        .filter(
            Station.id.in_(station_ids),
            Station.id_regional_energy_system.isnot(None),
            PGUMachinePower.year_number.between(start_year, end_year),
        )
    )

    pgu_query_direct = filter_by_db_version(pgu_query_direct, Station)
    pgu_query_direct = filter_by_db_version(pgu_query_direct, RegionalDistrict)
    pgu_query_direct = filter_by_db_version(pgu_query_direct, RegionalEnergySystem)
    pgu_query_direct = filter_by_db_version(pgu_query_direct, UnionEnergySystem)
    pgu_query_direct = filter_by_db_version(pgu_query_direct, EnergySystemType)

    # 2) Fallback через субъект РФ для ПГУ
    pgu_query_via_district = (
        db.session.query(
            EnergySystemType.id.label("energy_system_type_id"),
            UnionEnergySystem.id.label("union_energy_system_id"),
            RegionalEnergySystem.id.label("regional_energy_system_id"),
            RegionalDistrict.id.label("regional_district_id"),
            Station.id_energy_unit.label("energy_unit_id"),
            Station.id_station_type.label("station_type_id"),
            _labeled_tes_type_expr(),
            TesMachineType.id.label("tes_machine_type_id"),
            FuelType.id.label("fuel_type_id"),
            PGUMachinePower.year_number.label("year"),
            func.sum(PGUMachinePower.p_ust).label("p_ust"),
            func.sum(literal(0)).label("p_ogr"),
            func.sum(literal(0)).label("p_rasp"),
        )
        .select_from(PGUMachinePower)
        .join(PGUMachine, PGUMachine.id == PGUMachinePower.id_pgu_machine)
        .join(Machine, Machine.id == PGUMachine.id_parent_machine)
        .join(Station, Station.id == Machine.id_station)
        .outerjoin(MachineTesType, and_(
            MachineTesType.id_machine == Machine.id,
            MachineTesType.year_number == PGUMachinePower.year_number
        ))
        .outerjoin(TesType, TesType.id == MachineTesType.id_tes_type)
        .outerjoin(TesMachineType, TesMachineType.id == PGUMachine.id_tes_machine_type)
        .outerjoin(MachineFuel, and_(
            MachineFuel.id_machine == Machine.id,
            MachineFuel.year_number == PGUMachinePower.year_number
        ))
        .outerjoin(Fuel, Fuel.id == MachineFuel.id_fuel)
        .outerjoin(FuelType, FuelType.id == Fuel.id_fuel_type)
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .join(RegionalEnergySystem.union_energy_system)
        .join(UnionEnergySystem.energy_system_type)
        .filter(
            Station.id.in_(station_ids),
            Station.id_regional_energy_system.is_(None),
            PGUMachinePower.year_number.between(start_year, end_year),
        )
    )

    pgu_query_via_district = filter_by_db_version(pgu_query_via_district, Station)
    pgu_query_via_district = filter_by_db_version(pgu_query_via_district, RegionalDistrict)
    pgu_query_via_district = filter_by_db_version(pgu_query_via_district, RegionalEnergySystem)
    pgu_query_via_district = filter_by_db_version(pgu_query_via_district, UnionEnergySystem)
    pgu_query_via_district = filter_by_db_version(pgu_query_via_district, EnergySystemType)

    # Те же фильтры, что и для обычных агрегатов
    if filters.get("tes_type_filter"):
        pgu_query_direct = pgu_query_direct.filter(TesType.id.in_(filters["tes_type_filter"]))
        pgu_query_via_district = pgu_query_via_district.filter(TesType.id.in_(filters["tes_type_filter"]))

    if filters.get("tes_machine_type_filter"):
        pgu_query_direct = pgu_query_direct.filter(TesMachineType.id.in_(filters["tes_machine_type_filter"]))
        pgu_query_via_district = pgu_query_via_district.filter(TesMachineType.id.in_(filters["tes_machine_type_filter"]))

    if filters.get("fuel_type_filter"):
        pgu_query_direct = pgu_query_direct.filter(FuelType.id.in_(filters["fuel_type_filter"]))
        pgu_query_via_district = pgu_query_via_district.filter(FuelType.id.in_(filters["fuel_type_filter"]))

    if filters.get("condition_type_filter"):
        pgu_query_direct = pgu_query_direct.filter(PGUMachine.id_condition_type == filters["condition_type_filter"])
        pgu_query_via_district = pgu_query_via_district.filter(PGUMachine.id_condition_type == filters["condition_type_filter"])

    if filters.get("date_exploitation_filter"):
        pgu_query_direct = pgu_query_direct.filter(PGUMachine.date_exploitation.in_(filters["date_exploitation_filter"]))
        pgu_query_via_district = pgu_query_via_district.filter(PGUMachine.date_exploitation.in_(filters["date_exploitation_filter"]))

    if filters.get("date_decompressing_expected_filter"):
        pgu_query_direct = pgu_query_direct.filter(PGUMachine.date_decompressing_expected.in_(filters["date_decompressing_expected_filter"]))
        pgu_query_via_district = pgu_query_via_district.filter(PGUMachine.date_decompressing_expected.in_(filters["date_decompressing_expected_filter"]))

    if filters.get("date_modernization_expected_filter"):
        pgu_query_direct = pgu_query_direct.filter(PGUMachine.date_modernization_expected.in_(filters["date_modernization_expected_filter"]))
        pgu_query_via_district = pgu_query_via_district.filter(PGUMachine.date_modernization_expected.in_(filters["date_modernization_expected_filter"]))

    rows_pgu_direct = pgu_query_direct.group_by(
        EnergySystemType.id,
        UnionEnergySystem.id,
        RegionalEnergySystem.id,
        RegionalDistrict.id,
        Station.id_energy_unit,
        Station.id_station_type,
        tes_type_base_expr,
        TesMachineType.id,
        FuelType.id,
        PGUMachinePower.year_number,
    ).all()

    rows_pgu_via = pgu_query_via_district.group_by(
        EnergySystemType.id,
        UnionEnergySystem.id,
        RegionalEnergySystem.id,
        RegionalDistrict.id,
        Station.id_energy_unit,
        Station.id_station_type,
        tes_type_base_expr,
        TesMachineType.id,
        FuelType.id,
        PGUMachinePower.year_number,
    ).all()

    rows_pgu = rows_pgu_direct + rows_pgu_via

    # Объединяем обычные машины и ПГУ-компоненты
    return rows_regular + rows_pgu

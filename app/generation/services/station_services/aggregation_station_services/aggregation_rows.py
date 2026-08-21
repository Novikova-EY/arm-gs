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
from app.common.services.database_version_filter import filter_by_db_version, get_current_db_version_id


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

    current_version_id = get_current_db_version_id()

    def _version_cond(model_cls):
        """
        Условие по database_version_id для join'ов:
        - если версия выбрана -> только эта версия
        - если версия не выбрана -> только NULL
        """
        if not hasattr(model_cls, "database_version_id"):
            return literal(True)
        if current_version_id is None:
            return model_cls.database_version_id.is_(None)
        return model_cls.database_version_id == current_version_id

    def _version_cond_power(model_cls):
        """
        Условие для MachinePower/PGUMachinePower: версия или NULL.
        Родитель (Machine) уже отфильтрован по версии, поэтому NULL в дочерней
        таблице считаем legacy-данными той же версии.
        """
        if not hasattr(model_cls, "database_version_id"):
            return literal(True)
        if current_version_id is None:
            return model_cls.database_version_id.is_(None)
        return or_(
            model_cls.database_version_id == current_version_id,
            model_cls.database_version_id.is_(None),
        )

    # ---------------- Обычные агрегаты (машины) ----------------
    # Разделяем выборку на 2 части:
    # 1) электростанции с прямой связью с РЭС (Station.id_regional_energy_system IS NOT NULL)
    # 2) Остальные электростанции — через субъект РФ, как в старой логике

    # 1) Прямая связь электростанции с РЭС
    query_direct = (
        db.session.query(
            EnergySystemType.id.label("energy_system_type_id"),
            UnionEnergySystem.id.label("union_energy_system_id"),
            RegionalEnergySystem.id.label("regional_energy_system_id"),
            RegionalDistrict.id.label("regional_district_id"),
            RegionalDistrict.id_federal_district.label("federal_district_id"),
            RegionalDistrict.id_synchronous_area.label("synchronous_area_id"),
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
        .join(Machine, and_(Machine.id == MachinePower.id_machine, _version_cond(Machine)))
        .join(Station, and_(Station.id == Machine.id_station, _version_cond(Station)))
        .outerjoin(
            MachineTesType,
            and_(
                MachineTesType.id_machine == Machine.id,
                MachineTesType.year_number == MachinePower.year_number,
                _version_cond(MachineTesType),
            ),
        )
        .outerjoin(TesType, and_(TesType.id == MachineTesType.id_tes_type, _version_cond(TesType)))
        .outerjoin(TesMachineType, and_(TesMachineType.id == Machine.id_tes_machine_type, _version_cond(TesMachineType)))
        .outerjoin(
            MachineFuel,
            and_(
                MachineFuel.id_machine == Machine.id,
                MachineFuel.year_number == MachinePower.year_number,
                _version_cond(MachineFuel),
            ),
        )
        .outerjoin(Fuel, and_(Fuel.id == MachineFuel.id_fuel, _version_cond(Fuel)))
        .outerjoin(FuelType, and_(FuelType.id == Fuel.id_fuel_type, _version_cond(FuelType)))
        # Территориальная иерархия (субъект РФ можем взять, если есть)
        .outerjoin(Station.regional_district)
        # Иерархия РЭС/ОЭС/типов энергосистем по прямой связи
        .join(RegionalEnergySystem, RegionalEnergySystem.id == Station.id_regional_energy_system)
        .join(UnionEnergySystem, UnionEnergySystem.id == RegionalEnergySystem.id_union_energy_system)
        .join(EnergySystemType, EnergySystemType.id == UnionEnergySystem.id_energy_system_type)
        .filter(
            Station.id.in_(station_ids),
            Station.id_regional_energy_system.isnot(None),
            Machine.is_archived.isnot(True),
            MachinePower.year_number.between(start_year, end_year),
            _version_cond_power(MachinePower),
        )
    )

    # Фильтрация по текущей версии БД.
    # Региональные справочники (РЭС, ОЭС, типы) не фильтруем — они общие,
    # Station.id_regional_energy_system ссылается на них независимо от версии.
    query_direct = filter_by_db_version(query_direct, Station)

    # 2) Связь через субъект РФ (fallback для станций без прямой РЭС)
    query_via_district = (
        db.session.query(
            EnergySystemType.id.label("energy_system_type_id"),
            UnionEnergySystem.id.label("union_energy_system_id"),
            RegionalEnergySystem.id.label("regional_energy_system_id"),
            RegionalDistrict.id.label("regional_district_id"),
            RegionalDistrict.id_federal_district.label("federal_district_id"),
            RegionalDistrict.id_synchronous_area.label("synchronous_area_id"),
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
        .join(Machine, and_(Machine.id == MachinePower.id_machine, _version_cond(Machine)))
        .join(Station, and_(Station.id == Machine.id_station, _version_cond(Station)))
        .outerjoin(
            MachineTesType,
            and_(
                MachineTesType.id_machine == Machine.id,
                MachineTesType.year_number == MachinePower.year_number,
                _version_cond(MachineTesType),
            ),
        )
        .outerjoin(TesType, and_(TesType.id == MachineTesType.id_tes_type, _version_cond(TesType)))
        .outerjoin(TesMachineType, and_(TesMachineType.id == Machine.id_tes_machine_type, _version_cond(TesMachineType)))
        .outerjoin(
            MachineFuel,
            and_(
                MachineFuel.id_machine == Machine.id,
                MachineFuel.year_number == MachinePower.year_number,
                _version_cond(MachineFuel),
            ),
        )
        .outerjoin(Fuel, and_(Fuel.id == MachineFuel.id_fuel, _version_cond(Fuel)))
        .outerjoin(FuelType, and_(FuelType.id == Fuel.id_fuel_type, _version_cond(FuelType)))
        # Старый путь: через субъект РФ и M2M связь с РЭС
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .join(RegionalEnergySystem.union_energy_system)
        .join(UnionEnergySystem.energy_system_type)
        .filter(
            Station.id.in_(station_ids),
            Station.id_regional_energy_system.is_(None),
            Machine.is_archived.isnot(True),
            MachinePower.year_number.between(start_year, end_year),
            _version_cond_power(MachinePower),
        )
    )

    # Фильтрация по текущей версии БД (территориальные справочники не фильтруем — см. query_direct)
    query_via_district = filter_by_db_version(query_via_district, Station)

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

    if filters.get("machines_without_equipment_group"):
        from app.generation.services.station_services.filters_services import (
            build_machines_without_equipment_group_filter,
        )

        without_group = build_machines_without_equipment_group_filter(Machine)
        query_direct = query_direct.filter(without_group)
        query_via_district = query_via_district.filter(without_group)

    from app.generation.services.station_services.filters_services import (
        build_date_commission_filter,
        build_date_exploitation_filter,
        build_date_decompressing_filter,
        build_date_modernization_filter,
        build_date_modernization_no_power_filter,
        build_relabing_outcome_filter,
    )
    for build_fn in (
        build_date_commission_filter,
        build_date_exploitation_filter,
        build_date_decompressing_filter,
        build_date_modernization_filter,
        build_date_modernization_no_power_filter,
        build_relabing_outcome_filter,
    ):
        cond = build_fn(Machine, filters)
        if cond is not None:
            query_direct = query_direct.filter(cond)
            query_via_district = query_via_district.filter(cond)

    # Проверка топлива (должно совпадать с логикой station_list):
    # показываем строки только для "проблемных" агрегатов:
    # - fuel_so пустое, но топливо по годам задано, ИЛИ
    # - fuel_so заполнено, но не совпадает с топливом по годам (по строке/году).
    if filters.get("fuel_check"):
        current_version_id = get_current_db_version_id()
        if current_version_id is not None:
            mf_version_cond = MachineFuel.database_version_id == current_version_id
        else:
            mf_version_cond = MachineFuel.database_version_id.is_(None)

        fuel_so_missing = or_(
            Machine.fuel_so.is_(None),
            func.trim(Machine.fuel_so) == "",
            func.lower(func.trim(Machine.fuel_so)) == "не указано",
        )

        fuel_type_valid = and_(
            FuelType.id.isnot(None),
            func.lower(FuelType.name) != "не указано",
        )
        # "Мягкое" сравнение (fuel_so может содержать несколько видов топлива)
        match_row_fuel = func.strpos(
            func.lower(func.coalesce(Machine.fuel_so, "")),
            func.lower(FuelType.name),
        ) > 0

        query_direct = query_direct.filter(
            and_(
                mf_version_cond,
                fuel_type_valid,
                or_(fuel_so_missing, ~match_row_fuel),
            )
        )
        query_via_district = query_via_district.filter(
            and_(
                mf_version_cond,
                fuel_type_valid,
                or_(fuel_so_missing, ~match_row_fuel),
            )
        )

    # Применяем фильтры по электростанции
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
        RegionalDistrict.id_federal_district,
        RegionalDistrict.id_synchronous_area,
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
        RegionalDistrict.id_federal_district,
        RegionalDistrict.id_synchronous_area,
        Station.id_energy_unit,
        Station.id_station_type,
        tes_type_base_expr,
        TesMachineType.id,
        FuelType.id,
        MachinePower.year_number,
    ).all()

    return rows_regular_direct + rows_regular_via

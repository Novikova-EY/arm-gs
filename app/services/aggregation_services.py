from sqlalchemy import func, and_
from collections import defaultdict
from decimal import Decimal
from sqlalchemy.orm import aliased
from app.models import (
    RegionalDistrict,
    RegionalEnergySystem,
    UnionEnergySystem,
    EnergySystemType,
    Station,
    Machine,
    MachineFuel,
    MachineTesType,
    MachinePower,
    Year,
    Fuel,
    FuelType,
    TesType,
    EnergyUnit,
    regional_district_regional_energy_system
)


def aggregate_power_by_level(session, join_model, join_condition, level_id_column, start_year, end_year, filters=None):
    query = (
        session.query(
            level_id_column.label("level_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .select_from(join_model)
        .join(Station, join_condition)
        .join(Machine, Machine.id_station == Station.id)
        .join(MachinePower, MachinePower.id_machine == Machine.id)
        .join(Year, MachinePower.year_number == Year.id)
        .filter(Year.number >= start_year, Year.number <= end_year)
        .group_by(level_id_column, Year.number)
    )

    if filters:
        query = query.filter(*filters)

    results = query.all()

    p_ust = defaultdict(lambda: defaultdict(Decimal))
    p_ogr = defaultdict(lambda: defaultdict(Decimal))
    p_rasp = defaultdict(lambda: defaultdict(Decimal))

    for row in results:
        p_ust[row.level_id][row.year] = row.p_ust or Decimal(0)
        p_ogr[row.level_id][row.year] = row.p_ogr or Decimal(0)
        p_rasp[row.level_id][row.year] = row.p_rasp or Decimal(0)

    return {
        'aggregated': {
            'p_ust': p_ust,
            'p_ogr': p_ogr,
            'p_rasp': p_rasp,
        }
    }


# Агрегация по энергоузлам
def aggregate_power_by_energy_unit(session, start_year, end_year, filters=None):
    query = (
        session.query(
            EnergyUnit.id.label("level_id"),
            Year.number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Station, Station.id_energy_unit == EnergyUnit.id)
        .join(Machine, Machine.id_station == Station.id)
        .join(MachinePower, MachinePower.id_machine == Machine.id)
        .join(Year, MachinePower.year_number == Year.number)
        .filter(Year.number >= start_year, Year.number <= end_year)
        .group_by(EnergyUnit.id, Year.number)
    )

    if filters:
        query = query.filter(*filters)

    results = query.all()

    p_ust = defaultdict(lambda: defaultdict(Decimal))
    p_ogr = defaultdict(lambda: defaultdict(Decimal))
    p_rasp = defaultdict(lambda: defaultdict(Decimal))

    for row in results:
        p_ust[row.level_id][row.year] = row.p_ust or Decimal(0)
        p_ogr[row.level_id][row.year] = row.p_ogr or Decimal(0)
        p_rasp[row.level_id][row.year] = row.p_rasp or Decimal(0)


    return {
        'aggregated': {
            'p_ust': p_ust,
            'p_ogr': p_ogr,
            'p_rasp': p_rasp,
        }
    }


# Агрегация по субъектам РФ
def aggregate_power_by_regional_district(session, start_year, end_year, filters=None):
    stations = session.query(Station.id, Station.id_regional_district).filter(
        Station.id_regional_district.isnot(None)
    ).all()
    station_ids = [s.id for s in stations]

    query = (
        session.query(
            Station.id_regional_district.label("level_id"),
            Year.number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id_station == Station.id)
        .join(MachinePower, MachinePower.id_machine == Machine.id)
        .join(Year, MachinePower.year_number == Year.number)
        .filter(Year.number >= start_year, Year.number <= end_year)
        .filter(
            Station.id.in_(station_ids),
            Year.number.between(start_year, end_year)
        )
        .group_by(Station.id_regional_district, Year.number)
    )

    if filters:
        query = query.filter(*filters)

    results = query.all()

    p_ust = defaultdict(lambda: defaultdict(Decimal))
    p_ogr = defaultdict(lambda: defaultdict(Decimal))
    p_rasp = defaultdict(lambda: defaultdict(Decimal))

    for row in results:
        p_ust[row.level_id][row.year] = row.p_ust or Decimal(0)
        p_ogr[row.level_id][row.year] = row.p_ogr or Decimal(0)
        p_rasp[row.level_id][row.year] = row.p_rasp or Decimal(0)

    return {
        'aggregated': {
            'p_ust': p_ust,
            'p_ogr': p_ogr,
            'p_rasp': p_rasp,
        }
    }


# Агрегация по региональным энергосистемам
def aggregate_power_by_regional_energy_system(session, start_year, end_year, filters=None):
    rd_res = regional_district_regional_energy_system
    res_alias = aliased(RegionalEnergySystem)

    subquery = (
        session.query(
            res_alias.id.label("res_id"),
            Station.id.label("station_id")
        )
        .join(rd_res, rd_res.c.regional_energy_system_id == res_alias.id)
        .join(Station, Station.id_regional_district == rd_res.c.regional_district_id)
        .subquery()
    )

    query = (
        session.query(
            subquery.c.res_id.label("level_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Station, Station.id == subquery.c.station_id)
        .join(Machine, Machine.id_station == Station.id)
        .join(MachinePower, MachinePower.id_machine == Machine.id)
        .filter(MachinePower.year_number.between(start_year, end_year))
        .group_by(subquery.c.res_id, MachinePower.year_number)
    )

    if filters:
        query = query.filter(*filters)

    results = query.all()

    p_ust = defaultdict(lambda: defaultdict(Decimal))
    p_ogr = defaultdict(lambda: defaultdict(Decimal))
    p_rasp = defaultdict(lambda: defaultdict(Decimal))

    for row in results:
        p_ust[row.level_id][row.year] = row.p_ust or Decimal(0)
        p_ogr[row.level_id][row.year] = row.p_ogr or Decimal(0)
        p_rasp[row.level_id][row.year] = row.p_rasp or Decimal(0)

    return {
        'aggregated': {
            'p_ust': p_ust,
            'p_ogr': p_ogr,
            'p_rasp': p_rasp,
        }
    }


# Агрегация по объединенным энергосистемам
def aggregate_power_by_union_energy_system(session, start_year, end_year, filters=None):
    # print("🧪 Агрегация по ОЭС — старт")

    res_alias = aliased(RegionalEnergySystem)
    rd_res = regional_district_regional_energy_system

    # Подзапрос: станции, привязанные к ОЭС через цепочку
    subquery = (
        session.query(
            UnionEnergySystem.id.label("ues_id"),
            Station.id.label("station_id")
        )
        .join(res_alias, res_alias.id_union_energy_system == UnionEnergySystem.id)
        .join(rd_res, rd_res.c.regional_energy_system_id == res_alias.id)
        .join(Station, Station.id_regional_district == rd_res.c.regional_district_id)
        .subquery()
    )

    # Отладка
    # stations_debug = session.query(subquery.c.station_id).distinct().all()
    # print(f"📦 Станций, связанных с ОЭС: {len(stations_debug)}")

    # station_ids = [row.station_id for row in stations_debug]
    # machines = session.query(Machine).filter(Machine.id_station.in_(station_ids)).all()
    # print(f"🔢 Агрегатов у этих станций: {len(machines)}")

    # machine_ids = [m.id for m in machines]
    # machine_powers = session.query(MachinePower).filter(MachinePower.id_machine.in_(machine_ids)).all()
    # print(f"🔌 Строк мощностей по агрегатам: {len(machine_powers)}")

    # powers_filtered = session.query(MachinePower).filter(
    #    MachinePower.id_machine.in_(machine_ids),
    #    MachinePower.year_number >= start_year,
    #    MachinePower.year_number <= end_year
    #).all()
    #print(f"📆 Строк мощностей в заданном диапазоне лет: {len(powers_filtered)}")

    #print(f"⏳ Период агрегации: {start_year} — {end_year}")

    #year_numbers_in_mp = session.query(MachinePower.year_number).distinct().all()
    #print(f"🔢 Года в таблице MachinePower: {[y[0] for y in year_numbers_in_mp]}")

    # Основной запрос агрегации
    query = (
        session.query(
            subquery.c.ues_id.label("level_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Station, Station.id == subquery.c.station_id)
        .join(Machine, Machine.id_station == Station.id)
        .join(MachinePower, MachinePower.id_machine == Machine.id)
        .filter(MachinePower.year_number >= start_year, MachinePower.year_number <= end_year)
        .group_by(subquery.c.ues_id, MachinePower.year_number)
    )

    if filters:
        query = query.filter(*filters)

    results = query.all()
    #print(f"🔍 Найдено строк агрегированных мощностей по ОЭС: {len(results)}")

    p_ust = defaultdict(lambda: defaultdict(Decimal))
    p_ogr = defaultdict(lambda: defaultdict(Decimal))
    p_rasp = defaultdict(lambda: defaultdict(Decimal))

    for row in results:
        # print(f"📊 ОЭС {row.level_id} / Год {row.year} → Руст: {row.p_ust}, Рогр: {row.p_ogr}, Ррасп: {row.p_rasp}")
        p_ust[row.level_id][row.year] = row.p_ust or Decimal(0)
        p_ogr[row.level_id][row.year] = row.p_ogr or Decimal(0)
        p_rasp[row.level_id][row.year] = row.p_rasp or Decimal(0)

    #print("✅ Агрегация по ОЭС — завершена")

    return {
        'aggregated': {
            'p_ust': p_ust,
            'p_ogr': p_ogr,
            'p_rasp': p_rasp,
        }
    }


# Агрегация по частям энергосистем
def aggregate_power_by_energy_system_type(session, start_year, end_year, filters=None):
    res_alias = aliased(RegionalEnergySystem)
    rd_res = regional_district_regional_energy_system

    subquery = (
        session.query(
            EnergySystemType.id.label("type_id"),
            Station.id.label("station_id")
        )
        .join(UnionEnergySystem, UnionEnergySystem.id_energy_system_type == EnergySystemType.id)
        .join(res_alias, res_alias.id_union_energy_system == UnionEnergySystem.id)
        .join(rd_res, rd_res.c.regional_energy_system_id == res_alias.id)
        .join(Station, Station.id_regional_district == rd_res.c.regional_district_id)
        .subquery()
    )

    query = (
        session.query(
            subquery.c.type_id.label("level_id"),
            Year.number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Station, Station.id == subquery.c.station_id)
        .join(Machine, Machine.id_station == Station.id)
        .join(MachinePower, MachinePower.id_machine == Machine.id)
        .join(Year, MachinePower.year_number == Year.number)
        .filter(Year.number >= start_year, Year.number <= end_year)
        .group_by(subquery.c.type_id, Year.number)
    )

    if filters:
        query = query.filter(*filters)

    results = query.all()

    p_ust = defaultdict(lambda: defaultdict(Decimal))
    p_ogr = defaultdict(lambda: defaultdict(Decimal))
    p_rasp = defaultdict(lambda: defaultdict(Decimal))

    for row in results:
        p_ust[row.level_id][row.year] = row.p_ust or Decimal(0)
        p_ogr[row.level_id][row.year] = row.p_ogr or Decimal(0)
        p_rasp[row.level_id][row.year] = row.p_rasp or Decimal(0)

    return {
        'aggregated': {
            'p_ust': p_ust,
            'p_ogr': p_ogr,
            'p_rasp': p_rasp,
        }
    }


# Агрегация по России
def aggregate_total_power_by_all_system_types(session, start_year, end_year, filters=None):
    res_alias = aliased(RegionalEnergySystem)
    rd_res = regional_district_regional_energy_system
    station_sub_alias = aliased(Station)
    station_outer_alias = aliased(Station)

    subquery = (
        session.query(
            station_sub_alias.id.label("station_id")
        )
        .join(rd_res, rd_res.c.regional_district_id == station_sub_alias.id_regional_district)
        .join(res_alias, res_alias.id == rd_res.c.regional_energy_system_id)
        .join(UnionEnergySystem, UnionEnergySystem.id == res_alias.id_union_energy_system)
        .join(EnergySystemType, EnergySystemType.id == UnionEnergySystem.id_energy_system_type)
        .distinct()
        .subquery()
    )

    query = (
        session.query(
            Year.number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .select_from(subquery)
        .join(station_outer_alias, station_outer_alias.id == subquery.c.station_id)
        .join(Machine, Machine.id_station == station_outer_alias.id)
        .join(MachinePower, MachinePower.id_machine == Machine.id)
        .join(Year, MachinePower.year_number == Year.number)
        .filter(Year.number >= start_year, Year.number <= end_year)
        .group_by(Year.number)
    )

    if filters:
        query = query.filter(*filters)

    results = query.all()

    p_ust = defaultdict(Decimal)
    p_ogr = defaultdict(Decimal)
    p_rasp = defaultdict(Decimal)

    for row in results:
        p_ust[row.year] = row.p_ust or Decimal(0)
        p_ogr[row.year] = row.p_ogr or Decimal(0)
        p_rasp[row.year] = row.p_rasp or Decimal(0)

    return {
        'aggregated': {
            'p_ust': p_ust,
            'p_ogr': p_ogr,
            'p_rasp': p_rasp,
        }
    }


# Агрегация по типу станции
def aggregate_energy_units_by_station_types(session, start_year, end_year, filters=None):
    query = (
        session.query(
            Station.id_energy_unit.label("energy_unit_id"),
            Machine.id_station_type.label("station_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id_station == Station.id)
        .join(MachinePower, MachinePower.id_machine == Machine.id)
        .join(Year, MachinePower.year_number == Year.number)
        .filter(Year.number >= start_year, Year.number <= end_year)
        .group_by(Station.id_energy_unit, Machine.id_station_type, Year.number)
    )

    if filters:
        query = query.filter(*filters)

    results = query.all()

    p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for row in results:
        p_ust[row.energy_unit_id][row.station_type_id][row.year] = row.p_ust or Decimal(0)
        p_ogr[row.energy_unit_id][row.station_type_id][row.year] = row.p_ogr or Decimal(0)
        p_rasp[row.energy_unit_id][row.station_type_id][row.year] = row.p_rasp or Decimal(0)

    return {
        "aggregated": {
            "p_ust": p_ust,
            "p_ogr": p_ogr,
            "p_rasp": p_rasp,
        }
    }


# Агрегация по типу ТЭС
def aggregate_energy_units_by_tes_types(session, start_year, end_year, filters=None):
    query = (
        session.query(
            Station.id_energy_unit.label("energy_unit_id"),
            MachineTesType.id_tes_type.label("tes_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id_station == Station.id)
        .join(MachinePower, MachinePower.id_machine == Machine.id)
        .join(
            MachineTesType,
            and_(
                MachineTesType.id_machine == Machine.id,
                MachineTesType.year_number == MachinePower.year_number
            )
        )
        .join(Year, MachinePower.year_number == Year.number)
        .filter(Year.number >= start_year, Year.number <= end_year)
        .group_by(
            Station.id_energy_unit,
            MachineTesType.id_tes_type,
            Year.number
        )
    )

    if filters:
        query = query.filter(*filters)

    rows = query.all()

    p_ust  = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_ogr  = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for r in rows:
        eu, tt, yr = r.energy_unit_id, r.tes_type_id, r.year
        p_ust [eu][tt][yr] = r.p_ust  or Decimal(0)
        p_ogr [eu][tt][yr] = r.p_ogr  or Decimal(0)
        p_rasp[eu][tt][yr] = r.p_rasp or Decimal(0)

    return {
        "aggregated": {
            "p_ust":  p_ust,
            "p_ogr":  p_ogr,
            "p_rasp": p_rasp,
        }
    }


# Агрегация по типу машин ТЭС
def aggregate_energy_units_by_tes_machine_types(session, start_year, end_year, filters=None):
    query = (
        session.query(
            Station.id_energy_unit.label("eu_id"),
            MachineTesType.id_tes_type.label("tes_type_id"),
            Machine.id_tes_machine_type.label("tm_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id_station == Station.id)
        .join(MachinePower, MachinePower.id_machine == Machine.id)
        .join(
            MachineTesType,
            and_(MachineTesType.id_machine == Machine.id,
                 MachineTesType.year_number == MachinePower.year_number)
        )
        .join(Year, MachinePower.year_number == Year.number)
        .filter(Year.number >= start_year, Year.number <= end_year)
        .group_by(
            Station.id_energy_unit,
            MachineTesType.id_tes_type,
            Machine.id_tes_machine_type,
            Year.number
        )
    )
    if filters:
        query = query.filter(*filters)

    p_ust  = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_ogr  = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))

    for r in query.all():
        eu, tt, mt, yr = r.eu_id, r.tes_type_id, r.tm_type_id, r.year
        p_ust [eu][tt][mt][yr] = r.p_ust  or Decimal(0)
        p_ogr [eu][tt][mt][yr] = r.p_ogr  or Decimal(0)
        p_rasp[eu][tt][mt][yr] = r.p_rasp or Decimal(0)

    return {
        "aggregated": {
            "p_ust":  p_ust,
            "p_ogr":  p_ogr,
            "p_rasp": p_rasp,
        }
    }


# Агрегация по видам топлива по типу ТЭС
def aggregate_energy_units_by_tes_types_with_fuel(
        session,
        start_year: int,
        end_year: int,
        filters: list | None = None
    ):

    q = (
        session.query(
            Station.id_energy_unit.label("eu"),
            TesType.id.label("tes_type_id"),
            FuelType.id.label("fuel_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id_station == Station.id)
        .join(MachinePower, MachinePower.id_machine == Machine.id)
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
        .join(Year, MachinePower.year_number == Year.number)
        .filter(Year.number >= start_year, Year.number <= end_year)
        .group_by("eu", "tes_type_id", "fuel_type_id", "year")
    )

    if filters:
        q = q.filter(*filters)

    # Структура: [energy_unit][tes_type][fuel_type][year] = Σ
    make_leaf = lambda: defaultdict(Decimal)
    fuel_map  = lambda: defaultdict(make_leaf)
    tes_map   = lambda: defaultdict(fuel_map)

    p_ust  = defaultdict(tes_map)
    p_ogr  = defaultdict(tes_map)
    p_rasp = defaultdict(tes_map)

    for r in q:
        p_ust [r.eu][r.tes_type_id][r.fuel_type_id][r.year] = r.p_ust or Decimal(0)
        p_ogr [r.eu][r.tes_type_id][r.fuel_type_id][r.year] = r.p_ogr or Decimal(0)
        p_rasp[r.eu][r.tes_type_id][r.fuel_type_id][r.year] = r.p_rasp or Decimal(0)

    return {
        "aggregated": {
            "p_ust":  p_ust,
            "p_ogr":  p_ogr,
            "p_rasp": p_rasp,
        }
    }

from collections import defaultdict
from decimal import Decimal

# Пример реализации функции агрегирования по типу топлива и типу машины ТЭС
def aggregate_energy_units_by_tes_machine_types_with_fuel(
    session,
    start_year: int,
    end_year: int,
    filters: list | None = None
):
    q = (
        session.query(
            Station.id_energy_unit.label("eu_id"),
            TesType.id.label("tes_type_id"),
            Machine.id_tes_machine_type.label("tm_type_id"),
            FuelType.id.label("fuel_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, Machine.id_station == Station.id)
        .join(MachinePower, MachinePower.id_machine == Machine.id)
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
        .join(Year, MachinePower.year_number == Year.number)
        .filter(Year.number >= start_year, Year.number <= end_year)
        .group_by("eu_id", "tes_type_id", "tm_type_id", "fuel_type_id", "year")
    )

    if filters:
        q = q.filter(*filters)

    # Структура: [eu_id][tes_type_id][tm_type_id][fuel_type_id][year] = Σ
    make_leaf = lambda: defaultdict(Decimal)
    fuel_map  = lambda: defaultdict(make_leaf)
    tm_map    = lambda: defaultdict(fuel_map)
    tes_map   = lambda: defaultdict(tm_map)

    p_ust  = defaultdict(tes_map)
    p_ogr  = defaultdict(tes_map)
    p_rasp = defaultdict(tes_map)

    for r in q:
        p_ust [r.eu_id][r.tes_type_id][r.tm_type_id][r.fuel_type_id][r.year] = r.p_ust or Decimal(0)
        p_ogr [r.eu_id][r.tes_type_id][r.tm_type_id][r.fuel_type_id][r.year] = r.p_ogr or Decimal(0)
        p_rasp[r.eu_id][r.tes_type_id][r.tm_type_id][r.fuel_type_id][r.year] = r.p_rasp or Decimal(0)

    return {
        "aggregated": {
            "p_ust":  p_ust,
            "p_ogr":  p_ogr,
            "p_rasp": p_rasp,
        }
    }






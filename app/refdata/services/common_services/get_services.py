"""Сервисный модуль: Common get services."""

from sqlalchemy import text, or_
from sqlalchemy.orm import joinedload

# Модели
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.territories.federal_district_model import FederalDistrict
from app.refdata.models.gen_companies.gen_company_model import GenCompany
from app.refdata.models.fuels.fuel_model import Fuel
from app.refdata.models.fuels.fuel_type_model import FuelType
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from app.refdata.models.energy_systems.synchronous_area_model import SynchronousArea


def get_federal_district_list():
    """Получает список типов энергосистем."""
    query = (
        FederalDistrict.query
        .filter(FederalDistrict.id.isnot(None), FederalDistrict.id > 0)
    )
    return query


def get_fuel_types():
    """Возвращает список видов топлива."""
    query = (
        FuelType.query
        .filter(FuelType.id.isnot(None), FuelType.id > 0)
    )
    return query


def get_energy_zone_list():
    """Получает список энергозон."""
    query = (
        EnergyZone.query
        .filter(EnergyZone.id.isnot(None), EnergyZone.id > 0)
    )
    return query


def get_synchronous_area_list():
    """Получает список синхронных зон."""
    query = (
        SynchronousArea.query
        .filter(SynchronousArea.id.isnot(None), SynchronousArea.id > 0)
    )
    return query


def get_total_regional_district_records(
    regional_district_filter=None,
    federal_district_filter=None,
    energy_zone_filter=None,
    synchronous_area_filter=None,
):
    """
    Возвращает общее количество записей субъектов РФ, соответствующих фильтрам.
    :param regional_district_filter: Фильтр по имени субъекта РФ.
    :param federal_district_filter: Фильтр по федеральному округу (имя, полное имя, аббревиатура).
    :param energy_zone_filter: Фильтр по энергозоне (имя, полное имя).
    :param synchronous_area_filter: Фильтр по синхронной зоне (имя, полное имя).
    :return: Количество записей.
    """

    query = (
        RegionalDistrict.query
        .options(
            joinedload(RegionalDistrict.federal_district),
            joinedload(RegionalDistrict.energy_zone),
            joinedload(RegionalDistrict.synchronous_area),
        )
        .join(FederalDistrict)
        .outerjoin(EnergyZone, RegionalDistrict.energy_zone)
        .outerjoin(SynchronousArea, RegionalDistrict.synchronous_area)
        .filter(RegionalDistrict.id.isnot(None), RegionalDistrict.id > 0)
    )

    # --- Фильтр по субъекту РФ ---
    if regional_district_filter:
        query = query.filter(
            or_(
                RegionalDistrict.name.ilike(f"%{regional_district_filter}%"),
                RegionalDistrict.name_full.ilike(f"%{regional_district_filter}%"),
            )
        )

    # --- Фильтр по федеральному округу ---
    if federal_district_filter:
        query = query.filter(
            or_(
                FederalDistrict.name.ilike(f"%{federal_district_filter}%"),
                FederalDistrict.name_full.ilike(f"%{federal_district_filter}%"),
                FederalDistrict.name_abr.ilike(f"%{federal_district_filter}%"),
            )
        )

    # --- Фильтр по энергозоне ---
    if energy_zone_filter:
        query = query.filter(
            or_(
                EnergyZone.name.ilike(f"%{energy_zone_filter}%"),
                EnergyZone.name_full.ilike(f"%{energy_zone_filter}%"),
            )
        )

    # --- Фильтр по синхронной зоне ---
    if synchronous_area_filter:
        query = query.filter(
            or_(
                SynchronousArea.name.ilike(f"%{synchronous_area_filter}%"),
                SynchronousArea.name_full.ilike(f"%{synchronous_area_filter}%"),
            )
        )

    return query.count()


def get_total_federal_district_records(federal_district_filter):
    """
    Возвращает общее количество записей ФО, соответствующих фильтру.
    :param federal_district_filter: Фильтр по имени ФО.
    :return: Количество записей.
    """
    query = (
        FederalDistrict.query
        .filter(FederalDistrict.id.isnot(None), FederalDistrict.id > 0)
    )

    if federal_district_filter:
        query = query.filter(FederalDistrict.name.ilike(f"%{federal_district_filter}%"))
        
    return query.count()


def get_total_gen_company_records(gen_company_filter):
    """
    Возвращает общее количество записей генерирующей компании, соответствующих фильтру.
    :param gen_company_filter: Фильтр по имени генерирующей компании.
    :return: Количество записей.
    """
    query = (
        GenCompany.query
        .filter(GenCompany.id.isnot(None), GenCompany.id > 0)
    )
    
    if gen_company_filter:
        query = query.filter(GenCompany.name.ilike(f"%{gen_company_filter}%"))

    return query.count()


def get_total_fuel_type_records(fuel_type_filter=None):
    """Возвращает общее количество записей, соответствующих фильтрам.
    :param fuel_type_filter: Фильтр по названию вида топлива.
    :return: Количество записей.
    """
    query = (
        FuelType.query
        .filter(FuelType.id.isnot(None), FuelType.id > 0)
    )

    if fuel_type_filter:
        query = query.filter(FuelType.name.ilike(f"%{fuel_type_filter}%"))

    return query.count()


def get_total_fuel_records(fuel_filter=None, fuel_type_filter=None):
    """Возвращает общее количество записей, соответствующих фильтрам.
    :param fuel_filter: Фильтр по названию типа топлива.
    :param fuel_type_filter: Фильтр по типу топлива.
    :return: Количество записей.
    """
    query = (
        Fuel.query
        .filter(Fuel.id.isnot(None), Fuel.id > 0)
    )

    if fuel_filter:
        query = query.filter(Fuel.name.ilike(f"%{fuel_filter}%"))

    if fuel_type_filter:
        query = query.filter(Fuel.id_fuel_type == fuel_type_filter)

    return query.count()





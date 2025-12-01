from app import db
from sqlalchemy.orm import joinedload
from sqlalchemy import func, or_
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, localcontext, ROUND_HALF_UP
from collections.abc import Mapping, Sequence
from app.generation.models.station.station_group_model import StationGroup

from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit

from app.refdata.models.fuels.fuel_type_model import FuelType

from app.refdata.models.gen_companies.gen_company_model import GenCompany

from app.refdata.models.refdata_for_stations.condition_type_model import ConditionType
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
from app.refdata.models.refdata_for_stations.machine.machine_type_model import MachineType
from app.refdata.models.refdata_for_stations.machine.tes_machine_type_model import TesMachineType
from app.refdata.models.refdata_for_stations.machine.tes_type_model import TesType

from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.territories.federal_district_model import FederalDistrict

from app.refdata.models.years.year_model import Year
from app.refdata.models.years.year_feature_model import YearFeature

from functools import lru_cache
from app.common.services.database_version_filter import filter_by_db_version

    
def get_current_year():
    current_year_obj = db.session.query(Year).filter_by(id_year_feature=2).first()
    current_year = current_year_obj.number - 1 if current_year_obj else None
    return current_year
    

@lru_cache(maxsize=1)
def get_station_types_list(station):
    if not station:
        return None
    
    # station_type теперь является атрибутом самой станции, а не машин
    return station.station_type if hasattr(station, "station_type") else None


def get_gen_companies():
    """Получает список генкомпаний'."""
    return GenCompany.query.order_by(GenCompany.id).all()


def get_gen_companies_list(station):
    if not station or not station.machines:
        return None

    gen_companies = {machine.gen_company.name for machine in station.machines if machine.gen_company}
    return ", ".join(gen_companies) if gen_companies else None


@lru_cache(maxsize=1)
def get_station_groups():
    """Получает список групп электростанций'."""
    return StationGroup.query.all()


def get_condition_type():
    """Получает список типов состояний."""
    return ConditionType.query.all()


@lru_cache(maxsize=1)
def get_station_types():
    """Получает список типов электростанций'."""
    return StationType.query.order_by(StationType.id).all()


@lru_cache(maxsize=1)
def get_machine_type():
    """Получает список типов агрегатов электростанций'."""
    return MachineType.query.all()


@lru_cache(maxsize=1)
def get_tes_types():
    """Получает список типов ТЭС'."""
    return TesType.query.order_by(TesType.id).all()

_UNKNOWN_NAME_VARIANTS = (
    "не известно",
    "неизвестно",
    "не указано",
    "не указан",
)

@lru_cache(maxsize=1)
def get_unknown_tes_type_id():
    """
    Возвращает ID типа ТЭС со значением «не известно» (или его синонимом)
    для текущей версии БД. Если такого значения нет, используется запись с id=0
    или первый доступный элемент.
    """
    query = filter_by_db_version(TesType.query, TesType)

    normalized_variants = tuple(
        variant.strip().lower() for variant in _UNKNOWN_NAME_VARIANTS if variant
    )

    if normalized_variants:
        filters = [func.lower(TesType.name) == variant for variant in normalized_variants]
        unknown = query.filter(or_(*filters)).first()
        if unknown:
            return unknown.id

    zero_candidate = query.filter(TesType.id == 0).first()
    if zero_candidate:
        return zero_candidate.id

    fallback = query.order_by(TesType.id.asc()).first()
    return fallback.id if fallback else 0


@lru_cache(maxsize=1)
def get_tes_machine_types():
    """Получает список типов агрегатов ТЭС."""
    return TesMachineType.query.order_by(TesMachineType.id).all()


@lru_cache(maxsize=1)
def get_fuel_types():
    """Получает список типов топлива'."""
    return FuelType.query.order_by(FuelType.id).all()


@lru_cache(maxsize=1)
def get_energy_units():
    """Получает список энергоузлов''."""
    return EnergyUnit.query.order_by(EnergyUnit.id).all()


@lru_cache(maxsize=1)
def get_energy_system_types():
    """Получает список типов энергосистем."""
    energy_system_type_list = EnergySystemType.query.order_by(EnergySystemType.id).all()

    energy_system_type_names = {
        energy_system_type.id: energy_system_type.name for energy_system_type in db.session.query(EnergySystemType).all()
    }

    return energy_system_type_list, energy_system_type_names


@lru_cache(maxsize=1)
def get_union_energy_systems():
    """Получаем список ОЭС с привязанными региональными энергосистемами"""
    
    # Запрашиваем все ОЭС, загружая связанные региональные энергосистемы заранее (чтобы избежать дополнительных SQL-запросов)
    union_energy_systems = UnionEnergySystem.query.options(
        joinedload(UnionEnergySystem.regional_energy_systems)
    ).order_by(UnionEnergySystem.id).all()

    union_energy_system_names = {
        union_energy_system.id: union_energy_system.name for union_energy_system in db.session.query(UnionEnergySystem).all()
    }

    # Создаем словарь, где ключ - ID ОЭС, а значение - список ID региональных энергосистем
    regional_energy_system_mapping = {
        ues.id: [res.id for res in ues.regional_energy_systems] if ues.regional_energy_systems else []
        for ues in union_energy_systems
    }

    return union_energy_systems, union_energy_system_names, regional_energy_system_mapping


@lru_cache(maxsize=1)
def get_regional_energy_systems():
    """Получает список региональных энергосистем с предварительной загрузкой ОЭС."""
    
    # Оптимизация запроса: загружаем ОЭС заранее (уменьшаем количество SQL-запросов)
    regional_energy_systems = RegionalEnergySystem.query.options(
        joinedload(RegionalEnergySystem.union_energy_system)
    ).order_by(RegionalEnergySystem.id).all()
    
    regional_energy_system_names = {
        regional_energy_system.id: regional_energy_system.name_full for regional_energy_system in db.session.query(RegionalEnergySystem).all()
    }
    
    # Преобразуем данные в удобный формат
    regional_energy_systems_list = [
        {
            "id": res.id,
            "name": res.name,
            "union_energy_system_id": res.id_union_energy_system if res.union_energy_system else None,
            "union_energy_system_name": res.union_energy_system.name if res.union_energy_system else None,
        }
        for res in regional_energy_systems
    ]

    return regional_energy_systems_list, regional_energy_system_names


@lru_cache(maxsize=1)
def get_federal_districts():
    """Получаем список ФО с привязанными субъектами РФ (региональными округами)."""

    # Оптимизируем запрос: загружаем все ФО и сразу привязываем субъекты (уменьшаем SQL-запросы)
    federal_districts = FederalDistrict.query.options(
        joinedload(FederalDistrict.regional_districts)  # Предварительная загрузка субъектов РФ
    ).order_by(FederalDistrict.id).all()

    # Создаём список ФО и словарь соответствий "ФО → субъекты"
    regional_district_mapping = {
        fd.id: [rd.id for rd in fd.regional_districts] if fd.regional_districts else []
        for fd in federal_districts
    }

    return federal_districts, regional_district_mapping


@lru_cache(maxsize=1)
def get_regional_districts():
    """Получает список субъектов РФ с привязанными федеральными округами."""
    
    # Оптимизируем запрос: загружаем все субъекты с привязанными ФО, чтобы не делать дополнительные SQL-запросы
    regional_districts = RegionalDistrict.query.options(
        joinedload(RegionalDistrict.federal_district)  # Предварительная загрузка ФО
    ).order_by(RegionalDistrict.id).all()
    
    regional_district_names = {
        regional_district.id: regional_district.name for regional_district in db.session.query(RegionalDistrict).all()
    }

    # Создаём список субъектов РФ с дополнительной информацией о ФО
    regional_districts_list = [
        {
            "id": rd.id,
            "name": rd.name,
            "federal_district_id": rd.id_federal_district if rd.federal_district else None,
            "federal_district_name": rd.federal_district.name if rd.federal_district else None
        }
        for rd in regional_districts
    ]

    return regional_districts_list, regional_district_names


@lru_cache(maxsize=1)
def get_year_features():
    """
    Возвращает словарь {year_number: year_feature_name}, используя прямой SQL-запрос.
    """
    rows = (
        db.session.query(Year.number, YearFeature.name)
        .join(YearFeature, Year.id_year_feature == YearFeature.id)
        .all()
    )
    return {number: name for number, name in rows}

from jinja2 import Undefined

def format_decimal_for_display(value, digits=None):
    if value is None or isinstance(value, Undefined):
        return "—"

    # Приводим к Decimal
    try:
        if isinstance(value, str):
            value = Decimal(value.replace(",", "."))
        elif isinstance(value, float):
            value = Decimal(str(value))
        elif not isinstance(value, Decimal):
            value = Decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        return ""

    # digits == -1 → округление до целого
    if digits == -1:
        value = value.to_integral_value(rounding=ROUND_HALF_UP)
        return str(value).replace('.', ',')

    # digits is None → округляем до 1 знака по умолчанию
    if digits is None:
        digits = 1

    # digits == 0 → без округления, без экспоненты
    if digits == 0:
        return format(value.normalize(), 'f').replace('.', ',')

    # digits > 0 → округление с нужной точностью
    with localcontext() as ctx:
        ctx.rounding = ROUND_HALF_UP
        quant = Decimal('1.' + '0' * digits)
        value = value.quantize(quant)
        return format(value, f'.{digits}f').replace('.', ',')


def rounded_decimal(value, digits=15):
    """
    Безопасное округление значения с сохранением точности. 
    Возвращает None, если value пустое или невалидное.
    """
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(Decimal(f"1.{'0'*digits}"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None

import re
from datetime import datetime, date
import pandas as pd

def convert_to_date(value):
    """
    Универсально конвертирует значение в datetime.date:
    - '2021' → date(2021, 1, 1)
    - '01.01.2021' → date(2021, 1, 1)
    - '2021-01-01' → date(2021, 1, 1)
    - datetime, pd.Timestamp → date
    - пусто или некорректно → None
    """
    if not value or pd.isna(value):
        return None

    if isinstance(value, date):
        return value

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime().date()

    if isinstance(value, str):
        value = value.strip()

        # Только год
        if re.fullmatch(r"\d{4}", value):
            return date(int(value), 1, 1)

        # dd.mm.yyyy
        try:
            return datetime.strptime(value, "%d.%m.%Y").date()
        except ValueError:
            pass

        # yyyy-mm-dd
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            pass

    return None


def format_date_for_string_field(value):
    """
    Преобразует значение в строку даты формата 'DD.MM.YYYY', если это datetime/date.
    Если значение уже строка — возвращает очищенную строку.
    Если значение пустое или некорректное — возвращает None.
    """
    if pd.isna(value) or value in ("", None):
        return None
    if isinstance(value, (datetime, date)):
        return value.strftime("%d.%m.%Y")
    return str(value).strip()
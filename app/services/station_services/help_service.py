from app import db
from sqlalchemy.orm import joinedload
from app.models import (
    UnionEnergySystem, RegionalEnergySystem, EnergySystemType, EnergyUnit,
    RegionalDistrict, FederalDistrict,Station, StationType, Machine, 
    MachinePower, MachineFuel, MachineTesType, ConditionType, MachineType, 
    TesType, TesMachineType, StationGroup, Machine, StationPower,
    Year, Fuel, GenCompany, FuelType
)

    
def get_current_year():
    current_year_obj = db.session.query(Year).filter_by(id_year_feature=2).first()
    current_year = current_year_obj.number - 1 if current_year_obj else None
    return current_year
    

def get_station_types_list(station):
    if not hasattr(station, "machines") or not station.machines:
        return None

    station_type = next((machine.station_type for machine in station.machines if hasattr(machine, "station_type") and machine.station_type), None)
    
    return station_type


def get_gen_companies():
    """Получает список генкомпаний'."""
    return GenCompany.query.order_by(GenCompany.id).all()


def get_gen_companies_list(station):
    if not station or not station.machines:
        return None

    gen_companies = {machine.gen_company.name for machine in station.machines if machine.gen_company}
    return ", ".join(gen_companies) if gen_companies else None


def get_station_groups():
    """Получает список групп электростанций'."""
    return StationGroup.query.all()


def get_condition_type():
    """Получает список типов состояний."""
    return ConditionType.query.all()


def get_station_types():
    """Получает список типов электростанций'."""
    return StationType.query.order_by(StationType.id).all()


def get_machine_type():
    """Получает список типов агрегатов электростанций'."""
    return MachineType.query.all()


def get_tes_types():
    """Получает список типов ТЭС'."""
    return TesType.query.order_by(TesType.id).all()


def get_tes_machine_types():
    """Получает список типов агрегатов ТЭС."""
    return TesMachineType.query.order_by(TesMachineType.id).all()


def get_fuel_types():
    """Получает список типов топлива'."""
    return FuelType.query.order_by(FuelType.id).all()


def get_energy_units():
    """Получает список энергоузлов''."""
    return EnergyUnit.query.order_by(EnergyUnit.id).all()


def get_energy_system_types():
    """Получает список типов энергосистем."""
    energy_system_type_list = EnergySystemType.query.order_by(EnergySystemType.id).all()

    energy_system_type_names = {
        energy_system_type.id: energy_system_type.name for energy_system_type in db.session.query(EnergySystemType).all()
    }

    return energy_system_type_list, energy_system_type_names


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


def get_year_features():
    """
    Получает словарь с year.number как ключом и year.year_feature как значением.
    :return: Словарь year_features
    """
    return {year.number: year.year_feature for year in Year.query.options(db.joinedload(Year.year_feature)).all()}


from decimal import Decimal, ROUND_HALF_UP

def maybe_round(value, round_digits=1):
    if value is None:
        return None

    # Приводим сразу все float к Decimal(str(...))
    if isinstance(value, float):
        value = Decimal(str(value))
    elif isinstance(value, str):
        try:
            value = Decimal(value.replace(',', '.'))
        except Exception:
            return value

    if round_digits is None:
        return str(value)

    if round_digits == -1:
        return str(int(value.to_integral_value(rounding=ROUND_HALF_UP)))

    quantize_str = '1.' + '0' * round_digits
    rounded = value.quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP)
    return str(rounded)

def round_nested_power_dict(power_dict, round_digits=1):
    """Рекурсивное округление всех Decimal внутри вложенных словарей"""
    result = {}
    for key, inner in power_dict.items():
        if isinstance(inner, dict):
            result[key] = round_nested_power_dict(inner, round_digits)
        else:
            result[key] = maybe_round(inner, round_digits)
    return result


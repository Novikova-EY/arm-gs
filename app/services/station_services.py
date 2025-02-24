from app import db
from app.models.logs_models import Log
from app.models.energy_systems_models import UnionEnergySystem, RegionalEnergySystem, EnergySystemType
from app.models.territories_models import RegionalDistrict, FederalDistrict
from app.models.stations_models import ConditionType, Machine, MachineType, Station, StationType, TesType
from app.models import Station, Machine, MachinePower, MachineFuel, ConditionType, Fuel, RegionalDistrict, GenCompany, StationType, MachineType, TesType, TesMachineType
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.expression import and_


def log_to_db(username, action, details=None):
    """Записывает лог действия пользователя в базу данных."""
    try:
        log_entry = Log(username=username, action=action, details=details)
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        print(f"Ошибка записи лога: {e}")


def get_stations_list(
    page, 
    per_page,
    condition_type_filter=None, 
    gen_company_filter=None, 
    station_name_filter=None, 
    station_type_filter=None, 
    tes_type_filter=None, 
    tes_machine_type_filter=None, 
    energy_system_type_filter=None, 
    union_energy_system_filter=None, 
    regional_energy_system_filter=None, 
    federal_district_filter=None, 
    regional_district_filter=None, 
    sort_by="id", 
    sort_dir="asc"):
    """Получает список электростанций с пагинацией, фильтрацией и сортировкой, с возможностью выбора по годам."""

    # Загружаем связанные данные
    query = get_filtered_stations(
        condition_type_filter,
        gen_company_filter,
        station_name_filter,
        station_type_filter,
        tes_type_filter, 
        tes_machine_type_filter, 
        energy_system_type_filter,
        union_energy_system_filter,
        regional_energy_system_filter,
        federal_district_filter,
        regional_district_filter,
        sort_by,
        sort_dir)

    # Пагинация
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return pagination


def get_filtered_stations(
    condition_type_filter=None,
    gen_company_filter=None,
    station_name_filter=None,
    station_type_filter=None,
    tes_type_filter=None,
    tes_machine_type_filter=None,
    energy_system_type_filter=None,
    union_energy_system_filter=None,
    regional_energy_system_filter=None,
    federal_district_filter=None,
    regional_district_filter=None,
    sort_by="id",
    sort_dir="asc"
):
    query = Station.query.options(
        joinedload(Station.condition_type),  # Загружаем связь с состоянием станции
        joinedload(Station.regional_district),  # Загружаем связь с регионом
        joinedload(Station.group),  # Загружаем связь с группой электростанций
        joinedload(Station.machines),  # Загружаем связь с агрегатами станции
        joinedload(Station.machines).joinedload(Machine.machine_powers).joinedload(MachinePower.years),  # Загружаем мощность агрегатов и года
        joinedload(Station.machines).joinedload(Machine.machine_fuels).joinedload(MachineFuel.years),  # Загружаем топливо агрегатов и года
    )

    # Фильтрация по названию генерирующей компании
    if gen_company_filter:
        gen_companies = GenCompany.query.filter(GenCompany.name.ilike(f"%{gen_company_filter}%")).all()
        gen_company_ids = [company.id for company in gen_companies]
        
        query = query.join(Station.machines).filter(Machine.id_gen_company.in_(gen_company_ids))

    # Фильтрация по названию электростанции
    if station_name_filter:
        query = query.filter(Station.name.ilike(f"%{station_name_filter}%"))
    
    # Фильтрация по типу энергосистемы
    if energy_system_type_filter:
        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.regional_energy_systems.any(
                    RegionalEnergySystem.union_energy_system.has(
                        UnionEnergySystem.energy_system_type.has(
                            EnergySystemType.id == energy_system_type_filter
                        )
                    )
                )
            )
        )

    # Фильтрация по объединённой энергосистеме
    if union_energy_system_filter:
        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.regional_energy_systems.any(
                    RegionalEnergySystem.id_union_energy_system == union_energy_system_filter
                )
            )
        )

    # Фильтрация по региональной энергосистеме
    if regional_energy_system_filter:
        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.regional_energy_systems.any(
                    RegionalEnergySystem.id == regional_energy_system_filter
                )
            )
        )

    # Фильтрация по ФО
    if federal_district_filter:
        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.federal_district.has(
                    FederalDistrict.id == federal_district_filter
                )
            )
        )

    # Фильтрация по субъекту РФ
    if regional_district_filter:
        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.id == regional_district_filter
            )
        )

    # Фильтрация по состоянию электростанции
    if condition_type_filter:
        query = query.join(Station.machines).filter(Machine.id_condition_type == condition_type_filter)

    # Фильтрация по типу агрегатов, по типу ТЭС, по типу агрегатов ТЭС
    if station_type_filter or tes_type_filter or tes_machine_type_filter:
        query = query.join(Station.machines).filter(Machine.id_station_type == station_type_filter)
        if tes_type_filter and not tes_machine_type_filter:
            query = query.filter(Machine.id_tes_type == tes_type_filter)
        if not tes_type_filter and tes_machine_type_filter:
            query = query.filter(Machine.id_tes_machine_type.in_(tes_machine_type_filter))

        if tes_type_filter and tes_machine_type_filter:
            query = query.filter(
                and_(
                    Machine.id_tes_type == tes_type_filter,
                    Machine.id_tes_machine_type.in_(tes_machine_type_filter)
                )
            )

    # Сортировка
    if sort_by == "name":
        query = query.order_by(Station.name.desc() if sort_dir == "desc" else Station.name.asc())
    else:
        query = query.order_by(Station.id.desc() if sort_dir == "desc" else Station.id.asc())

    return query


def get_total_with_filter(
    condition_type_filter=None, 
    gen_company_filter=None, 
    station_name_filter=None,
    station_type_filter=None, 
    tes_type_filter=None, 
    tes_machine_type_filter=None,
    energy_system_type_filter=None, 
    union_energy_system_filter=None,
    regional_energy_system_filter=None, 
    federal_district_filter=None,
    regional_district_filter=None,
):
    """
    Возвращает общее количество записей электростанций, соответствующих фильтру.
    """
    print(f"Принятые параметры в get_filtered_stations: {locals()}")

    query = Station.query.options(
        joinedload(Station.condition_type),  # Загружаем связь с состоянием станции
        joinedload(Station.regional_district),  # Загружаем связь с регионом
        joinedload(Station.group),  # Загружаем связь с группой электростанций
        joinedload(Station.machines),  # Загружаем связь с агрегатами станции
        joinedload(Station.machines).joinedload(Machine.machine_powers).joinedload(MachinePower.years),  # Загружаем мощность агрегатов и года
        joinedload(Station.machines).joinedload(Machine.machine_fuels).joinedload(MachineFuel.years),  # Загружаем топливо агрегатов и года
    )

    # Фильтрация по названию генерирующей компании
    if gen_company_filter:
        gen_companies = GenCompany.query.filter(GenCompany.name.ilike(f"%{gen_company_filter}%")).all()
        gen_company_ids = [company.id for company in gen_companies]
        
        query = query.join(Station.machines).filter(Machine.id_gen_company.in_(gen_company_ids))

    # Фильтрация по названию электростанции
    if station_name_filter:
        query = query.filter(Station.name.ilike(f"%{station_name_filter}%"))
    
    # Фильтрация по типу энергосистемы
    if energy_system_type_filter:
        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.regional_energy_systems.any(
                    RegionalEnergySystem.union_energy_system.has(
                        UnionEnergySystem.energy_system_type.has(
                            EnergySystemType.id == energy_system_type_filter
                        )
                    )
                )
            )
        )


    # Фильтрация по объединённой энергосистеме
    if union_energy_system_filter:
        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.regional_energy_systems.any(
                    RegionalEnergySystem.id_union_energy_system == union_energy_system_filter
                )
            )
        )

    # Фильтрация по региональной энергосистеме
    if regional_energy_system_filter:
        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.regional_energy_systems.any(
                    RegionalEnergySystem.id == regional_energy_system_filter
                )
            )
        )

    # Фильтрация по ФО
    if federal_district_filter:
        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.federal_district.has(
                    FederalDistrict.id == federal_district_filter
                )
            )
        )

    # Фильтрация по субъекту РФ
    if regional_district_filter:
        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.id == regional_district_filter
            )
        )

    # Фильтрация по типу агрегатов
    if station_type_filter:
        query = query.join(Station.machines).filter(Machine.id_station_type == station_type_filter)
    
    # Фильтрация по типу ТЭС
    if tes_type_filter:
        query = query.join(Station.machines).filter(Machine.id_tes_type == tes_type_filter)

    # Фильтрация по типу агрегатов ТЭС
    if tes_machine_type_filter:
        query = query.filter(Machine.id_tes_machine_type.in_(tes_machine_type_filter))
    
    return query.count()


def get_condition_type():
    """Получает список типов состояний."""
    return ConditionType.query.order_by(ConditionType.id).all()


def get_station_type():
    """Получает список типов электростанций'."""
    return StationType.query.order_by(StationType.id).all()


def get_machine_type():
    """Получает список типов агрегатов электростанций'."""
    return MachineType.query.all()


def get_tes_types():
    """Получает список типов электростанций'."""
    return TesType.query.order_by(TesType.id).all()


def get_tes_machine_types():
    """Получает список типов электростанций'."""
    return TesMachineType.query.order_by(TesMachineType.id).all()


def get_energy_system_types():
    """Получает список типов энергосистем."""
    return EnergySystemType.query.order_by(EnergySystemType.id).all()


def get_union_energy_systems():
    """Получаем список ОЭС с привязанными региональными энергосистемами"""
    union_energy_systems = UnionEnergySystem.query.order_by(UnionEnergySystem.id).all()

    # Создаем словарь, где ключ - ID ОЭС, а значение - список ID региональных энергосистем
    regional_energy_system_mapping = {
        ues.id: [res.id for res in ues.regional_energy_systems]
        for ues in union_energy_systems
    }

    return union_energy_systems, regional_energy_system_mapping


def get_regional_energy_systems():
    """Получает список региональных энергосистем."""
    regional_energy_systems = RegionalEnergySystem.query.order_by(RegionalEnergySystem.id).all()
    
    regional_energy_systems_list = [
        {"id": res.id, "name": res.name} for res in regional_energy_systems
    ]

    return regional_energy_systems_list


def get_federal_districts():
    """Получаем список ФО с привязанными региональными энергосистемами"""
    federal_districts = FederalDistrict.query.all()

    # Создаем словарь, где ключ - ID ФО, а значение - список ID субъектов РФ
    regional_district_mapping = {
        federal_district.id: [regional_district.id for regional_district in federal_district.regional_districts]
        for federal_district in federal_districts
    }

    return federal_districts, regional_district_mapping


def get_regional_districts():
    """Получает список субъектов."""
    regional_districts = RegionalDistrict.query.all()
    
    regional_districts_list = [
        {"id": regional_district.id, "name": regional_district.name} for regional_district in regional_districts
    ]

    return regional_districts_list

import re
import pandas as pd
from app import db
from datetime import datetime

# Функция для очистки текста
def clean_name(name_to_change):
    if not isinstance(name_to_change, str):
        return name_to_change
    
    # Проверка на строку 'nan', игнорируем её
    if name_to_change.strip().lower() == "nan":
        return None
    
    # Очищаем строку
    name = name_to_change.strip()
    name = name.replace('\xa0', ' ')  # заменяем неразрывные пробелы на обычные
    name = re.sub(r'\s+', ' ', name)  # заменяем несколько пробелов на один
    
    # Исправляем кавычки внутри текста
    name = re.sub(r'"\s*(\w)', r'«\1', name)  # Заменяем открывающую кавычку "
    name = re.sub(r'(\w)\s*"', r'\1»', name)  # Заменяем закрывающую кавычку "

    # Дополнительная обработка кавычек внутри текста (если между словами)
    name = re.sub(r'(\s)"(\w)', r'\1«\2', name)  # Начальные кавычки внутри текста
    name = re.sub(r'(\w)"(\s)', r'\1»\2', name)  # Закрывающие кавычки внутри текста

    return name


# Функция для конверстиции даты в формат 'гггг-мм-дд'
def convert_date(date_value):
    """
    Преобразует дату в формат 'гггг-мм-дд'.
    Поддерживает строки в формате 'дд.мм.гггг', pandas.Timestamp и datetime.
    Если дата некорректна, возвращает None.
    
    :param date_value: Строка, Timestamp или datetime
    :return: Строка в формате 'гггг-мм-дд' или None
    """
    if pd.isna(date_value) or not date_value:
        return None

    # Если это pandas.Timestamp или datetime — преобразуем сразу
    if isinstance(date_value, (pd.Timestamp, datetime)):
        return date_value.strftime("%Y-%m-%d")

    # Если это строка — пытаемся распарсить
    if isinstance(date_value, str):
        try:
            date_obj = datetime.strptime(date_value, "%d.%m.%Y")
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            return None

    # Если неизвестный тип данных
    return None
    

# Функция для проверки значений на NaN и замены на None
def safe_value(value):
    return None if pd.isna(value) or value in ['', ' '] else value

# Функция для импорта списка станций с параметрами в базу данных
def import_station_list_from_excel(file, user):
    xls = pd.ExcelFile(file)
    df = xls.parse('станции', header=0)
    df = df.dropna(how='all')

    current_station = None
    current_machine = None
    last_machine = None
    previous_was_machine = False

    start_year = 2021
    end_year = 2031

    for index, row in df.iterrows():
        # Пропускаем полностью пустые строки
        if row.isnull().all():
            continue

        print(f"Обрабатываем строку {index}: {row.to_dict()}")

        # Проверка и создание/обновление станции
        if not (pd.isna(row['regional_district']) and pd.isna(row['station_name'])): # если поля regional_district и station_name заполнены, то создаем/обновляем станцию
            print("Выполняется условие если поля regional_district и station_name заполнены, то создаем/обновляем станцию")
            regional_district_name = clean_name(row['regional_district'])
            regional_district = RegionalDistrict.query.filter_by(name=regional_district_name).first()

            station_name = clean_name(row['station_name'])
            station = Station.query.filter_by(name=station_name).first()

            condition_type = ConditionType.query.filter_by(name="действующий").first()

            if not station:
                station = Station(
                    name=station_name,
                    id_regional_district=regional_district.id if regional_district else None,
                    id_condition_type=condition_type.id if condition_type else None,
                )
                db.session.add(station)
                print("Создана электростанция", station_name)
            else:
                if station.id_regional_district != regional_district.id:
                    station.id_regional_district = regional_district.id if regional_district else None
                    print("Обновлена электростанция", station_name)

            db.session.commit()
            current_station = station
            current_machine = None
            previous_was_machine = False

        # Проверка и создание/обновление агрегатов станции
        elif not pd.isna(row['machine_name']) and not pd.isna(row['gen_company']): # если поля regional_district и station_name не заполнены, а поля machine_name и gen_company заполнены, то создаем/обновляем агрегат
            print("Выполняется условие если поля regional_district и station_name не заполнены, а поля machine_name и gen_company заполнены, то создаем/обновляем агрегат, записываем его установленную мощность и топливо")

            machine_group = clean_name(row.get('machine_group'))

            # Проверяем, является ли значение NaN или некорректным
            if pd.isna(machine_group) or machine_group in [None, 'nan', 'NaN', '']:
                machine_group = ""
            else:
                # Если это число (int или float), приводим его к строке без '.0' в случае целых чисел
                if isinstance(machine_group, (int, float)):
                    machine_group = str(int(machine_group)) if machine_group.is_integer() else str(machine_group)
                else:
                    machine_group = str(machine_group).strip()


            machine_number = clean_name(row.get('machine_number'))

            # Проверяем, является ли значение NaN или некорректным
            if pd.isna(machine_number) or machine_number in [None, 'nan', 'NaN', '']:
                machine_number = ""
            else:
                # Если это число (int или float), приводим его к строке без '.0' в случае целых чисел
                if isinstance(machine_number, (int, float)):
                    machine_number = str(int(machine_number)) if machine_number.is_integer() else str(machine_number)
                else:
                    machine_number = str(machine_number).strip()


            machine_name = str(clean_name(row['machine_name']))
            gen_company = GenCompany.query.filter_by(name=clean_name(row['gen_company'])).first()

            condition_type = ConditionType.query.filter_by(name="действующий").first()
            if row.get('p_2024') == 0:
                condition_type = ConditionType.query.filter_by(name="планируемый").first()

            # Если machine_number является None, то выполняем запрос по machine_name
            machine = Machine.query.filter_by(machine_number=machine_number, machine_group=machine_group, id_station=current_station.id).first()

            if machine:
                print(f"Агрегат группы  {machine_group} № {machine_number} - {machine_name} уже существует, обновляем данные.")
                machine.machine_name = machine_name
                machine.machine_group = machine_group
                machine.id_gen_company = gen_company.id if gen_company else None
                machine.date_exploitation=row.get('date_exploitation') if not pd.isna(row.get('date_exploitation')) else None,
                machine.note=clean_name(row['note']) if not pd.isna(row['note']) else None,
                machine.id_station_type=StationType.query.filter_by(name=clean_name(row['station_type'])).first().id if not pd.isna(row['station_type']) else None,
                machine.id_tes_type=TesType.query.filter_by(name=clean_name(row['tes_type'])).first().id if not pd.isna(row['tes_type']) else None,
                machine.id_tes_machine_type=TesMachineType.query.filter_by(name=clean_name(row['tes_machine_type'])).first().id if not pd.isna(row['tes_machine_type']) else None,
                machine.date_commission_expected=convert_date(row.get('date_commission_expected')) if not convert_date(pd.isna(row.get('date_commission_expected'))) else None,
                machine.date_commission_fact=convert_date(row.get('date_commission_fact')) if not convert_date(pd.isna(row.get('date_commission_fact'))) else None,
                machine.date_joining_expected=convert_date(row.get('date_joining_expected')) if not convert_date(pd.isna(row.get('date_joining_expected'))) else None,
                machine.date_joining_fact=convert_date(row.get('date_joining_fact')) if not convert_date(pd.isna(row.get('date_joining_fact'))) else None,
                machine.date_detatchment_fact=convert_date(row.get('date_detatchment_fact')) if not convert_date(pd.isna(row.get('date_detatchment_fact'))) else None,
                machine.date_decompressing_expected=convert_date(row.get('date_decompressing_expected')) if not convert_date(pd.isna(row.get('date_decompressing_expected'))) else None,
                machine.date_decompressing_fact=convert_date(row.get('date_decompressing_fact')) if not convert_date(pd.isna(row.get('date_decompressing_fact'))) else None,
                machine.date_modernization_expected=convert_date(row.get('date_modernization_expected')) if not convert_date(pd.isna(row.get('date_modernization_expected'))) else None,
                machine.date_relabing_fact=convert_date(row.get('date_relabing_fact')) if not convert_date(pd.isna(row.get('date_relabing_fact'))) else None
                machine.date_update_fact=convert_date(row.get('date_update_fact')) if not convert_date(pd.isna(row.get('date_update_fact'))) else None
                print(f"Обновлен агрегат группы  {machine_group} № {machine_number}, {machine_name}")
            else:
                print(f"Создаем новый агрегат группы  {machine_group} № {machine_number} - {machine_name}.")
                machine = Machine(
                    id_condition_type=condition_type.id if condition_type else None,
                    id_gen_company=gen_company.id if gen_company else None,
                    id_station=current_station.id,
                    machine_number=machine_number,
                    machine_name=machine_name,
                    machine_group=machine_group,
                    date_exploitation=row.get('date_exploitation') if not pd.isna(row.get('date_exploitation')) else None,
                    note=clean_name(row['note']) if not pd.isna(row['note']) else None,
                    id_station_type=StationType.query.filter_by(name=clean_name(row['station_type'])).first().id if not pd.isna(row['station_type']) else None,
                    id_tes_type=TesType.query.filter_by(name=clean_name(row['tes_type'])).first().id if not pd.isna(row['tes_type']) else None,
                    id_tes_machine_type=TesMachineType.query.filter_by(name=clean_name(row['tes_machine_type'])).first().id if not pd.isna(row['tes_machine_type']) else None,
                    date_commission_expected=convert_date(row.get('date_commission_expected')) if not convert_date(pd.isna(row.get('date_commission_expected'))) else None,
                    date_commission_fact=convert_date(row.get('date_commission_fact')) if not convert_date(pd.isna(row.get('date_commission_fact'))) else None,
                    date_joining_expected=convert_date(row.get('date_joining_expected')) if not convert_date(pd.isna(row.get('date_joining_expected'))) else None,
                    date_joining_fact=convert_date(row.get('date_joining_fact')) if not convert_date(pd.isna(row.get('date_joining_fact'))) else None,
                    date_detatchment_fact=convert_date(row.get('date_detatchment_fact')) if not convert_date(pd.isna(row.get('date_detatchment_fact'))) else None,
                    date_decompressing_expected=convert_date(row.get('date_decompressing_expected')) if not convert_date(pd.isna(row.get('date_decompressing_expected'))) else None,
                    date_decompressing_fact=convert_date(row.get('date_decompressing_fact')) if not convert_date(pd.isna(row.get('date_decompressing_fact'))) else None,
                    date_modernization_expected=convert_date(row.get('date_modernization_expected')) if not convert_date(pd.isna(row.get('date_modernization_expected'))) else None,
                    date_relabing_fact=convert_date(row.get('date_relabing_fact')) if not convert_date(pd.isna(row.get('date_relabing_fact'))) else None,
                    date_update_fact=convert_date(row.get('date_update_fact')) if not convert_date(pd.isna(row.get('date_update_fact'))) else None
                )
                print("Создан агрегат", machine_number, machine_name)
                db.session.add(machine)

            db.session.commit()
            current_machine = machine
            last_machine = current_machine

            # Установленная мощность (p_ust) и топливо (MachineFuel)     
            for year in range(start_year, end_year + 1):
                p_ust = clean_name(row.get(f'p_{year}'))
                p_ust = None if p_ust in ['', ' ', 'nan', 'NaN'] or pd.isna(p_ust) else p_ust
                try:
                    p_ust = float(p_ust) if p_ust is not None else None
                except ValueError:
                    p_ust = None

                if p_ust is None or current_machine.id_condition_type == ConditionType.query.filter_by(name="планируемый").first().id:
                    p_ust = 0
                
                print(f"Установленная мощность для машины {current_machine.machine_number}, год {year}: {p_ust}")

                # Сохраняем данные о мощности
                machine_power = MachinePower.query.filter_by(year_number=year, id_machine=current_machine.id).first()
                if machine_power:
                    if machine_power.p_ust != p_ust:
                        machine_power.p_ust = p_ust
                else:
                    machine_power = MachinePower(
                        year_number=year,
                        id_machine=machine.id,
                        p_ust=p_ust
                    )
                    db.session.add(machine_power)

                fuel_name = clean_name(row.get(f'fuel_{year}'))

                fuel_type_mapping = {
                    "газ": 1,
                    "уголь": 2,
                    "прочее": 3
                }

                fuel_type_id = fuel_type_mapping.get(fuel_name)

                if fuel_type_id:
                    fuel = Fuel.query.filter_by(id_fuel_type=fuel_type_id).first()
                else:
                    fuel = None

                print(f"Топливо для машины {current_machine.machine_number}, год {year}: {fuel}")

                if fuel and current_machine.id_station_type == StationType.query.filter_by(name="ТЭС").first().id:
                    machine_fuel = MachineFuel.query.filter_by(year_number=year, id_machine=current_machine.id).first()
                    
                    if not machine_fuel:
                        machine_fuel = MachineFuel(
                            year_number=year,
                            id_machine=current_machine.id,
                            id_fuel=fuel.id
                        )
                        db.session.add(machine_fuel)
                    else:
                        # Обновляем id_fuel, если оно изменилось
                        if machine_fuel.id_fuel != fuel.id:
                            machine_fuel.id_fuel = fuel.id
                        
                        # Обновляем p_ust, если передано новое значение
                        if p_ust is not None:
                            machine_fuel.p_ust = p_ust

            db.session.commit()
            print("Установленные мощности и топливо внесены")
            previous_was_machine = True

        # Располагаемая мощность (p_rasp)
        elif previous_was_machine: # если поля regional_district и station_name, machine_name и gen_company не заполнены, но шагом ранее был создан агрегат, то добавляем ему располагаему мощность
                print("если поля regional_district и station_name, machine_name и gen_company не заполнены, но шагом ранее был создан агрегат, то добавляем ему располагаему мощность")
                current_machine = last_machine  # Используем последнюю машину

                for year in range(start_year, end_year + 1):
                    p_rasp = clean_name(row.get(f'p_{year}'))
                    p_rasp = None if p_rasp in ['', ' ', 'nan', 'NaN'] or pd.isna(p_rasp) else p_rasp
                    try:
                        p_rasp = float(p_rasp) if p_rasp is not None else None
                    except ValueError:
                        p_rasp = None

                    if p_rasp is None or current_machine.id_condition_type == ConditionType.query.filter_by(name="планируемый").first().id:
                        p_rasp = 0

                    print(f"Располагаемая мощность для машины {current_machine.machine_number}, год {year}: {p_rasp}")
                    
                    machine_power = MachinePower.query.filter_by(year_number=year, id_machine=current_machine.id).first()
                    if machine_power:
                        machine_power.p_rasp = p_rasp if p_rasp is not None else machine_power.p_rasp
                        machine_power.p_ogr = machine_power.p_ust - machine_power.p_rasp
                        db.session.add(machine_power)

                db.session.commit()
                previous_was_machine = False 

    return {'message': f'Данные успешно загружены пользователем {user}'}

from io import BytesIO

def export_station_list_to_excel(user, filters=None):
    """Экспортирует данные электростанций в Excel и возвращает бинарный поток."""

    log_to_db(user, "Начата выгрузка таблицы электростанций из базы данных")
    log_to_db(user, "Параметры экспорта", f"Фильтры: {filters}")

    query = get_filtered_stations(**filters)
    station_list = query.all()

    # Собираем уникальные компании для каждой станции
    for station in station_list:
        gen_companies = {machine.gen_company.name for machine in station.machines if machine.gen_company}
        station.gen_companies = "\n".join(gen_companies)  # Добавляем перенос строки

    # Получаем список всех годов
    all_years = list(range(2024, 2032))

    data = []

    # Получаем название **региональной энергосистемы** для субъекта РФ
    regional_energy_system_name = ""
    if station.regional_district and station.regional_district.regional_energy_systems:
        regional_energy_system_name = ", ".join(
            res.name for res in station.regional_district.regional_energy_systems
        )

    # Добавляем строку с региональной энергосистемой
    data.append({
        "Электростанция": regional_energy_system_name,
        "Генерирующая компания": "",
        "Станционный номер": "",
        "Тип генерирующего оборудования": "",
        "Вид топлива": "",
        **{year: "" for year in all_years},
        "Примечание": "",
    })

    for station in station_list:
        station_total_p_ust = {year: 0 for year in all_years}  # Словарь для суммарной мощности
            
        # Добавляем строку с названием электростанции
        data.append({
            "Электростанция": station.name,
            "Генерирующая компания": station.gen_companies,
            "Станционный номер": "",
            "Тип генерирующего оборудования": "",
            "Вид топлива": "",
            **{year: "" for year in all_years},
            "Примечание": "",
        })


        for machine in station.machines:
            row = {
                "Электростанция": machine.machine_group,
                "Генерирующая компания": "",
                "Станционный номер": machine.machine_number,
                "Тип генерирующего оборудования": machine.machine_name,
                "Вид топлива": "",
                **{year: "" for year in all_years},
                "Примечание": machine.note,
            }

            # Добавляем мощности по годам
            for year in all_years:
                power_value = next(
                    (p.p_ust for p in machine.machine_powers if p.year.number == year), 0
                )
                row[year] = power_value
                station_total_p_ust[year] += power_value  # Считаем суммарную мощность

            data.append(row)

        # 🔹 Добавляем строку "Установленная мощность, всего" по станции
        total_row = {
            "Электростанция": "Установленная мощность, всего",
            "Генерирующая компания": "",
            "Станционный номер": "–",
            "Тип генерирующего оборудования": "–",
            "Вид топлива": "–",
            **{year: station_total_p_ust[year] for year in all_years},
            "Примечание": "",
        }

        data.append(total_row)

    log_to_db(user, "Подготовка данных для экспорта электростанций в Excel", f"Записей для экспорта: {len(data)}")

    df = pd.DataFrame(data)
    df = df.fillna("")

    # Создание Excel-файла
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, header=False, startrow=6, sheet_name="Приложение А")
        workbook = writer.book
        workbook.use_nan_inf_to_errors = True
        worksheet = writer.sheets["Приложение А"]

        title_format =  workbook.add_format({
            'font_name': 'Times New Roman',  # Устанавливаем шрифт
            'font_size': 13,                 # Размер шрифта 13pt
            'bold': True,
            'align': 'center',               # Выравнивание текста по левому краю
            'valign': 'vcenter',             # Выравнивание по центру по вертикали
        })

        subtitle_format = workbook.add_format({
            'font_name': 'Times New Roman',  # Устанавливаем шрифт
            'font_size': 13,                 # Размер шрифта 13pt
            'align': 'left',                 # Выравнивание текста по левому краю
            'valign': 'vcenter',             # Выравнивание по центру по вертикали
            'text_wrap': True,               # Перенос слов (разрыв строк)
        })

        year_format = workbook.add_format({
            'align': 'center', 'valign': 'vcenter', 'border': 1, 'bold': True
        })

        text_format = workbook.add_format({
            'font_name': 'Times New Roman',  # Устанавливаем шрифт
            'font_size': 10,                 # Размер шрифта 10pt
            'align': 'left',                 # Выравнивание текста по левому краю
            'valign': 'vcenter',             # Выравнивание по центру по вертикали
            'text_wrap': True,               # Перенос слов (разрыв строк)
            'border': 1                      # Границы ячейки
        })

        text_center_format = workbook.add_format({
            'font_name': 'Times New Roman',  # Устанавливаем шрифт
            'font_size': 10,                 # Размер шрифта 10pt
            'align': 'center',               # Выравнивание текста по центру
            'valign': 'vcenter',             # Выравнивание по центру по вертикали
            'text_wrap': True,               # Перенос слов (разрыв строк)
            'border': 1                      # Границы ячейки
        })


        # Заголовки
        worksheet.merge_range("A1:N1", "ПРИЛОЖЕНИЕ А", title_format)
        worksheet.merge_range("A2:N2", "Перечень электростанций, действующих и планируемых к сооружению, расширению, модернизации и выводу из эксплуатации", title_format)
        worksheet.merge_range("A3:N3", "", title_format)
        worksheet.merge_range("A4:N4", "Таблица А.1 – Перечень действующих электростанций, с указанием состава генерирующего оборудования и планов по выводу из эксплуатации, реконструкции (модернизации или перемаркировке), вводу в эксплуатацию генерирующего оборудования в период до 2030 года", subtitle_format)
        worksheet.set_row(3, 42)

        # Шапка таблицы
        col_names = ["Электростанция", "Генерирующая компания", "Станционный номер",
                     "Тип генерирующего оборудования", "Вид топлива", "Примечание"]
        num_cols = len(col_names) - 1  # Без "Примечание"

        # Объединяем и форматируем первый столбец (первая колонка шапки)
        worksheet.merge_range(4, 0, 5, 0, col_names[0], text_format)

        # Объединяем и форматируем остальные столбцы
        for col_num in range(1, num_cols):  # Начинаем с 1, чтобы не дублировать первый столбец
            worksheet.merge_range(4, col_num, 5, col_num, col_names[col_num], text_center_format)


        # Первая строка над мощностями
        worksheet.merge_range(4, num_cols, 4, num_cols + len(all_years) - 1, "Установленная мощность (МВт)", text_center_format)

        # Вторая строка - годы
        for idx, year in enumerate(all_years):
            col_num = num_cols + idx
            worksheet.write(5, col_num, year, text_center_format)

        # Добавляем "Примечание" в 1 строке
        worksheet.merge_range(4, num_cols + len(all_years), 5, num_cols + len(all_years), "Примечание", text_center_format)

        # Определяем индекс нужного столбца
        station_column_name = "Электростанция"
        gen_company_column_name = "Генерирующая компания"
        machine_number_column_name = "Станционный номер"
        machine_name_column_name = "Тип генерирующего оборудования"
        fuel_type_name = "Вид топлива"
        note_column_name = "Примечание"

        station_col_idx = df.columns.get_loc(station_column_name)
        gen_company_col_idx = df.columns.get_loc(gen_company_column_name)
        machine_number_col_idx = df.columns.get_loc(machine_number_column_name)
        machine_name_col_idx = df.columns.get_loc(machine_name_column_name)
        fuel_type_col_idx = df.columns.get_loc(fuel_type_name)
        p_ust_col_idxs = {year: df.columns.get_loc(year) for year in all_years}
        note_column_col_idx = df.columns.get_loc(note_column_name)

        # Применяем ширину (217 пикселей ≈ 30 Excel ширина) и формат только к этому столбцу
        worksheet.set_column(station_col_idx, station_col_idx, 30.29, text_format)
        worksheet.set_column(gen_company_col_idx, gen_company_col_idx, 17, text_center_format)
        worksheet.set_column(machine_number_col_idx, machine_number_col_idx, 12, text_center_format)
        worksheet.set_column(machine_name_col_idx, machine_name_col_idx, 20.86, text_center_format)
        worksheet.set_column(fuel_type_col_idx, fuel_type_col_idx, 11.29, text_center_format)
        
        for year in all_years:
            col_idx = p_ust_col_idxs[year]
            worksheet.set_column(col_idx, col_idx, 8, text_center_format)

        worksheet.set_column(note_column_col_idx, note_column_col_idx, 28.71, text_format)

        # Определяем диапазон объединения (все столбцы)
        start_col = 0
        end_col = len(df.columns) - 1  # Последний столбец

        # Найти индекс строки, где находится региональная энергосистема (первое её появление в data)
        regional_row_idx = next(i for i, row in enumerate(data) if row["Электростанция"] == regional_energy_system_name)

        # Объединяем ячейки в Excel
        worksheet.merge_range(regional_row_idx + 6, start_col, regional_row_idx + 6, end_col,  # +6 из-за заголовков
                            regional_energy_system_name, text_format)

        # Определяем последнюю заполненную строку
        last_row = len(df) + 6  # +5 из-за заголовков

        # Определяем последний используемый столбец
        last_col = len(df.columns)

        # Создаем пустой стиль (без границ, выравнивания и других атрибутов)
        empty_format = workbook.add_format()

        # Снимаем форматирование с пустых строк после таблицы
        for row_num in range(last_row, 1000):  # 1000 - большое число, можно сделать динамическим
            worksheet.set_row(row_num, None, empty_format)

        # Снимаем форматирование с пустых столбцов после таблицы
        for col_num in range(last_col + 1, 50):  # 50 - запасное число столбцов
            worksheet.set_column(col_num, col_num, None, empty_format)


    output.seek(0)

    log_to_db(user, "Экспорт завершён", f"Экспортировано записей: {len(data)}")
    return output






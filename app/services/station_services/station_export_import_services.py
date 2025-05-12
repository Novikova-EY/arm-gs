from app import db
import re
import pandas as pd
from datetime import datetime
import traceback
from io import BytesIO
import math
from flask import flash
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from app.services.logging_services.logging_service import log_to_db
from app.models import (
    EnergyUnit, RegionalDistrict, Station, StationType, Machine, 
    MachinePower, MachineFuel, MachineTesType, ConditionType, MachineType, 
    TesType, TesMachineType,  Machine, StationPower, Fuel, GenCompany
)
from app.services.station_services.filters_service import (
        get_filtered_stations
    )
from app.services.station_services.groupped_service import (
        group_machines_by_group_and_fuel
    )
from app.services.reference_services.gen_company_services import (
        clean_name
)


# Функция для конвертации даты в формат 'гггг-мм-дд'
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
    

# Функция для проверки значений дат на NaN и замены на None
def safe_date(value):
    if pd.isna(value):
        return None
    try:
        if isinstance(value, (int, float)) and value > 1000:
            return pd.to_datetime(f"{int(value)}-01-01").date()
        return pd.to_datetime(value, errors='coerce').date()
    except Exception:
        return None


# Функция для проверки полей на NaN и замены на None
def safe_lookup(model, field, value, cleaner=clean_name):
    """Безопасный поиск объекта по справочнику. Возвращает .id или None."""
    try:
        if pd.isna(value):
            return None
        cleaned = cleaner(value) if cleaner else value
        if cleaned in [None, '', float('nan')]:
            return None
        obj = model.query.filter_by(**{field: cleaned}).first()
        return obj.id if obj else None
    except Exception as e:
        print(f"❌ Ошибка при поиске {model.__name__}.{field}='{value}':", e)
        return None


# Функция для сравнения float-значений с учётом погрешности
def floats_equal(a, b, tol=1e-9):
    return a == b or (a is not None and b is not None and math.isclose(a, b, rel_tol=tol, abs_tol=tol))


def to_decimal(val, digits=9):
    try:
        return Decimal(str(val)).quantize(Decimal(f"1.{'0'*digits}"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(0)
    
def normalize(v):
    if isinstance(v, Decimal):
        return round(v, 9)  # или другой нужный уровень точности
    if isinstance(v, float):
        return round(v, 9)
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    try:
        return int(v)
    except (ValueError, TypeError):
        return v

def update_if_changed(obj, field, new_value, changes, display_name=None):
    old_value = getattr(obj, field)

    if normalize(old_value) != normalize(new_value):
        changes.append(f"{display_name or field}: {old_value} → {new_value}")
        setattr(obj, field, new_value)


# Вспомогательная функция: создание или обновление станции
def handle_station(row, user):
    station_name = clean_name(row['station_name'])

    raw_district = row.get('regional_district')
    regional_district_name = clean_name(raw_district) if not pd.isna(raw_district) else None

    # Найти региональный округ
    regional_district = RegionalDistrict.query.filter_by(name=regional_district_name).first()
    if not regional_district:
        energy_unit = EnergyUnit.query.filter_by(name=regional_district_name).first()
        if energy_unit and energy_unit.regional_district:
            regional_district = energy_unit.regional_district

    # Энергоузел по умолчанию (или найденный)
    energy_unit = EnergyUnit.query.filter_by(id=100).first() or safe_lookup(EnergyUnit, 'id', 100, cleaner=None)
    condition_type = ConditionType.query.filter_by(name="действующий").first()

    group_id = row.get("id_group")
    group_id = int(group_id) if not pd.isna(group_id) and str(group_id).isdigit() else None

    note = clean_name(row.get('note')) if not pd.isna(row.get('note')) else None

    station = Station.query.filter_by(
        name=station_name,
        id_regional_district=regional_district.id if regional_district else None
    ).first()

    if not station:
        station = Station(
            name=station_name,
            id_regional_district=regional_district.id if regional_district else None,
            id_condition_type=condition_type.id if condition_type else None,
            id_energy_unit=energy_unit.id if energy_unit else None,
            note=note if note else None,
        )
        db.session.add(station)
        db.session.commit()
        log_to_db(user, "Создание станции", f"Создана станция: {station_name}")
        print(f"Создание станции, Создана станция: {station_name}")
    else:
        changes = {}
        if station.id_regional_district != (regional_district.id if regional_district else None):
            changes['id_regional_district'] = regional_district.id if regional_district else None
        if station.id_energy_unit != (energy_unit.id if energy_unit else None):
            changes['id_energy_unit'] = energy_unit.id if energy_unit else None
        if station.note != note:
            changes['note'] = note

        if changes:
            for k, v in changes.items():
                setattr(station, k, v)
            db.session.commit()
            log_to_db(user, "Обновление станции", f"Обновлена станция: {station.name} ({station.regional_district.name}), изменения: {changes}")
            print(f"Обновление станции, Обновлена станция: {station.name} ({station.regional_district.name}), изменения: {changes}")

    return station


# Вспомогательная функция: создание или обновление агрегата
def handle_machine(row, current_station, user):
    machine_name = clean_name(row['machine_name'])

    machine_group = row.get('machine_group')
    if pd.isna(machine_group) or machine_group in [None, 'nan', 'NaN', '']:
        machine_group = ""
    else:
        if isinstance(machine_group, (int, float)):
            machine_group = str(int(machine_group)) if machine_group.is_integer() else str(machine_group)
        else:
            machine_group = str(machine_group).strip()

    machine_number = clean_name(row.get('machine_number'))
    if pd.isna(machine_number) or machine_number in [None, 'nan', 'NaN', '']:
        machine_number = ""
    else:
        if isinstance(machine_number, (int, float)):
            machine_number = str(int(machine_number)) if machine_number.is_integer() else str(machine_number)
        else:
            machine_number = str(machine_number).strip()

    gen_company = GenCompany.query.filter_by(name=clean_name(row['gen_company'])).first()

    condition_type = ConditionType.query.filter_by(name="действующий").first()

    raw_year = row.get('date_exploitation')
    if not pd.isna(raw_year):
        try:
            date_exploitation = int(str(raw_year).strip())
        except ValueError:
            date_exploitation = None
    else:
        date_exploitation = None

    if row.get('p_2024') == 0 or (date_exploitation and date_exploitation > 2025):
        condition_type = ConditionType.query.filter_by(name="планируемый").first()

    machine = Machine.query.filter_by(
        machine_number=machine_number,
        machine_group=machine_group,
        machine_name=machine_name,
        id_station=current_station.id
    ).first()

    if machine:
        changes = []
        update_if_changed(machine, 'machine_name', machine_name, changes)
        update_if_changed(machine, 'machine_group', machine_group, changes)
        update_if_changed(machine, 'date_exploitation', date_exploitation, changes)
        update_if_changed(machine, 'id_gen_company', gen_company.id if gen_company else None, changes)
        update_if_changed(machine, 'id_station_type', safe_lookup(StationType, 'name', row.get('station_type')), changes)
        update_if_changed(machine, 'id_tes_machine_type', safe_lookup(TesMachineType, 'name', row.get('tes_machine_type')), changes)
        update_if_changed(machine, 'id_machine_type', safe_lookup(MachineType, 'id', 100, cleaner=None), changes)

        # Исключаем автоматические поля
        date_fields = [
            'date_commission_fact',
            'date_joining_expected', 'date_joining_fact',
            'date_detatchment_fact',
            'date_decompressing_fact', 'date_modernization_expected',
            'date_relabing_fact', 'date_update_fact'
        ]
        for field in date_fields:
            update_if_changed(machine, field, convert_date(row.get(field)), changes)

        if not pd.isna(row.get('note')):
            note_val = clean_name(row['note'])
            update_if_changed(machine, 'note', note_val, changes)

        if changes:
            db.session.commit()
            log_to_db(user, f"Обновление агрегата электростанции {current_station.name} ({current_station.regional_district.name})", f"Агрегат группы {machine_group} № {machine_number}, {machine_name} обновлен: {', '.join(changes)}")
            print(f"Обновление агрегата электростанции {current_station.name} ({current_station.regional_district.name}), Агрегат группы {machine_group} № {machine_number}, {machine_name} обновлен: {', '.join(changes)}")

    else:
        machine = Machine(
            id_condition_type=condition_type.id if condition_type else None,
            id_gen_company=gen_company.id if gen_company else None,
            id_station=current_station.id,
            machine_number=machine_number,
            machine_name=machine_name,
            machine_group=machine_group,
            note=clean_name(row['note']) if not pd.isna(row.get('note')) else None,
            id_station_type=safe_lookup(StationType, 'name', row.get('station_type')),
            id_machine_type=safe_lookup(MachineType, 'id', 100, cleaner=None),
            id_tes_machine_type=safe_lookup(TesMachineType, 'name', row.get('tes_machine_type')),
            date_exploitation=date_exploitation,
            date_commission_fact=safe_date(row.get('date_commission_fact')),
            date_joining_expected=safe_date(row.get('date_joining_expected')),
            date_joining_fact=safe_date(row.get('date_joining_fact')),
            date_detatchment_fact=safe_date(row.get('date_detatchment_fact')),
            date_decompressing_expected=safe_date(row.get('date_decompressing_expected')),
            date_decompressing_fact=safe_date(row.get('date_decompressing_fact')),
            date_modernization_expected=safe_date(row.get('date_modernization_expected')),
            date_relabing_fact=safe_date(row.get('date_relabing_fact')),
            date_update_fact=safe_date(row.get('date_update_fact')),
        )
        db.session.add(machine)
        db.session.flush()
        log_to_db(user, f"Создание агрегата электростанции {current_station.name} ({current_station.regional_district.name})", f"Создан агрегат: {machine_number} - {machine_name}")
        print(f"Создание агрегата электростанции {current_station.name} ({current_station.regional_district.name}), Создан агрегат: {machine_number} - {machine_name}")

    # Если в Excel явно указана дата модернизации — установим флаг, чтобы не переопределять автоматически
    if not pd.isna(row.get('date_modernization_expected')):
        machine._modernization_set_manually = True
        
    return machine


# Вспомогательная функция: присвоение типа ТЭС агрегату на диапазон лет
def assign_machine_types(machine, row, start_year, end_year, user):
    # Получаем id типа ТЭС из строки
    tes_type_id = safe_lookup(TesType, 'name', row.get('tes_type'))
    tes_type_name = TesType.query.get(tes_type_id).name if tes_type_id else 'не указано'

    for year in range(start_year, end_year + 1):
        record = MachineTesType.query.filter_by(year_number=year, id_machine=machine.id).first()

        if record:
            if record.id_tes_type != tes_type_id:
                old_name = record.tes_type.name if record.tes_type else 'не указано'
                record.id_tes_type = tes_type_id
                log_to_db(
                    user, f"Обновление типа ТЭС электростанции {machine.machine_station.name} ({machine.machine_station.regional_district.name})",
                    f"Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: {old_name} → {tes_type_name}"
                )
                print(f"Обновление типа ТЭС электростанции {machine.machine_station.name} ({machine.machine_station.regional_district.name}). Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: {old_name} → {tes_type_name}")
        else:
            new_record = MachineTesType(
                year_number=year,
                id_machine=machine.id,
                id_tes_type=tes_type_id
            )
            db.session.add(new_record)
            log_to_db(
                user, f"Создание типа ТЭС электростанции {machine.machine_station.name} ({machine.machine_station.regional_district.name})",
                f"Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: {tes_type_name}"
            )
            print(f"Создание типа ТЭС электростанции {machine.machine_station.name} ({machine.machine_station.regional_district.name}). Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: {tes_type_name}")


# Вспомогательная функция: запись установленной мощности агрегата на диапазон лет
def assign_machine_power_p_ust(machine, row, start_year, end_year, user):
    for year in range(start_year, end_year + 1):
        val = row.get(f'p_{year}')
        p_ust = to_decimal(val) if not pd.isna(val) else Decimal(0)

        power = MachinePower.query.filter_by(year_number=year, id_machine=machine.id).first()

        if power:
            if power.p_ust != p_ust:
                old_val = power.p_ust
                power.p_ust = p_ust
                db.session.add(power)
                log_to_db(
                    user, f"Обновление мощности электростанции {machine.machine_station.name} ({machine.machine_station.regional_district.name})",
                    f"Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: p_ust {old_val} → {p_ust}"
                )
                print(f"Обновление мощности электростанции {machine.machine_station.name} ({machine.machine_station.regional_district.name}), Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: p_ust {old_val} → {p_ust}")
        else:
            new_power = MachinePower(
                year_number=year,
                id_machine=machine.id,
                p_ust=p_ust,
            )
            db.session.add(new_power)
            log_to_db(
                user, f"Создание мощности электростанции {machine.machine_station.name} ({machine.machine_station.regional_district.name})",
                f"Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: p_ust {p_ust}"
            )
            print(f"Создание мощности электростанции {machine.machine_station.name} ({machine.machine_station.regional_district.name}), Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: p_ust {p_ust}")


# Вспомогательная функция: запись располагаемой мощности и автоматическое удаление/добавление топлива
def assign_machine_power_p_rasp(machine, row, start_year, end_year, user):
    if not machine:
        return

    station = machine.machine_station
    district_name = station.regional_district.name if station and station.regional_district else "—"

    for year in range(start_year, end_year + 1):
        val = row.get(f'p_{year}')
        p_rasp = to_decimal(val) if not pd.isna(val) else Decimal(0)

        machine_power = MachinePower.query.filter_by(year_number=year, id_machine=machine.id).first()

        if machine_power:
            if machine_power.p_rasp != p_rasp:
                old_val = machine_power.p_rasp
                machine_power.p_rasp = p_rasp
                log_to_db(
                    user, f"Обновление p_rasp электростанции {machine.machine_station.name} ({district_name})",
                    f"Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: p_rasp {old_val} → {p_rasp}"
                )
                print(f"Обновление p_rasp электростанции {machine.machine_station.name} ({district_name}), Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: p_rasp {p_rasp}")
        else:
            machine_power = MachinePower(
                year_number=year,
                id_machine=machine.id,
                p_ust=0,
                p_rasp=p_rasp,
                p_ogr=0 - p_rasp
            )
            db.session.add(machine_power)
            log_to_db(
                user, f"Создание p_rasp электростанции {machine.machine_station.name} ({district_name})",
                f"Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: p_rasp {p_rasp}"
            )
            print(f"Создание p_rasp электростанции {machine.machine_station.name} ({district_name}), Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: p_rasp {p_rasp}")


# Отдельная функция для пересчёта ограничений мощности
def update_machine_power_ogr(machine, start_year, end_year, user):
    for year in range(start_year, end_year + 1):
        power = MachinePower.query.filter_by(year_number=year, id_machine=machine.id).first()
        if power:
            old_ogr = power.p_ogr
            val = (power.p_ust or 0) - (power.p_rasp or 0)
            power.p_ogr = to_decimal(val) if not pd.isna(val) else Decimal(0)

            if old_ogr != power.p_ogr:
                log_to_db(
                    user, f"Пересчёт ограничения мощности электростанции {machine.machine_station.name} ({machine.machine_station.regional_district.name}))",
                    f"Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: p_ogr {old_ogr} → {power.p_ogr}"
                )
                print(f"Пересчёт ограничения мощности электростанции {machine.machine_station.name} ({machine.machine_station.regional_district.name}), Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: p_ogr {old_ogr} → {power.p_ogr}")


# Вспомогательная функция: расчёт агрегированной мощности станции по годам
def update_station_power(station, start_year, end_year, user):
    for year in range(start_year, end_year + 1):
        total_values = db.session.query(
            db.func.sum(MachinePower.p_ust).label("total_p_ust"),
            db.func.sum(MachinePower.p_ogr).label("total_p_ogr"),
            db.func.sum(MachinePower.p_rasp).label("total_p_rasp")
        ).join(Machine).filter(
            Machine.id_station == station.id,
            MachinePower.year_number == year
        ).first()

        total_p_ust = total_values.total_p_ust or 0
        total_p_ogr = total_values.total_p_ogr or 0
        total_p_rasp = total_values.total_p_rasp or 0

        record = StationPower.query.filter_by(id_station=station.id, year_number=year).first()
        updates = []

        if record:
            if record.p_ust != total_p_ust:
                updates.append(f"p_ust {record.p_ust} → {total_p_ust}")
                record.p_ust = total_p_ust
            if record.p_ogr != total_p_ogr:
                updates.append(f"p_ogr {record.p_ogr} → {total_p_ogr}")
                record.p_ogr = total_p_ogr
            if record.p_rasp != total_p_rasp:
                updates.append(f"p_rasp {record.p_rasp} → {total_p_rasp}")
                record.p_rasp = total_p_rasp

            if updates:
                log_to_db(user, f"Обновление мощности электростанции {station.name} ({station.regional_district.name})",
                          f"Станция: {station.name}, год {year}: " + ", ".join(updates))
                print(f"Обновление мощности электростанции {station.name} ({station.regional_district.name}), Станция: {station.name}, год {year}: " + ", ".join(updates))
        else:
            record = StationPower(
                id_station=station.id,
                year_number=year,
                p_ust=total_p_ust,
                p_ogr=total_p_ogr,
                p_rasp=total_p_rasp
            )
            db.session.add(record)
            log_to_db(user, f"Создание мощности электростанции ({station.name})",
                      f"Станция: {station.name}, год {year}: p_ust {total_p_ust}, p_ogr {total_p_ogr}, p_rasp {total_p_rasp}")
            print(f"Создание мощности электростанции ({station.name}), Станция: {station.name}, год {year}: p_ust {total_p_ust}, p_ogr {total_p_ogr}, p_rasp {total_p_rasp}")


# Вспомогательная функция: запись топлива агрегата по годам
def assign_machine_fuel(machine, row, start_year, end_year, user):
    station_type_name = StationType.query.get(machine.id_station_type).name if machine.id_station_type else None

    fuel_type_mapping = {
        "газ": 1,
        "уголь": 2,
        "прочее": 3
    }

    for year in range(start_year, end_year + 1):
        fuel_name = clean_name(row.get(f'fuel_{year}'))
        fuel_type_id = fuel_type_mapping.get(fuel_name)
        fuel = Fuel.query.filter_by(id_fuel_type=fuel_type_id).first() if fuel_type_id else None

        if not fuel or station_type_name != "ТЭС":
            continue

        fuel_record = MachineFuel.query.filter_by(year_number=year, id_machine=machine.id).first()

        if fuel_record:
            if fuel_record.id_fuel != fuel.id:
                old_name = fuel_record.fuel.name if fuel_record.fuel else 'не указано'
                fuel_record.id_fuel = fuel.id
                log_to_db(user, f"Обновление топлива электростанции {machine.machine_station.name} ({machine.machine_station.regional_district.name})",
                          f"Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: {old_name} → {fuel.name}")
                print(f"Обновление топлива электростанции {machine.machine_station.name} ({machine.machine_station.regional_district.name}), Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: {old_name} → {fuel.name}")
        else:
            new_fuel = MachineFuel(
                year_number=year,
                id_machine=machine.id,
                id_fuel=fuel.id
            )
            db.session.add(new_fuel)
            log_to_db(user, f"Создание топлива электростанции {machine.machine_station.name} ({machine.machine_station.regional_district.name})",
                      f"Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: {fuel.name}")
            print(f"Создание топлива электростанции {machine.machine_station.name} ({machine.machine_station.regional_district.name}), Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: {fuel.name}")


# Вспомогательная функция: автоматическое удаление/добавление топлива
def cleanup_machine_fuel(machine, row, start_year, end_year, user):
    fuel_type_mapping = {
        "газ": 1,
        "уголь": 2,
        "прочее": 3
    }

    station = machine.machine_station
    district_name = station.regional_district.name if station and station.regional_district else "—"

    for year in range(start_year, end_year + 1):
        p_val = row.get(f'p_{year}')
        fuel_val = row.get(f'fuel_{year}')

        try:
            p_ust = float(p_val) if not pd.isna(p_val) else 0
        except ValueError:
            p_ust = 0

        # Получаем установленную мощность агрегата на этот год
        machine_power = MachinePower.query.filter_by(year_number=year, id_machine=machine.id).first()
        p_ust = machine_power.p_ust if machine_power else 0

        machine_fuel = MachineFuel.query.filter_by(year_number=year, id_machine=machine.id).first()

        if p_ust == 0:
            # Установленная мощность 0 — удаляем топливо, если есть
            if machine_fuel:
                db.session.delete(machine_fuel)
                log_to_db(
                    user,
                    f"Удаление топлива электростанции {machine.machine_station.name} ({district_name})",
                    f"Агрегат: {machine.machine_number}, год {year}: удалено топливо (p_ust = 0)"
                )
                print(f"Удаление топлива электростанции {machine.machine_station.name} ({district_name}), Агрегат: {machine.machine_number}, год {year}: удалено топливо (p_ust = 0)")
            continue

        # Если p_ust > 0, обрабатываем топливо
        fuel_name = clean_name(fuel_val)
        fuel_type_id = fuel_type_mapping.get(fuel_name)
        fuel = Fuel.query.filter_by(id_fuel_type=fuel_type_id).first() if fuel_type_id else None

        if p_ust > 0:
            if not machine_fuel and fuel:
                machine_fuel = MachineFuel(
                    year_number=year,
                    id_machine=machine.id,
                    id_fuel=fuel.id
                )
                db.session.add(machine_fuel)
                log_to_db(
                    user,
                    f"Добавление топлива электростанции {machine.machine_station.name} ({machine.machine_station.regional_district.name})",
                    f"Агрегат: {machine.machine_number}, год {year}: добавлено топливо {fuel.name}"
                )
                print(f"Добавление топлива электростанции {machine.machine_station.name} ({machine.machine_station.regional_district.name}), Агрегат: {machine.machine_number}, год {year}: добавлено топливо {fuel.name}")

            elif machine_fuel and fuel and machine_fuel.id_fuel != fuel.id:
                old_fuel_name = machine_fuel.fuel.name if machine_fuel.fuel else 'не указано'
                machine_fuel.id_fuel = fuel.id
                log_to_db(
                    user,
                    f"Обновление топлива электростанции {machine.machine_station.name} ({machine.machine_station.regional_district.name})",
                    f"Агрегат: {machine.machine_number}, год {year}: топливо {old_fuel_name} → {fuel.name}"
                )
                print(f"Обновление топлива электростанции {machine.machine_station.name} ({machine.machine_station.regional_district.name}), Агрегат: {machine.machine_number}, год {year}: топливо {old_fuel_name} → {fuel.name}")


# Вспомогательная функция: автоматическое добавление годов ввода/вывода в/из эксплуатации
def update_machine_commission_status(machine, start_year, end_year, user):
    station = machine.machine_station
    district_name = station.regional_district.name if station and station.regional_district else "—"

    powers_by_year = {
        power.year_number: power.p_ust
        for power in machine.machine_powers
        if power.p_ust is not None
    }

    # Если есть фактические даты — убираем ожидаемую модернизацию
    if machine.date_relabing_fact or machine.date_update_fact:
        if machine.date_modernization_expected is not None:
            old_year = machine.date_modernization_expected
            machine.date_modernization_expected = None
            db.session.add(machine)
            log_to_db(
                user,
                f"Удалена ожидаемая модернизация агрегата {station.name} ({district_name})",
                f"Агрегат {machine.machine_number} станции '{station.name}': дата модернизации {old_year} удалена, т.к. указаны фактические даты"
            )
            print(f"[Сброс модернизации] {station.name} — агрегат {machine.machine_number}: была {old_year}, удалена из-за наличия фактической даты")

    for year in range(start_year, end_year):
        if year < 2022:
            continue

        curr = powers_by_year.get(year, 0)
        next_ = powers_by_year.get(year + 1, 0)

        # 🔻 Плановый вывод
        if curr and not next_ and not machine.date_decompressing_expected:
            machine.date_decompressing_expected = year + 1
            db.session.add(machine)
            log_to_db(
                user,
                f"Автоматический вывод агрегата электростанции {station.name} ({district_name})",
                f"Агрегат {machine.machine_number} станции '{station.name}': плановый вывод из эксплуатации в {year + 1}"
            )
            print(f"Автоматический вывод агрегата: {station.name} ({district_name}), агрегат {machine.machine_number} — вывод в {year + 1}")

        # 🔺 Плановый ввод
        if not curr and next_ and not machine.date_exploitation:
            machine.date_exploitation = year + 1
            db.session.add(machine)
            log_to_db(
                user,
                f"Автоматический ввод агрегата электростанции {station.name} ({district_name})",
                f"Агрегат {machine.machine_number} станции '{station.name}': ввод в эксплуатацию в {year + 1}"
            )
            print(f"Автоматический ввод агрегата: {station.name} ({district_name}), агрегат {machine.machine_number} — ввод в {year + 1}")

        # 🔧 Модернизация (мощность изменилась, при отсутствии факт-даты и ручного ввода)
        if (
            curr and next_ and curr != next_
            and not getattr(machine, "_modernization_set_manually", False)
            and not (machine.date_relabing_fact or machine.date_update_fact)
            and not machine.date_modernization_expected
        ):
            machine.date_modernization_expected = year + 1
            db.session.add(machine)
            log_to_db(
                user,
                f"Автоматическая модернизация агрегата {station.name} ({district_name})",
                f"Агрегат {machine.machine_number} станции '{station.name}': изменение мощности ({curr} → {next_}) в {year + 1} — год модернизации"
            )
            print(f"[Модернизация] {station.name} — агрегат {machine.machine_number}: {curr} → {next_} в {year + 1}")

    db.session.commit()


# Функция для импорта списка станций с параметрами в базу данных
def import_station_list_from_excel(file, user):
    xls = pd.ExcelFile(file)
    df = xls.parse('список', header=0)
    df = df.dropna(how='all')

    current_station = None
    current_machine = None
    start_year, end_year = 2021, 2031

    for index, row in df.iterrows():
        if row.isnull().all():
            continue

        print(f"\n🔄 Обрабатываем строку {index}...")

        if not (pd.isna(row['regional_district']) and pd.isna(row['station_name'])):
            current_station = handle_station(row, user)

        elif not pd.isna(row.get('machine_name')) and not pd.isna(row.get('gen_company')):
            current_machine = handle_machine(row, current_station, user)
            assign_machine_types(current_machine, row, start_year, end_year, user)
            assign_machine_power_p_ust(current_machine, row, start_year, end_year, user)
            cleanup_machine_fuel(current_machine, row, start_year, end_year, user)
        
        elif not pd.isna(row.get('station_type')) and not pd.isna(row.get('gen_company')):
            assign_machine_power_p_rasp(current_machine, row, start_year, end_year, user)
            update_machine_commission_status(current_machine, start_year, end_year, user)

            has_rasp_values = any(not pd.isna(row.get(f'p_{y}')) for y in range(start_year, end_year + 1))
            if has_rasp_values:
                update_machine_power_ogr(current_machine, start_year, end_year, user)
            

    # После всех строк: расчёт агрегированных мощностей по каждой станции
    station_ids = df['station_name'].dropna().unique()
    for name in station_ids:
        station = Station.query.filter_by(name=clean_name(name)).first()
        if station:
            update_station_power(station, start_year, end_year, user)

    db.session.commit()
    print(f"✅Данные успешно загружены пользователем {user}")
    return {"message": f"Данные успешно загружены пользователем {user}"}


def import_station_list_from_excel_old(file, user):
    xls = pd.ExcelFile(file)
    df = xls.parse('список', header=0)
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

            energy_unit = EnergyUnit.query.filter_by(id=100).first()

            if not regional_district:
                energy_unit = EnergyUnit.query.filter_by(name=regional_district_name).first()
                print("energy_unit=", energy_unit)
                if energy_unit:
                    regional_district = energy_unit.regional_district if energy_unit.regional_district else None
                    print(f"[!] Регион '{regional_district}' не найден напрямую, получен из EnergyUnit ID={energy_unit.id}")

            station_name = clean_name(row['station_name'])
            station = Station.query.filter_by(name=station_name).first()

            condition_type = ConditionType.query.filter_by(name="действующий").first()

            if not station:
                station = Station(
                    name=station_name,
                    id_regional_district=regional_district.id if regional_district else None,
                    id_condition_type=condition_type.id if condition_type else None,
                    id_energy_unit=energy_unit.id if energy_unit else safe_lookup(EnergyUnit, 'id', 100, cleaner=None),
                )
                db.session.add(station)
                db.session.commit()
                log_to_db(user, "Создание станции", f"Создана станция: {station_name}")
                print("Создана электростанция", station_name)
            else:
                changes = {}
                if station.id_regional_district != (regional_district.id if regional_district else None):
                    changes['id_regional_district'] = regional_district.id if regional_district else None
                
                if station.id_energy_unit != (energy_unit.id if energy_unit else None):
                    changes['id_energy_unit'] = energy_unit.id if energy_unit else None

                if changes:
                    for key, value in changes.items():
                        setattr(station, key, value)
                    db.session.commit()
                    log_to_db(user, "Обновление станции", f"Обновлена станция: {station.name}, изменения: {changes}")
                    print("Обновлена электростанция", station_name)

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
            if row.get('p_2024') == 0 or safe_date(row.get("date_exploitation")) > 2025:
                condition_type = ConditionType.query.filter_by(name="планируемый").first()

            # Если machine_number является None, то выполняем запрос по machine_name
            machine = Machine.query.filter_by(machine_number=machine_number, machine_group=machine_group, id_station=current_station.id).first()

            id_tes_machine_type = None
            if not pd.isna(row.get('tes_machine_type')):
                tes_machine_type_obj = TesMachineType.query.filter_by(
                    name=clean_name(row['tes_machine_type'])
                ).first()
                if tes_machine_type_obj:
                    id_tes_machine_type = tes_machine_type_obj.id

            if machine:
                print(f"Агрегат группы {machine_group} № {machine_number} - {machine_name} уже существует, обновляем данные.")
                changes = []

                update_if_changed(machine, 'machine_name', machine_name, changes)
                update_if_changed(machine, 'machine_group', machine_group, changes)
                update_if_changed(machine, 'id_gen_company', gen_company.id if gen_company else None, changes)
                update_if_changed(machine, 'id_station_type', safe_lookup(StationType, 'name', row.get('station_type')), changes)
                update_if_changed(machine, 'id_tes_type', safe_lookup(TesType, 'name', row.get('tes_type')), changes)
                update_if_changed(machine, 'id_tes_machine_type', safe_lookup(TesMachineType, 'name', row.get('tes_machine_type')), changes)
                update_if_changed(machine, 'id_machine_type', safe_lookup(MachineType, 'id', 100, cleaner=None), changes)

                # Обновление всех дат
                date_fields = [
                    'date_commission_fact',
                    'date_joining_expected', 'date_joining_fact',
                    'date_detatchment_fact', 'date_decompressing_expected',
                    'date_decompressing_fact', 'date_modernization_expected',
                    'date_relabing_fact', 'date_update_fact'
                ]
                for field in date_fields:
                    update_if_changed(machine, field, safe_date(row.get(field)), changes)

                # Примечание
                note_val = clean_name(row['note']) if not pd.isna(row.get('note')) else None
                update_if_changed(machine, 'note', note_val, changes)

                if changes:
                    db.session.commit()
                    log_to_db(user, "Обновление агрегата", f"Агрегат группы {machine_group} № {machine_number}, {machine_name} обновлен: {', '.join(changes)}")

                print("✅ Проверка завершена, изменения:", changes)
                print(f"Обновлен агрегат группы {machine_group} № {machine_number}, {machine_name}")

            else:
                print(f"Создаем новый агрегат группы {machine_group} № {machine_number} - {machine_name}.")

                machine = Machine(
                    id_condition_type=condition_type.id if condition_type else None,
                    id_gen_company=gen_company.id if gen_company else None,
                    id_station=current_station.id,
                    machine_number=machine_number,
                    machine_name=machine_name,
                    machine_group=machine_group,
                    note=clean_name(row['note']) if not pd.isna(row.get('note')) else None,
                    id_station_type=safe_lookup(StationType, 'name', row.get('station_type')),
                    id_machine_type=safe_lookup(MachineType, 'id', 100, cleaner=None),
                    id_tes_machine_type=safe_lookup(TesMachineType, 'name', row.get('tes_machine_type')),

                    date_commission_fact=safe_date(row.get('date_commission_fact')),
                    date_joining_expected=safe_date(row.get('date_joining_expected')),
                    date_joining_fact=safe_date(row.get('date_joining_fact')),
                    date_detatchment_fact=safe_date(row.get('date_detatchment_fact')),
                    date_decompressing_expected=safe_date(row.get('date_decompressing_expected')),
                    date_decompressing_fact=safe_date(row.get('date_decompressing_fact')),
                    date_modernization_expected=safe_date(row.get('date_modernization_expected')),
                    date_relabing_fact=safe_date(row.get('date_relabing_fact')),
                    date_update_fact=safe_date(row.get('date_update_fact')),
                )

                # Получаем id типа ТЭС из строки
                tes_type_id = safe_lookup(TesType, 'name', row.get('tes_type'))
                tes_type_name = TesType.query.get(tes_type_id).name if tes_type_id else 'не указано'

                # Если мощность = 0, ставим тип по умолчанию
                if p_ust == 0:
                    tes_type_id = 100
                    tes_type_name = 'нулевая мощность'

                # Обработка всех лет от start_year до end_year
                for year in range(start_year, end_year + 1):
                    machine_tes_type = MachineTesType.query.filter_by(
                        year_number=year,
                        id_machine=current_machine.id
                    ).first()

                    if machine_tes_type:
                        # Обновляем, если тип изменился
                        if machine_tes_type.id_tes_type != tes_type_id:
                            old_name = machine_tes_type.tes_type.name if machine_tes_type.tes_type else 'не указано'
                            machine_tes_type.id_tes_type = tes_type_id
                            log_to_db(
                                user, "Обновление типа ТЭС",
                                f"Агрегат: {current_machine.machine_number} - {current_machine.machine_name}, год {year}: "
                                f"{old_name} → {tes_type_name}"
                            )
                    else:
                        # Создаём новую запись
                        machine_tes_type = MachineTesType(
                            year_number=year,
                            id_machine=current_machine.id,
                            id_tes_type=tes_type_id
                        )
                        db.session.add(machine_tes_type)
                        log_to_db(
                            user, "Создание типа ТЭС",
                            f"Агрегат: {current_machine.machine_number} - {current_machine.machine_name}, год {year}: {tes_type_name}"
                        )

                    print(f"[{year}] → Тип ТЭС: {tes_type_id} ({tes_type_name})")

                db.session.add(machine)
                db.session.commit()
                log_to_db(user, "Создание агрегата", f"Создан агрегат: {machine_number} - {machine_name}")
                print(f"✅ Успешно создан агрегат: {machine_number} - {machine_name}")

            current_machine = machine
            last_machine = current_machine

            # Вносим установленную мощность, тип ТЭС и топливо     
            last_non_zero_year = None
            was_zero = False

            for year in range(start_year, end_year + 1):
                # Вносим данные о мощности
                p_ust = clean_name(row.get(f'p_{year}'))
                p_ust = None if p_ust in ['', ' ', 'nan', 'NaN'] or pd.isna(p_ust) else p_ust
                try:
                    p_ust = float(p_ust) if p_ust is not None else None
                except ValueError:
                    p_ust = None

                # Приводим к 0, если планируемый
                if p_ust is None or current_machine.id_condition_type == ConditionType.query.filter_by(name="планируемый").first().id:
                    p_ust = 0

                machine_power = MachinePower.query.filter_by(year_number=year, id_machine=current_machine.id).first()
                if machine_power:
                    if machine_power.p_ust != p_ust:
                        machine_power.p_ust = p_ust
                        log_to_db(user, "Обновление мощности", 
                                f"Станция: {current_station.name}, агрегат: {current_machine.machine_number} - {current_machine.machine_name}, "
                                f"год {year}: p_ust {machine_power.p_ust} → {p_ust}")
                else:
                    machine_power = MachinePower(year_number=year, id_machine=current_machine.id, p_ust=p_ust)
                    db.session.add(machine_power)
                    log_to_db(user, "Создание мощности", 
                            f"Станция: {current_station.name}, агрегат: {current_machine.machine_number} - {current_machine.machine_name}, "
                            f"год {year}: p_ust {p_ust}")

                print(f"Установленная мощность для машины {current_machine.machine_number}, год {year}: {p_ust}")

                # Расчёт и обновление StationPower после обработки всех машин станции ===
                for year in range(start_year, end_year + 1):
                    total_values = db.session.query(
                        db.func.sum(MachinePower.p_ust).label("total_p_ust"),
                        db.func.sum(MachinePower.p_ogr).label("total_p_ogr"),
                        db.func.sum(MachinePower.p_rasp).label("total_p_rasp")
                    ).join(Machine).filter(
                        Machine.id_station == current_station.id,
                        MachinePower.year_number == year
                    ).first()

                    total_p_ust = total_values.total_p_ust or 0
                    total_p_ogr = total_values.total_p_ogr or 0
                    total_p_rasp = total_values.total_p_rasp or 0

                    station_power = StationPower.query.filter_by(id_station=current_station.id, year_number=year).first()
                    if station_power:
                        updates = []
                        if station_power.p_ust != total_p_ust:
                            updates.append(f"p_ust {station_power.p_ust} → {total_p_ust}")
                            station_power.p_ust = total_p_ust
                        if station_power.p_ogr != total_p_ogr:
                            updates.append(f"p_ogr {station_power.p_ogr} → {total_p_ogr}")
                            station_power.p_ogr = total_p_ogr
                        if station_power.p_rasp != total_p_rasp:
                            updates.append(f"p_rasp {station_power.p_rasp} → {total_p_rasp}")
                            station_power.p_rasp = total_p_rasp

                        if updates:
                            log_to_db(user, "Обновление мощности станции",
                                    f"Станция: {current_station.name}, год {year}: " + ", ".join(updates))
                    else:
                        station_power = StationPower(
                            id_station=current_station.id,
                            year_number=year,
                            p_ust=total_p_ust,
                            p_ogr=total_p_ogr,
                            p_rasp=total_p_rasp
                        )
                        db.session.add(station_power)
                        log_to_db(user, "Создание мощности станции",
                                f"Станция: {current_station.name}, год {year}: p_ust {total_p_ust}, "
                                f"p_ogr {total_p_ogr}, p_rasp {total_p_rasp}")

                    print(f"Станция {current_station.name}, год {year} — p_ust: {total_p_ust}, p_ogr: {total_p_ogr}, p_rasp: {total_p_rasp}")


                # Вносим данные о типе ТЭС
                tes_type = TesType.query.filter_by(id=current_machine.id_tes_type).first()

                # Присваиваем ID, по умолчанию 100, если p_ust == 0
                if p_ust == 0:
                    tes_type_id = 100
                    tes_type_name = 'не указан (нулевая мощность)'
                else:
                    tes_type_id = tes_type.id if tes_type else None
                    tes_type_name = tes_type.name if tes_type else 'не указано'

                # Проходим по всем годам от start_year до end_year
                for year in range(start_year, end_year + 1):
                    machine_tes_type = MachineTesType.query.filter_by(
                        year_number=year,
                        id_machine=current_machine.id
                    ).first()

                    if machine_tes_type:
                        if machine_tes_type.id_tes_type != tes_type_id:
                            log_to_db(
                                user, "Обновление типа ТЭС",
                                f"Станция: {current_station.name}, агрегат: {current_machine.machine_number} - {current_machine.machine_name}, год {year}: "
                                f"tes_type {machine_tes_type.tes_type.name if machine_tes_type.tes_type else 'не указано'} → {tes_type_name}"
                            )
                            machine_tes_type.id_tes_type = tes_type_id
                    else:
                        new_mtt = MachineTesType(
                            year_number=year,
                            id_machine=current_machine.id,
                            id_tes_type=tes_type_id
                        )
                        db.session.add(new_mtt)
                        log_to_db(
                            user, "Создание типа ТЭС",
                            f"Станция: {current_station.name}, агрегат: {current_machine.machine_number} - {current_machine.machine_name}, год {year}: tes_type {tes_type_name}"
                        )

                    print(f"[Год {year}] Тип ТЭС для машины {current_machine.machine_number}: {tes_type_id}")


                # Вносим данные о типе топлива
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
                        machine_fuel = MachineFuel(year_number=year, id_machine=current_machine.id, id_fuel=fuel.id)
                        db.session.add(machine_fuel)
                        log_to_db(user, "Создание вида топлива", f"Станция: {current_station.name}, агрегат: {current_machine.machine_number} - {current_machine.machine_name}, год {year}: machine_fuel {fuel.name}")
                    else:
                        # Обновляем id_fuel, если оно изменилось
                        if machine_fuel.id_fuel != fuel.id:
                            machine_fuel.id_fuel = fuel.id
                            log_to_db(user, "Обновление вида топлива", f"Станция: {current_station.name}, агрегат: {current_machine.machine_number} - {current_machine.machine_name}, год {year}: machine_fuel {fuel.name} → {machine_fuel.fuel.name}")
                        
                        # Обновляем p_ust, если передано новое значение
                        if p_ust is not None:
                            machine_fuel.p_ust = p_ust

            db.session.commit()
            previous_was_machine = True
            print("Установленные мощности, типы ТЭС и топливо внесены")

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
                    
                    def floats_equal(a, b, eps=1e-6):
                        if a is None and b is None:
                            return True
                        if a is None or b is None:
                            return False
                        return abs(a - b) < eps

                    machine_power = MachinePower.query.filter_by(year_number=year, id_machine=current_machine.id).first()
                    if machine_power:
                        if not floats_equal(machine_power.p_rasp, p_rasp):
                            old_val = machine_power.p_rasp
                            machine_power.p_rasp = p_rasp if p_rasp is not None else old_val
                            machine_power.p_ogr = machine_power.p_ust - machine_power.p_rasp
                            db.session.add(machine_power)
                            log_to_db(
                                user, 
                                "Обновление располагаемой мощности", 
                                f"Станция: {current_station.name}, агрегат: {current_machine.machine_number} - {current_machine.machine_name}, год {year}: p_rasp {old_val} → {p_rasp}"
                            )

                        # Проверка топлива
                        machine_fuel = MachineFuel.query.filter_by(year_number=year, id_machine=current_machine.id).first()
                        if p_rasp == 0 and machine_fuel:
                            db.session.delete(machine_fuel)
                            log_to_db(user, "Удаление топлива", f"Станция: {current_station.name}, агрегат: {current_machine.machine_number} - {current_machine.machine_name}, год {year}: удалено топливо")
                            print(f"Удаляем топливо для машины {current_machine.machine_number}, год {year}, так как p_rasp = 0")
                        elif p_rasp > 0 and not machine_fuel:
                            # Если располагаемая мощность больше 0, но топливо отсутствует, добавляем топливо
                            fuel_name = clean_name(row.get(f'fuel_{year}'))
                            fuel_type_id = fuel_type_mapping.get(fuel_name)

                            if fuel_type_id:
                                fuel = Fuel.query.filter_by(id_fuel_type=fuel_type_id).first()
                                if fuel:
                                    machine_fuel = MachineFuel(
                                        year_number=year,
                                        id_machine=current_machine.id,
                                        id_fuel=fuel.id
                                    )
                                    db.session.add(machine_fuel)
                                    log_to_db(user, "Добавление топлива", f"Станция: {current_station.name}, агрегат: {current_machine.machine_number} - {current_machine.machine_name}, год {year}: добавлено топливо {fuel_name}")
                                    print(f"Добавлено топливо {fuel_name} для машины {current_machine.machine_number}, год {year}")

                db.session.commit()
                previous_was_machine = False 

    return {'message': f'Данные успешно загружены пользователем {user}'}


# Функция для импорта топлива по СО ЕЭС для станций в базу данных
def import_fuel_tes_station_from_excel(file, user):
    xls = pd.ExcelFile(file)

    # Список обрабатываемых листов
    sheet_names = ['Приложение А_ЕЭС', 'Приложение А_ТИТЭС']

    for sheet in sheet_names:
        print(f"\n📄 Обработка листа: {sheet}")
        if sheet not in xls.sheet_names:
            print(f"⚠️ Лист '{sheet}' не найден в файле. Пропускаем.")
            continue

        df = xls.parse(sheet, header=0)
        df = df.dropna(how='all')

        for index, row in df.iterrows():
            if row.isnull().all():
                continue

            print(f"Обрабатываем строку {index}: {row.to_dict()}")

            if not (pd.isna(row['name']) and pd.isna(row['gen_company'])):
                if not pd.isna(row['name']) and pd.isna(row['gen_company']):
                    print("Пропускаем строку, так как есть имя, но нет генкомпании.")
                    continue

                station_name = clean_name(row['name'])
                gen_company_name = clean_name(row['gen_company'])

                if pd.isna(gen_company_name):
                    print("Ошибка: значение генкомпании NaN")
                    continue

                gen_company_obj = GenCompany.query.filter_by(name=gen_company_name).first()
                if gen_company_obj:
                    print(f"Генкомпания найдена: {gen_company_obj.name}")
                else:
                    print(f"⚠️ Генкомпания с именем '{gen_company_name}' не найдена.")
                    continue

                fuel_name = clean_name(row['fuel']) if not pd.isna(row['fuel']) else None
                if pd.isna(fuel_name) or fuel_name is None:
                    print("⚠️ Топливо не указано, пропускаем строку.")
                    continue

                station = Station.query.join(Machine).filter(
                    Station.name == station_name,
                    Machine.gen_company == gen_company_obj
                ).first()

                if station:
                    print(f"✅ Станция найдена: {station_name}")
                    if station.machines:
                        updated_machines = 0
                        for machine in station.machines:
                            if machine.fuel_so != fuel_name:
                                machine.fuel_so = fuel_name
                                updated_machines += 1

                        if updated_machines > 0:
                            db.session.commit()
                            log_to_db(user, "Обновление топлива машин", f"Станция: {station_name}, обновлено агрегатов: {updated_machines}")
                            print(f"🔄 Обновлено топливо для {updated_machines} агрегатов станции '{station_name}'.")
                        else:
                            print(f"ℹ️ Все агрегаты станции '{station_name}' уже имеют актуальное топливо.")
                    else:
                        print(f"⚠️ У станции '{station_name}' нет агрегатов.")
                else:
                    print(f"❌ Станция '{station_name}' с генкомпанией '{gen_company_name}' не найдена.")
            else:
                print("⏭ Имя и генкомпания отсутствуют, пропускаем строку.")

    return {'message': f'Данные по топливу успешно загружены пользователем {user}'}


def convert_to_iso_date(value):
    """
    Преобразует введённую строку в нужный формат:
      - YYYY → возвращается как есть
      - DD.MM.YYYY → преобразуется в YYYY-MM-DD
      - YYYY-MM-DD → возвращается как есть (если корректно)
      - None/пусто → None
    """
    if not value or not value.strip():
        return None

    value = value.strip()

    # Если только год (YYYY)
    if re.match(r'^\d{4}$', value):
        return value

    # Если уже ISO-формат YYYY-MM-DD
    if re.match(r'^\d{4}-\d{2}-\d{2}$', value):
        try:
            datetime.strptime(value, '%Y-%m-%d')  # просто проверка
            return value
        except ValueError:
            raise ValueError("Некорректный формат даты. Используйте YYYY, DD.MM.YYYY или YYYY-MM-DD.")

    # Если формат DD.MM.YYYY
    try:
        date_obj = datetime.strptime(value, '%d.%m.%Y')
        return date_obj.strftime('%Y-%m-%d')
    except ValueError:
        raise ValueError("Некорректный формат даты. Используйте YYYY, DD.MM.YYYY или YYYY-MM-DD.")


def export_station_list_to_excel(user, filters=None):
    """Экспортирует данные электростанций в Excel, создавая отдельный файл для каждого субъекта РФ."""

    log_to_db(user, "Начата выгрузка таблицы электростанций из базы данных")
    log_to_db(user, "Параметры экспорта", f"Фильтры: {filters}")

    query = get_filtered_stations(**filters)
    station_list = query.all()
    station_list = group_machines_by_group_and_fuel(station_list)

    total_stations = len(station_list)
    log_to_db(user, "Найдено станций в БД", f"{total_stations} записей")

    if not station_list:
        log_to_db(user, "Экспорт остановлен", "Нет данных для экспорта.")
        return None

    all_years = list(range(2024, 2032))
    output_files = []
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

    # Группируем станции по субъекту РФ
    regional_districts = {"Без субъекта": []}
    regional_systems = {}
    for station in station_list:
        district_name = station.regional_district.name if station.regional_district else "Без субъекта"
        if district_name not in regional_districts:
            regional_districts[district_name] = []
        regional_districts[district_name].append(station)

        regional_system_name = station.regional_energy_system if station.regional_energy_system else "Неизвестно"
        if regional_system_name not in regional_systems:
            regional_systems[regional_system_name] = set()
        regional_systems[regional_system_name].add(district_name)

    processed_stations = 0
    
    for district_name, stations in regional_districts.items():
        log_to_db(user, f"Выгрузка данных по форме Приложения А к СиПР ЭЭС: {district_name} (Энергосистема: {regional_system_name}) | Найдено станций: {len(stations)}")
        if not stations:
            continue
        try:
            data = []

            # Добавляем строку с названием региональной энергосистемы
            first_station = stations[0]
            regional_system_name = first_station.regional_energy_system if first_station.regional_energy_system else "Неизвестно"

            # Получаем список субъектов для данной энергосистемы
            subject_list = sorted(regional_systems.get(regional_system_name, set()))

            # Определяем, что писать в region_label
            if len(subject_list) > 1:
                region_label = f"{regional_system_name}, в том числе {district_name}"
            else:
                region_label = regional_system_name  # Если субъект один, пишем его напрямую

            data.append({
                "Электростанция": region_label,
                "Генерирующая компания": "",
                "Станционный номер": "",
                "Тип генерирующего оборудования": "",
                "Вид топлива": "",
                **{year: "" for year in all_years},
                "Примечание": "",
            })

            for station in stations:
                processed_stations += 1
                power_data = station.power_by_year() or {}

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

                def extract_year(date_str):
                    """Пытается извлечь год из строки"""
                    if not date_str:
                        return None
                    try:
                        return datetime.strptime(date_str, "%Y-%m-%d").year
                    except ValueError:
                        try:
                            return int(date_str[:4])
                        except ValueError:
                            return None

                def format_full_date(date_str):
                    """Преобразует строку вида '2023-06-16' в '16.06.2023'"""
                    try:
                        dt = datetime.strptime(date_str, "%Y-%m-%d")
                        return dt.strftime("%d.%m.%Y")
                    except Exception:
                        return date_str
    
                # Добавляем строки с установленной мощностью по машинам электростанции
                for machine in station.machines:
                    machine_power_data = {}
                    for mp in machine.machine_powers:
                        if mp.year and mp.p_ust is not None:
                            machine_power_data[mp.year.number] = mp.p_ust

                    note_parts = []
                    if machine.date_decompressing_expected:
                        year = extract_year(machine.date_decompressing_expected)
                        if year:
                            note_parts.append(f"Вывод из эксплуатации в {year} г.")

                    if machine.date_modernization_expected:
                        year = extract_year(machine.date_modernization_expected)
                        if year:
                            note_parts.append(f"Модернизация в {year} г.")

                    if machine.date_relabing_fact:
                        full_date = format_full_date(machine.date_relabing_fact)
                        note_parts.append(f"Перемаркировка {full_date}")

                    full_note = ". ".join(note_parts)
                    if machine.note:
                        if full_note:
                            full_note = f"{full_note}. {machine.note}"
                        else:
                            full_note = machine.note

                    row = {
                        "Электростанция": machine.machine_group,
                        "Генерирующая компания": "",
                        "Станционный номер": machine.machine_number,
                        "Тип генерирующего оборудования": machine.machine_name,
                        "Вид топлива": machine.fuel_so if getattr(machine, 'fuel_so', 0) else "–",
                        **{
                            year: f"{machine_power_data.get(year):.1f}".replace('.', ',')
                            if machine_power_data.get(year)
                            else ""
                            for year in all_years
                        },
                        "Примечание": full_note or "",
                    }
                    data.append(row)

                # Добавляем строку "Установленная мощность, всего" по станции
                total_row = {
                    "Электростанция": "Установленная мощность, всего",
                    "Генерирующая компания": "",
                    "Станционный номер": "–",
                    "Тип генерирующего оборудования": "–",
                    "Вид топлива": "–",
                    **{year: f"{power_data.get(year, {}).get('p_ust', 0):.1f}".replace('.', ',') for year in all_years},
                    "Примечание": "",
                }
                data.append(total_row)

            df = pd.DataFrame(data)
            df = df.fillna("")

            # Создание Excel-файла
            output = BytesIO()
            sheet_name = f"Приложение А"
            file_name = f"Приложение_А_{district_name}_{timestamp}.xlsx".replace(" ", "_")
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, header=False, startrow=6, sheet_name=sheet_name)
                workbook = writer.book
                worksheet = writer.sheets['Приложение А']

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

                # Заменяем первый год на "По состоянию на 01.01.<год>"
                first_year = all_years[0]  # Берем первый год из списка
                year_headers = ["По состоянию на 01.01.{}".format(first_year)] + [str(year) for year in all_years[1:]]

                # Вторая строка - годы
                for idx, year in enumerate(year_headers):
                    col_num = num_cols + idx
                    worksheet.write(5, col_num, year, text_center_format)

                # Устанавливаем особую ширину для первого года
                first_year_col_idx = num_cols  # Столбец первого года
                worksheet.set_column(first_year_col_idx, first_year_col_idx, 12.86, text_center_format)

                # Устанавливаем стандартную ширину для остальных годов
                for idx in range(1, len(all_years)):  # Пропускаем первый год
                    col_num = num_cols + idx
                    worksheet.set_column(col_num, col_num, 8, text_center_format)

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
                
                worksheet.set_column(note_column_col_idx, note_column_col_idx, 28.71, text_format)

                # Определяем диапазон объединения (все столбцы)
                start_col = 0
                end_col = len(df.columns) - 1  # Последний столбец

                # Найти индекс строки, где находится региональная энергосистема (первое её появление в data)
                regional_row_idx = next(
                    (i for i, row in enumerate(data) if row["Электростанция"] == region_label),
                    None
                )

                # Объединяем ячейки в Excel
                worksheet.merge_range(regional_row_idx + 6, start_col, regional_row_idx + 6, end_col,  # +6 из-за заголовков
                                    region_label, text_format)

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
            output_files.append((file_name, output))
    
        except Exception as e:
            error_message = f"❌ Ошибка экспорта субъекта {district_name}: {str(e)}\n{traceback.format_exc()}"
            log_to_db(user, error_message)
            print(error_message)

    log_to_db(user, "Экспорт завершён", f"Обработано {processed_stations} из {total_stations} станций.")

    return output_files[0] if len(output_files) == 1 else output_files




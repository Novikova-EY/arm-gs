from app.extensions import db
import pandas as pd
from sqlalchemy import func
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from app.logs.services.logging_service import log_to_db
from app.common.services.help_services import (
    _replace_quotes_sequentially,
    _clean_name,
)
from app.common.services.database_version_filter import (
    set_db_version_on_create,
    filter_by_db_version,
)
from app.generation.models.station.station_model import Station
from app.generation.models.station.station_power_model import StationPower
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.machine.machine_fuel_model import MachineFuel
from app.generation.models.machine.machine_tes_type_model import MachineTesType
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.fuels.fuel_model import Fuel
from app.refdata.models.gen_companies.gen_company_model import GenCompany
from app.refdata.models.refdata_for_stations.condition_type_model import ConditionType
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
from app.refdata.models.refdata_for_stations.machine.machine_type_model import MachineType
from app.refdata.models.refdata_for_stations.machine.tes_machine_type_model import TesMachineType
from app.refdata.models.refdata_for_stations.machine.tes_type_model import TesType
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.generation.services.station_services.help_services import get_unknown_tes_type_id


FUEL_COLUMN_PATTERNS = (
    "{year} (топливо)",
    "{year} (Топливо)",
    "{year} (fuel)",
    "{year} (Fuel)",
    "fuel_{year}",
    "fuel {year}",
    "fuel{year}",
)

FUEL_NAME_ALIASES = {
    "газ": ["газ", "природный газ"],
    "уголь": ["уголь", "каменный уголь", "бурый уголь"],
    "прочее": ["прочее"],
}


# Функция для проверки значений дат на NaN и замены на None
def safe_date(value):
    if pd.isna(value):
        return None
    try:
        # Если это число и выглядит как год
        if isinstance(value, (int, float)) and 1000 <= value <= 3000:
            return str(int(value))

        # Преобразуем как дату
        parsed = pd.to_datetime(value, errors='coerce', dayfirst=True)

        if pd.isna(parsed):
            return None

        # Если это ровно 1 января — можно оставить как год
        if parsed.month == 1 and parsed.day == 1:
            return str(parsed.year)

        return parsed.strftime('%Y-%m-%d')
    except Exception:
        return None


# Вспомогательная функция, возвращающая query, отфильтрованный по текущей версии БД
def versioned_query(model):
    return filter_by_db_version(model.query, model)


# Функция для проверки полей на NaN и замены на None
def safe_lookup(model, field, value, cleaner=_clean_name):
    """Безопасный поиск объекта по справочнику. Возвращает .id или None."""
    try:
        if pd.isna(value):
            return None
        cleaned = cleaner(value) if cleaner else value
        if cleaned in [None, '', float('nan')]:
            return None
        query = versioned_query(model).filter_by(**{field: cleaned})
        obj = query.first()
        return obj.id if obj else None
    except Exception as e:
        print(f"[ERROR] Ошибка при поиске {model.__name__}.{field}='{value}':", e)
        return None


def _extract_value_from_row(row, year, patterns):
    """Возвращает значение из строки по первому совпавшему шаблону колонки."""
    for pattern in patterns:
        column_name = pattern.format(year=year)
        if column_name in row and not pd.isna(row[column_name]):
            return row[column_name]
    return None


def get_fuel_value(row, year):
    """Получает значение топлива из ряда Excel для указанного года."""
    return _extract_value_from_row(row, year, FUEL_COLUMN_PATTERNS)


def resolve_fuel(value):
    """Возвращает объект Fuel для текущей версии БД по названию топлива."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None

    cleaned = _clean_name(value)
    if not cleaned:
        return None

    fuel = (
        versioned_query(Fuel)
        .filter(func.lower(Fuel.name) == cleaned.lower())
        .first()
    )
    if fuel:
        return fuel

    aliases = FUEL_NAME_ALIASES.get(cleaned.lower(), [])
    for alias in aliases:
        fuel = (
            versioned_query(Fuel)
            .filter(func.lower(Fuel.name) == alias.lower())
            .first()
        )
        if fuel:
            return fuel

    print(f"[WARNING] Топливо '{value}' не найдено в текущей версии БД.")
    return None


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
    station_name = _clean_name(row['station_name'])

    raw_district = row.get('regional_district')
    regional_district_name = _clean_name(raw_district) if not pd.isna(raw_district) else None

    # Найти региональный округ
    regional_district = (
        versioned_query(RegionalDistrict)
        .filter_by(name=regional_district_name)
        .first()
    )
    if not regional_district:
        energy_unit = (
            versioned_query(EnergyUnit)
            .filter_by(name=regional_district_name)
            .first()
        )
        if energy_unit and energy_unit.regional_district:
            regional_district = energy_unit.regional_district

    # Энергоузел по умолчанию (или найденный)
    energy_unit = (
        versioned_query(EnergyUnit).filter_by(id=0).first()
        or safe_lookup(EnergyUnit, 'id', 0, cleaner=None)
    )
    condition_type = (
        versioned_query(ConditionType).filter_by(name="действующий").first()
    )
    station_type_id = safe_lookup(StationType, 'name', row.get('station_type'))

    group_id = row.get("id_group")
    group_id = int(group_id) if not pd.isna(group_id) and str(group_id).isdigit() else None

    note = _clean_name(row.get('note')) if not pd.isna(row.get('note')) else None

    station = (
        versioned_query(Station)
        .filter_by(
            name=station_name,
            id_regional_district=regional_district.id if regional_district else None
        )
        .first()
    )

    if not station:
        station = Station(
            name=station_name,
            id_regional_district=regional_district.id if regional_district else None,
            id_condition_type=condition_type.id if condition_type else None,
            id_energy_unit=energy_unit.id if energy_unit else None,
            id_station_type=station_type_id,
            note=note if note else None,
        )
        set_db_version_on_create(station)
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
        if station_type_id and station.id_station_type != station_type_id:
            changes['id_station_type'] = station_type_id

        if changes:
            for k, v in changes.items():
                setattr(station, k, v)
            db.session.commit()
            log_to_db(user, "Обновление станции", f"Обновлена станция: {station.name} ({station.regional_district.name}), изменения: {changes}")
            print(f"Обновление станции, Обновлена станция: {station.name} ({station.regional_district.name}), изменения: {changes}")

    return station


# Вспомогательная функция: создание или обновление агрегата
def handle_machine(row, current_station, user):
    machine_name = _clean_name(row['machine_name'])

    machine_group = row.get('machine_group')
    if pd.isna(machine_group) or machine_group in [None, 'nan', 'NaN', '']:
        machine_group = ""
    else:
        if isinstance(machine_group, (int, float)):
            machine_group = str(int(machine_group)) if machine_group.is_integer() else str(machine_group)
        else:
            machine_group = str(machine_group).strip()

    machine_number = _clean_name(row.get('machine_number'))
    if pd.isna(machine_number) or machine_number in [None, 'nan', 'NaN', '']:
        machine_number = ""
    else:
        if isinstance(machine_number, (int, float)):
            machine_number = str(int(machine_number)) if machine_number.is_integer() else str(machine_number)
        else:
            machine_number = str(machine_number).strip()

    gen_company = (
        versioned_query(GenCompany)
        .filter_by(name=_clean_name(row['gen_company']))
        .first()
    )

    condition_type = (
        versioned_query(ConditionType).filter_by(name="действующий").first()
    )

    raw_year = row.get('date_exploitation')
    if not pd.isna(raw_year):
        try:
            date_exploitation = int(str(raw_year).strip())
        except ValueError:
            date_exploitation = None
    else:
        date_exploitation = None

    if row.get('p_2024') == 0 or (date_exploitation and date_exploitation > 2025):
        condition_type = (
            versioned_query(ConditionType).filter_by(name="планируемый").first()
        )

    station_type_id = safe_lookup(StationType, 'name', row.get('station_type'))
    if (
        current_station
        and station_type_id
        and current_station.id_station_type != station_type_id
    ):
        old_type = (
            current_station.station_type.name
            if getattr(current_station, "station_type", None)
            else '—'
        )
        current_station.id_station_type = station_type_id
        db.session.add(current_station)
        db.session.commit()
        log_to_db(
            user,
            f"Обновление типа станции {current_station.name}",
            f"Тип станции: {old_type} → {row.get('station_type')}",
        )
        print(
            f"Обновление типа станции {current_station.name}: {old_type} → {row.get('station_type')}"
        )

    machine = (
        versioned_query(Machine)
        .filter_by(
            machine_number=machine_number,
            machine_group=machine_group,
            machine_name=machine_name,
            id_station=current_station.id
        )
        .first()
    )

    if machine:
        changes = []
        update_if_changed(machine, 'machine_name', machine_name, changes)
        update_if_changed(machine, 'machine_group', machine_group, changes)
        update_if_changed(machine, 'date_exploitation', date_exploitation, changes)
        update_if_changed(machine, 'id_gen_company', gen_company.id if gen_company else None, changes)
        update_if_changed(machine, 'id_tes_machine_type', safe_lookup(TesMachineType, 'name', row.get('tes_machine_type')), changes)
        update_if_changed(machine, 'id_machine_type', safe_lookup(MachineType, 'id', 0, cleaner=None), changes)

        # Исключаем автоматические поля
        date_fields = [
            'date_commission_fact',
            'date_joining_expected', 'date_joining_fact',
            'date_detatchment_fact',
            'date_decompressing_fact', 'date_modernization_expected',
            'date_relabing_fact', 'date_update_fact'
        ]
        for field in date_fields:
            update_if_changed(machine, field, safe_date(row.get(field)), changes)

        if not pd.isna(row.get('note')):
            note_val = _clean_name(row['note'])
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
            note=_clean_name(row['note']) if not pd.isna(row.get('note')) else None,
            id_machine_type=safe_lookup(MachineType, 'id', 0, cleaner=None),
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
        set_db_version_on_create(machine)
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
    tes_type_obj = (
        versioned_query(TesType).filter_by(id=tes_type_id).first()
        if tes_type_id
        else None
    )
    tes_type_name = tes_type_obj.name if tes_type_obj else 'не указано'

    for year in range(start_year, end_year + 1):
        record = (
            versioned_query(MachineTesType)
            .filter_by(year_number=year, id_machine=machine.id)
            .first()
        )

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
            set_db_version_on_create(new_record)
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

        power = (
            versioned_query(MachinePower)
            .filter_by(year_number=year, id_machine=machine.id)
            .first()
        )

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
            set_db_version_on_create(new_power)
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

        machine_power = (
            versioned_query(MachinePower)
            .filter_by(year_number=year, id_machine=machine.id)
            .first()
        )

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
            set_db_version_on_create(machine_power)
            db.session.add(machine_power)
            log_to_db(
                user, f"Создание p_rasp электростанции {machine.machine_station.name} ({district_name})",
                f"Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: p_rasp {p_rasp}"
            )
            print(f"Создание p_rasp электростанции {machine.machine_station.name} ({district_name}), Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: p_rasp {p_rasp}")


# Отдельная функция для пересчета ограничений мощности
def update_machine_power_ogr(machine, start_year, end_year, user):
    for year in range(start_year, end_year + 1):
        power = (
            versioned_query(MachinePower)
            .filter_by(year_number=year, id_machine=machine.id)
            .first()
        )
        if power:
            old_ogr = power.p_ogr
            val = (power.p_ust or 0) - (power.p_rasp or 0)
            power.p_ogr = to_decimal(val) if not pd.isna(val) else Decimal(0)

            if old_ogr != power.p_ogr:
                log_to_db(
                    user, f"Пересчет ограничения мощности электростанции {machine.machine_station.name} ({machine.machine_station.regional_district.name}))",
                    f"Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: p_ogr {old_ogr} → {power.p_ogr}"
                )
                print(f"Пересчет ограничения мощности электростанции {machine.machine_station.name} ({machine.machine_station.regional_district.name}), Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: p_ogr {old_ogr} → {power.p_ogr}")


# Вспомогательная функция: расчет агрегированной мощности станции по годам
def update_station_power(station, start_year, end_year, user):
    for year in range(start_year, end_year + 1):
        total_values = db.session.query(
            db.func.sum(MachinePower.p_ust).label("total_p_ust"),
            db.func.sum(MachinePower.p_ogr).label("total_p_ogr"),
            db.func.sum(MachinePower.p_rasp).label("total_p_rasp")
        ).join(Machine).filter(
            Machine.id_station == station.id,
            MachinePower.year_number == year
        )
        total_values = filter_by_db_version(total_values, MachinePower)
        total_values = filter_by_db_version(total_values, Machine)
        total_values = total_values.first()

        total_p_ust = total_values.total_p_ust or 0
        total_p_ogr = total_values.total_p_ogr or 0
        total_p_rasp = total_values.total_p_rasp or 0

        record = (
            versioned_query(StationPower)
            .filter_by(id_station=station.id, year_number=year)
            .first()
        )
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
            set_db_version_on_create(record)
            db.session.add(record)
            log_to_db(user, f"Создание мощности электростанции ({station.name})",
                      f"Станция: {station.name}, год {year}: p_ust {total_p_ust}, p_ogr {total_p_ogr}, p_rasp {total_p_rasp}")
            print(f"Создание мощности электростанции ({station.name}), Станция: {station.name}, год {year}: p_ust {total_p_ust}, p_ogr {total_p_ogr}, p_rasp {total_p_rasp}")


# Вспомогательная функция: запись топлива агрегата по годам
def assign_machine_fuel(machine, row, start_year, end_year, user):
    # Получаем тип станции из связанной станции
    station_type_name = None
    if machine.machine_station and machine.machine_station.id_station_type:
        station_type_obj = (
            versioned_query(StationType)
            .filter_by(id=machine.machine_station.id_station_type)
            .first()
        )
        station_type_name = station_type_obj.name if station_type_obj else None

    for year in range(start_year, end_year + 1):
        fuel_value = get_fuel_value(row, year)
        fuel = resolve_fuel(fuel_value)

        if not fuel or station_type_name != "ТЭС":
            continue

        fuel_record = (
            versioned_query(MachineFuel)
            .filter_by(year_number=year, id_machine=machine.id)
            .first()
        )

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
            set_db_version_on_create(new_fuel)
            db.session.add(new_fuel)
            log_to_db(user, f"Создание топлива электростанции {machine.machine_station.name} ({machine.machine_station.regional_district.name})",
                      f"Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: {fuel.name}")
            print(f"Создание топлива электростанции {machine.machine_station.name} ({machine.machine_station.regional_district.name}), Агрегат: {machine.machine_number} - {machine.machine_name}, год {year}: {fuel.name}")


# Вспомогательная функция: автоматическое удаление/добавление топлива и типа ТЭС
def cleanup_machine_fuel_and_tes_type(machine, row, start_year, end_year, user):
    station = machine.machine_station
    district_name = station.regional_district.name if station and station.regional_district else "—"

    unknown_tes_type_id = get_unknown_tes_type_id()

    for year in range(start_year, end_year + 1):
        p_val = row.get(f'p_{year}')
        fuel_val = get_fuel_value(row, year)
        tes_type_val = row.get(f'tes_type_{year}')

        try:
            p_ust = float(p_val) if not pd.isna(p_val) else 0
        except ValueError:
            p_ust = 0

        # Получаем установленную мощность агрегата на этот год
        machine_power = (
            versioned_query(MachinePower)
            .filter_by(year_number=year, id_machine=machine.id)
            .first()
        )
        p_ust = machine_power.p_ust if machine_power else 0

        # Получаем текущее топливо и тип ТЭС агрегата
        machine_fuel = (
            versioned_query(MachineFuel)
            .filter_by(year_number=year, id_machine=machine.id)
            .first()
        )
        machine_tes_type = (
            versioned_query(MachineTesType)
            .filter_by(year_number=year, id_machine=machine.id)
            .first()
        )

        # ======================== Если установленная мощность = 0 ========================
        if p_ust == 0:
            # Удаляем топливо
            if machine_fuel:
                db.session.delete(machine_fuel)
                log_to_db(
                    user,
                    f"Удаление топлива электростанции {station.name} ({district_name})",
                    f"Агрегат: {machine.machine_number}, год {year}: удалено топливо (p_ust = 0)"
                )
                print(f"Удалено топливо: {station.name} ({district_name}), Агрегат {machine.machine_number}, год {year}")

            # Сбрасываем тип ТЭС на «не известно» текущей версии
            if machine_tes_type and machine_tes_type.id_tes_type != unknown_tes_type_id:
                old_tes_type_name = machine_tes_type.tes_type.name if machine_tes_type.tes_type else 'не указано'
                machine_tes_type.id_tes_type = unknown_tes_type_id
                log_to_db(
                    user,
                    f"Сброс типа ТЭС электростанции {station.name} ({district_name})",
                    f"Агрегат: {machine.machine_number}, год {year}: тип ТЭС {old_tes_type_name} → не известно"
                )
                print(f"Сброс типа ТЭС: {station.name} ({district_name}), Агрегат {machine.machine_number}, год {year}, был: {old_tes_type_name}")
            continue

        # ======================== Если установленная мощность > 0 ========================

        # Обработка топлива
        fuel = resolve_fuel(fuel_val)

        if fuel:
            if not machine_fuel:
                machine_fuel = MachineFuel(
                    year_number=year,
                    id_machine=machine.id,
                    id_fuel=fuel.id
                )
                set_db_version_on_create(machine_fuel)
                db.session.add(machine_fuel)
                log_to_db(
                    user,
                    f"Добавление топлива электростанции {station.name} ({district_name})",
                    f"Агрегат: {machine.machine_number}, год {year}: добавлено топливо {fuel.name}"
                )
                print(f"Добавлено топливо: {station.name} ({district_name}), Агрегат {machine.machine_number}, год {year}: {fuel.name}")
            elif machine_fuel.id_fuel != fuel.id:
                old_fuel_name = machine_fuel.fuel.name if machine_fuel.fuel else 'не указано'
                machine_fuel.id_fuel = fuel.id
                log_to_db(
                    user,
                    f"Обновление топлива электростанции {station.name} ({district_name})",
                    f"Агрегат: {machine.machine_number}, год {year}: топливо {old_fuel_name} → {fuel.name}"
                )
                print(f"Обновлено топливо: {station.name} ({district_name}), Агрегат {machine.machine_number}, год {year}: {old_fuel_name} → {fuel.name}")

        # Обработка типа ТЭС
        tes_type_name = _clean_name(tes_type_val)
        tes_type = (
            versioned_query(TesType)
            .filter(func.lower(TesType.name) == tes_type_name.lower())
            .first()
            if tes_type_name
            else None
        )

        if tes_type:
            if not machine_tes_type:
                machine_tes_type = MachineTesType(
                    year_number=year,
                    id_machine=machine.id,
                    id_tes_type=tes_type.id
                )
                set_db_version_on_create(machine_tes_type)
                db.session.add(machine_tes_type)
                log_to_db(
                    user,
                    f"Добавление типа ТЭС электростанции {station.name} ({district_name})",
                    f"Агрегат: {machine.machine_number}, год {year}: добавлен тип ТЭС {tes_type.name}"
                )
                print(f"Добавлен тип ТЭС: {station.name} ({district_name}), Агрегат {machine.machine_number}, год {year}: {tes_type.name}")
            elif machine_tes_type.id_tes_type != tes_type.id:
                old_tes_type_name = machine_tes_type.tes_type.name if machine_tes_type.tes_type else 'не указано'
                machine_tes_type.id_tes_type = tes_type.id
                log_to_db(
                    user,
                    f"Обновление типа ТЭС электростанции {station.name} ({district_name})",
                    f"Агрегат: {machine.machine_number}, год {year}: тип ТЭС {old_tes_type_name} → {tes_type.name}"
                )
                print(f"Обновлен тип ТЭС: {station.name} ({district_name}), Агрегат {machine.machine_number}, год {year}: {old_tes_type_name} → {tes_type.name}")


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
        if year < 2021:
            continue

        curr = powers_by_year.get(year, 0)
        next_ = powers_by_year.get(year + 1, 0)

        # 🔻 Плановый вывод
        if curr and not next_ and not machine.date_decompressing_expected:
            machine.date_decompressing_expected = year
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

        print(f"\n[PROCESS] Обрабатываем строку {index}...")

        if not (pd.isna(row['regional_district']) and pd.isna(row['station_name'])):
            current_station = handle_station(row, user)

        elif not pd.isna(row.get('machine_name')) and not pd.isna(row.get('gen_company')):
            current_machine = handle_machine(row, current_station, user)
            assign_machine_types(current_machine, row, start_year, end_year, user)
            assign_machine_power_p_ust(current_machine, row, start_year, end_year, user)
            cleanup_machine_fuel_and_tes_type(current_machine, row, start_year, end_year, user)
        
        elif not pd.isna(row.get('station_type')) and not pd.isna(row.get('gen_company')):
            assign_machine_power_p_rasp(current_machine, row, start_year, end_year, user)
            update_machine_commission_status(current_machine, start_year, end_year, user)

            has_rasp_values = any(not pd.isna(row.get(f'p_{y}')) for y in range(start_year, end_year + 1))
            if has_rasp_values:
                update_machine_power_ogr(current_machine, start_year, end_year, user)
            

    # После всех строк: расчет агрегированных мощностей по каждой станции
    station_ids = df['station_name'].dropna().unique()
    for name in station_ids:
        station = (
            versioned_query(Station)
            .filter_by(name=_clean_name(name))
            .first()
        )
        if station:
            update_station_power(station, start_year, end_year, user)

    db.session.commit()
    print(f"[SUCCESS] Данные успешно загружены пользователем {user}")
    return {"message": f"Данные успешно загружены пользователем {user}"}


# Функция для импорта топлива по СО ЕЭС для станций в базу данных
def import_fuel_tes_station_from_excel(file, user):
    xls = pd.ExcelFile(file)

    # Список обрабатываемых листов
    sheet_names = ['Приложение А_ЕЭС', 'Приложение А_ТИТЭС']

    for sheet in sheet_names:
        print(f"\n[SHEET] Обработка листа: {sheet}")
        if sheet not in xls.sheet_names:
            print(f"[WARNING] Лист '{sheet}' не найден в файле. Пропускаем.")
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

                station_name = _clean_name(row['name'])
                gen_company_name = _clean_name(row['gen_company'])

                if pd.isna(gen_company_name):
                    print("Ошибка: значение генкомпании NaN")
                    continue

                gen_company_obj = (
                    versioned_query(GenCompany)
                    .filter_by(name=gen_company_name)
                    .first()
                )
                if gen_company_obj:
                    print(f"Генкомпания найдена: {gen_company_obj.name}")
                else:
                    print(f"[WARNING] Генкомпания с именем '{gen_company_name}' не найдена.")
                    continue

                fuel_name = _clean_name(row['fuel']) if not pd.isna(row['fuel']) else None
                if pd.isna(fuel_name) or fuel_name is None:
                    print("[WARNING] Топливо не указано, пропускаем строку.")
                    continue

                station_query = (
                    Station.query.join(Machine).filter(
                        Station.name == station_name,
                        Machine.gen_company == gen_company_obj
                    )
                )
                station_query = filter_by_db_version(station_query, Station)
                station_query = filter_by_db_version(station_query, Machine)
                station = station_query.first()

                if station:
                    print(f"[OK] Станция найдена: {station_name}")
                    if station.machines:
                        updated_machines = 0
                        for machine in station.machines:
                            if machine.fuel_so != fuel_name:
                                machine.fuel_so = fuel_name
                                updated_machines += 1

                        if updated_machines > 0:
                            db.session.commit()
                            log_to_db(user, "Обновление топлива машин", f"Станция: {station_name}, обновлено агрегатов: {updated_machines}")
                            print(f"[UPDATE] Обновлено топливо для {updated_machines} агрегатов станции '{station_name}'.")
                        else:
                            print(f"[INFO] Все агрегаты станции '{station_name}' уже имеют актуальное топливо.")
                    else:
                        print(f"[WARNING] У станции '{station_name}' нет агрегатов.")
                else:
                    print(f"[ERROR] Станция '{station_name}' с генкомпанией '{gen_company_name}' не найдена.")
            else:
                print("[SKIP] Имя и генкомпания отсутствуют, пропускаем строку.")

    return {'message': f'Данные по топливу успешно загружены пользователем {user}'}



from app.extensions import db
import pandas as pd
from sqlalchemy import func
import numbers
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from app.logs.services.logging_service import log_to_db
import logging
import time
from flask import current_app, has_app_context
import re
from app.logs.services.field_names_ru import format_field_change
from app.common.services.help_services import (
    _replace_quotes_sequentially,
    _clean_name,
    _clean_multiline_text,
)
from app.common.services.database_version_filter import (
    set_db_version_on_create,
    filter_by_db_version,
    get_current_db_version_id,
)
from app.generation.models.station.station_model import Station
from app.generation.models.station.station_power_model import StationPower
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.machine.machine_fuel_model import MachineFuel
from app.generation.models.machine.machine_tes_type_model import MachineTesType
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.fuels.fuel_model import Fuel
from app.refdata.models.fuels.fuel_type_model import FuelType
from app.refdata.models.gen_companies.gen_company_model import GenCompany
from app.refdata.models.refdata_for_stations.condition_type_model import ConditionType
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
from app.refdata.models.refdata_for_stations.machine.machine_type_model import MachineType
from app.refdata.models.refdata_for_stations.machine.tes_machine_type_model import TesMachineType
from app.refdata.models.refdata_for_stations.machine.tes_type_model import TesType
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.common.services.get_services.stations.tes_type_get_services import get_unknown_tes_type_id


def _get_logger():
    """
    Используем логгер Flask (current_app.logger) в контексте приложения,
    иначе — стандартный модульный логгер.
    """
    try:
        if has_app_context():
            return current_app.logger
    except Exception:
        pass
    return logging.getLogger(__name__)


def _normalize_column_name(col) -> str:
    """
    Нормализует заголовок колонки для сопоставления (регистронезависимо, пробелы -> '_', удаление спецсимволов).
    Поддерживает русские буквы.
    """
    s = "" if col is None else str(col)
    s = s.replace("\r", " ").replace("\n", " ").strip().lower()
    s = s.replace("ё", "е")
    s = re.sub(r"\s+", " ", s)
    s = s.replace(" ", "_")
    s = re.sub(r"[^0-9a-zа-я_]+", "", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _apply_station_import_column_aliases(df: pd.DataFrame) -> pd.DataFrame:
    """
    Переименовывает колонки Excel в канонические имена, которые ожидает импорт.
    Возвращает новый DataFrame (с возможным переименованием).
    """
    # Синонимы (нормализованные заголовки) -> каноническое имя
    alias_to_canonical = {}

    def add_aliases(canonical: str, aliases: list[str]):
        for a in aliases:
            alias_to_canonical[_normalize_column_name(a)] = canonical

    # Канонические колонки, которые используются в импорте
    add_aliases("station_name", [
        "station_name",
        "станция",
        "электростанция",
        "наименование_станции",
        "название_станции",
        "имя_станции",
        "наименование",
    ])
    add_aliases("regional_district", [
        "regional_district",
        "региональный_округ",
        "региональный_район",
        "регион",
        "округ",
        "рэг",
    ])
    add_aliases("machine_name", [
        "machine_name",
        "тип_агрегата",
        "наименование_агрегата",
        "агрегат",
    ])
    add_aliases("gen_company", [
        "gen_company",
        "генкомпания",
        "ген_компания",
        "генерирующая_компания",
        "гк",
    ])
    add_aliases("station_type", [
        "station_type",
        "тип_станции",
    ])

    rename_map = {}
    for col in df.columns:
        n = _normalize_column_name(col)
        canonical = alias_to_canonical.get(n)
        if canonical and canonical != col:
            # не перетираем, если уже есть каноническая колонка
            if canonical not in df.columns:
                rename_map[col] = canonical

    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def _fuel_name_sql_normalized():
    """
    SQL-выражение для нормализованного имени топлива:
    - заменяем NBSP на обычный пробел
    - trim
    - lower
    """
    return func.lower(func.trim(func.replace(Fuel.name, "\xa0", " ")))


def _fuel_type_name_sql_normalized():
    return func.lower(func.trim(func.replace(FuelType.name, "\xa0", " ")))


def _apply_fuel_import_column_aliases(df: pd.DataFrame) -> pd.DataFrame:
    """
    Переименовывает колонки Excel в канонические имена, которые ожидает импорт топлива:
    - name (станция)
    - gen_company (генерирующая компания)
    - fuel (топливо)
    """
    alias_to_canonical: dict[str, str] = {}

    def add_aliases(canonical: str, aliases: list[str]):
        for a in aliases:
            alias_to_canonical[_normalize_column_name(a)] = canonical

    add_aliases("name", [
        "name",
        "station",
        "station_name",
        "станция",
        "электростанция",
        "наименование_станции",
        "название_станции",
        "наименование",
        "объект",
    ])
    add_aliases("gen_company", [
        "gen_company",
        "gencompany",
        "генкомпания",
        "ген_компания",
        "генерирующая_компания",
        "собственник",
        "владелец",
        "owner",
    ])
    add_aliases("fuel", [
        "fuel",
        "топливо",
        "вид_топлива",
        "тип_топлива",
        "топливо_по_со",
        "топливо_со",
        "fuel_so",
    ])

    rename_map: dict[str, str] = {}
    for col in df.columns:
        n = _normalize_column_name(col)
        canonical = alias_to_canonical.get(n)
        if canonical and canonical != col:
            if canonical not in df.columns:
                rename_map[col] = canonical

    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def _detect_header_row_index(df_raw: pd.DataFrame, normalized_header_candidates: set[str], max_rows: int = 30) -> int | None:
    """
    Пытается найти строку, которая является заголовком таблицы.
    Возвращает индекс строки или None, если уверенно определить не удалось.
    """
    if df_raw is None or df_raw.empty:
        return None

    best_idx: int | None = None
    best_score = 0
    rows_to_scan = min(max_rows, len(df_raw))

    for i in range(rows_to_scan):
        try:
            row_vals = df_raw.iloc[i].tolist()
        except Exception:
            continue

        normalized = {_normalize_column_name(v) for v in row_vals if v is not None and str(v).strip() != ""}
        score = len(normalized & normalized_header_candidates)

        if score > best_score:
            best_score = score
            best_idx = i

        # Если нашли минимум 2 ключевых колонки — этого обычно достаточно.
        if best_score >= 2:
            break

    # Если нашли только 0/1 совпадение — считаем, что заголовок не определён.
    if best_score < 2:
        return None
    return best_idx


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
    # Для значения в Excel "газ попут" используем FuelType "газ попутный"
    # (далее через общую логику resolve_fuel будет выбран Fuel вида
    # "газ естественный попутный" в текущей версии БД).
    "газ попут": ["газ попутный"],
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
        _get_logger().exception(
            "[IMPORT][safe_lookup] Ошибка при поиске %s.%s='%s'",
            getattr(model, "__name__", str(model)),
            field,
            value,
        )
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

    cleaned_norm = cleaned.strip().lower()

    # Спец-кейс для "газ попут": в разных версиях БД могут существовать
    # два очень похожих типа топлива ("газ попут" и "газ попутный").
    # Нам нужно жёстко привязаться к текущей версии БД и, по возможности,
    # выбирать FuelType "газ попутный" и одно из его топлив.
    if cleaned_norm == "газ попут":
        try:
            # Ищем подходящий FuelType в ТЕКУЩЕЙ версии БД
            candidate_types = (
                versioned_query(FuelType)
                .filter(
                    _fuel_type_name_sql_normalized().in_(
                        ["газ попутный", "газ попут"]
                    )
                )
                .all()
            )

            chosen_type = None
            # 1) Приоритет — "газ попутный"
            for ft in candidate_types:
                if ft.name.strip().lower() == "газ попутный":
                    chosen_type = ft
                    break
            # 2) Если нет — берём "газ попут"
            if not chosen_type and candidate_types:
                chosen_type = candidate_types[0]

            if chosen_type:
                fuel = (
                    versioned_query(Fuel)
                    .filter(Fuel.id_fuel_type == chosen_type.id)
                    .order_by(Fuel.id.asc())
                    .first()
                )
                if fuel:
                    _get_logger().info(
                        "[IMPORT] Топливо '%s' сопоставлено через FuelType='%s' -> Fuel(id=%s, name=%s)",
                        value,
                        chosen_type.name,
                        fuel.id,
                        fuel.name,
                    )
                    return fuel
        except Exception:
            _get_logger().exception(
                "[IMPORT] Ошибка при спец-сопоставлении топлива '%s' (газ попут)",
                value,
            )

    fuel = versioned_query(Fuel).filter(_fuel_name_sql_normalized() == cleaned_norm).first()
    if fuel:
        return fuel

    aliases = FUEL_NAME_ALIASES.get(cleaned.lower(), [])
    for alias in aliases:
        alias_norm = str(alias).strip().lower()
        fuel = versioned_query(Fuel).filter(_fuel_name_sql_normalized() == alias_norm).first()
        if fuel:
            return fuel

    # Если Fuel по имени не найден, пробуем трактовать значение как FuelType
    try:
        fuel_type = (
            versioned_query(FuelType)
            .filter(_fuel_type_name_sql_normalized() == cleaned_norm)
            .first()
        )
        if not fuel_type and aliases:
            for a in aliases:
                a_norm = str(a).strip().lower()
                fuel_type = (
                    versioned_query(FuelType)
                    .filter(_fuel_type_name_sql_normalized() == a_norm)
                    .first()
                )
                if fuel_type:
                    break

        if fuel_type:
            # Берём "первое попавшееся" топливо данного типа в текущей версии
            fuel = (
                versioned_query(Fuel)
                .filter(Fuel.id_fuel_type == fuel_type.id)
                .order_by(Fuel.id.asc())
                .first()
            )
            if fuel:
                _get_logger().info(
                    "[IMPORT] Топливо '%s' сопоставлено через FuelType='%s' -> Fuel(id=%s, name=%s)",
                    value,
                    fuel_type.name,
                    fuel.id,
                    fuel.name,
                )
                return fuel
            _get_logger().warning(
                "[IMPORT] FuelType='%s' найден, но в текущей версии нет ни одной записи Fuel с этим типом.",
                fuel_type.name,
            )
    except Exception:
        _get_logger().exception("[IMPORT] Ошибка при сопоставлении топлива '%s' через FuelType", value)

    _get_logger().warning(
        "[IMPORT] Топливо '%s' не найдено в текущей версии БД.",
        value,
    )

    # Диагностика: проверим, есть ли такое топливо в других версиях/NULL
    try:
        names_to_check = [cleaned_norm] + [str(a).strip().lower() for a in aliases]
        found = []
        for nm in names_to_check:
            rows = Fuel.query.filter(_fuel_name_sql_normalized() == nm).all()
            for r in rows:
                found.append({"name": r.name, "database_version_id": r.database_version_id, "id": r.id})

        if found:
            _get_logger().warning(
                "[IMPORT] Топливо '%s' найдено в других версиях (current_db_version_id=%s): %s",
                value,
                get_current_db_version_id(),
                found[:20],
            )
        else:
            _get_logger().warning(
                "[IMPORT] Топливо '%s' отсутствует во всех версиях (current_db_version_id=%s).",
                value,
                get_current_db_version_id(),
            )

        # Доп. подсказка: похожие названия В ТЕКУЩЕЙ ВЕРСИИ
        try:
            like_q = f"%{cleaned_norm}%"
            similar = (
                versioned_query(Fuel)
                .filter(_fuel_name_sql_normalized().like(like_q))
                .limit(20)
                .all()
            )
            if similar:
                _get_logger().warning(
                    "[IMPORT] Похожие топлива в текущей версии (like '%s'): %s",
                    cleaned_norm,
                    [{"id": r.id, "name": r.name, "database_version_id": r.database_version_id} for r in similar],
                )
        except Exception:
            _get_logger().exception("[IMPORT] Не удалось получить похожие топлива для '%s' в текущей версии", value)

        # Доп. подсказка: похожие FuelType в текущей версии
        try:
            like_q = f"%{cleaned_norm}%"
            similar_types = (
                versioned_query(FuelType)
                .filter(_fuel_type_name_sql_normalized().like(like_q))
                .limit(20)
                .all()
            )
            if similar_types:
                _get_logger().warning(
                    "[IMPORT] Похожие fuel_type в текущей версии (like '%s'): %s",
                    cleaned_norm,
                    [{"id": r.id, "name": r.name, "database_version_id": r.database_version_id} for r in similar_types],
                )
        except Exception:
            _get_logger().exception("[IMPORT] Не удалось получить похожие fuel_type для '%s' в текущей версии", value)
    except Exception:
        _get_logger().exception("[IMPORT] Не удалось выполнить диагностику по топливу '%s'", value)
    return None


def to_decimal(val, digits=15):
    """
    Приводит значение из Excel к Decimal с фиксированной точностью.
    Важно: используем аккуратную обработку float, чтобы не терять точность,
    если в ячейке было больше знаков после запятой, чем показывает формат.
    Для float: только точное целое (50.0) приводим к 50; значения вида 49.99999999999999 не округляем.
    """
    if val is None:
        return Decimal(0)
    if isinstance(val, float) and pd.isna(val):
        return Decimal(0)
    if isinstance(val, str) and val.strip() == "":
        return Decimal(0)
    try:
        if isinstance(val, Decimal):
            dec_val = val
        elif isinstance(val, float):
            # При чтении из Excel pandas обычно даёт float, у которого
            # строковое представление соответствует «человеческому» виду ячейки.
            # Поэтому конвертируем через str(val), чтобы 9.2 и 9,2
            # попадали в БД именно как 9.2, а не 9.199999999999.
            dec_val = Decimal(str(val))
        elif isinstance(val, int):
            dec_val = Decimal(val)
        elif isinstance(val, str):
            dec_val = Decimal(val.strip().replace(",", "."))
        else:
            dec_val = Decimal(str(val))
        return dec_val.quantize(Decimal(f"1.{'0'*digits}"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(0)
    
def normalize(v):
    if isinstance(v, Decimal):
        return round(v, 15)  # согласуем с точностью БД (Numeric(25, 15))
    if isinstance(v, float):
        return round(v, 15)
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

    # Текущая версия БД для версионированных справочников/станций
    current_version_id = get_current_db_version_id()

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

    # Определяем «основную» РЭС для субъекта:
    # приоритет у той, у которой есть ОЭС, иначе берём первую.
    main_res_id = None
    if regional_district:
        try:
            # Учитываем только РЭС той же версии БД, что и текущая,
            # либо записи без версии, если current_version_id is NULL.
            energy_systems = [
                res
                for res in (regional_district.regional_energy_systems or [])
                if (
                    (current_version_id is None and res.database_version_id is None)
                    or res.database_version_id == current_version_id
                )
            ]
            main_res = None
            for res in energy_systems:
                if res.union_energy_system:
                    main_res = res
                    break
            if not main_res and energy_systems:
                main_res = energy_systems[0]
            if main_res:
                main_res_id = main_res.id
        except Exception:
            main_res_id = None

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
            id_regional_energy_system=main_res_id,
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
        new_district_id = regional_district.id if regional_district else None

        if station.id_regional_district != new_district_id:
            changes['id_regional_district'] = new_district_id

        # Автоподстановка/обновление РЭС:
        # - если у станции ещё нет прямой РЭС, но есть main_res_id;
        # - либо если сменился субъект и новая «основная» РЭС отличается.
        if main_res_id and (
            station.id_regional_energy_system is None
            or station.id_regional_district != new_district_id
        ):
            if station.id_regional_energy_system != main_res_id:
                changes['id_regional_energy_system'] = main_res_id

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
    machine_name = _clean_multiline_text(row['machine_name'])

    machine_group = row.get('machine_group')
    if pd.isna(machine_group) or machine_group in [None, 'nan', 'NaN', '']:
        machine_group = ""
    else:
        if isinstance(machine_group, numbers.Integral):
            machine_group = str(int(machine_group))
        elif isinstance(machine_group, numbers.Real):
            machine_group = (
                str(int(machine_group))
                if float(machine_group).is_integer()
                else str(machine_group)
            )
        else:
            machine_group = str(machine_group).strip()

    machine_number = _clean_name(row.get('machine_number'))
    if pd.isna(machine_number) or machine_number in [None, 'nan', 'NaN', '']:
        machine_number = ""
    else:
        if isinstance(machine_number, numbers.Integral):
            machine_number = str(int(machine_number))
        elif isinstance(machine_number, numbers.Real):
            machine_number = (
                str(int(machine_number))
                if float(machine_number).is_integer()
                else str(machine_number)
            )
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

        # Если указана фактическая дата вывода из эксплуатации — ожидаемый год не заполняем
        date_decompressing_fact_val = safe_date(row.get('date_decompressing_fact'))
        if date_decompressing_fact_val and machine.date_decompressing_expected:
            update_if_changed(machine, 'date_decompressing_expected', None, changes)

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
            date_decompressing_expected=None if safe_date(row.get('date_decompressing_fact')) else safe_date(row.get('date_decompressing_expected')),
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

            # Нормализуем значения для сравнения: None и 0 считаются одинаковыми
            old_ogr_normalized = Decimal(0) if old_ogr is None or old_ogr == 0 else old_ogr
            new_ogr_normalized = Decimal(0) if power.p_ogr is None or power.p_ogr == 0 else power.p_ogr

            # Логируем только если значения действительно изменились
            if old_ogr_normalized != new_ogr_normalized:
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
            # Нормализуем значения для сравнения: None и 0 считаются одинаковыми
            record_p_ust_normalized = record.p_ust if record.p_ust is not None else Decimal(0)
            record_p_ogr_normalized = record.p_ogr if record.p_ogr is not None else Decimal(0)
            record_p_rasp_normalized = record.p_rasp if record.p_rasp is not None else Decimal(0)
            total_p_ust_normalized = total_p_ust if total_p_ust is not None else Decimal(0)
            total_p_ogr_normalized = total_p_ogr if total_p_ogr is not None else Decimal(0)
            total_p_rasp_normalized = total_p_rasp if total_p_rasp is not None else Decimal(0)
            
            if record_p_ust_normalized != total_p_ust_normalized:
                updates.append(f"p_ust {record.p_ust} → {total_p_ust}")
                record.p_ust = total_p_ust
            if record_p_ogr_normalized != total_p_ogr_normalized:
                updates.append(f"p_ogr {record.p_ogr} → {total_p_ogr}")
                record.p_ogr = total_p_ogr
            if record_p_rasp_normalized != total_p_rasp_normalized:
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

        # 🔻 Плановый вывод (не заполняем ожидаемый год, если уже есть фактическая дата)
        if curr and not next_ and not machine.date_decompressing_expected and not machine.date_decompressing_fact:
            machine.date_decompressing_expected = year
            db.session.add(machine)
            log_to_db(
                user,
                f"Автоматический вывод агрегата электростанции {station.name} ({district_name})",
                f"Агрегат {machine.machine_number} станции '{station.name}': плановый вывод из эксплуатации в {year + 1}"
            )
            print(f"Автоматический вывод агрегата: {station.name} ({district_name}), агрегат {machine.machine_number} — вывод в {year + 1}")

        # 🔺 Плановый ввод (расчетный плановый год ввода) -> date_exploitation_expected
        # Фактический ввод хранится в date_exploitation и не должен вычисляться автоматически.
        if not curr and next_ and not machine.date_exploitation and not machine.date_exploitation_expected:
            machine.date_exploitation_expected = year + 1
            db.session.add(machine)
            log_to_db(
                user,
                f"Автоматический ввод агрегата электростанции {station.name} ({district_name})",
                f"Агрегат {machine.machine_number} станции '{station.name}': расчетный плановый ввод в эксплуатацию в {year + 1}"
            )
            print(
                f"Автоматический ввод агрегата: {station.name} ({district_name}), "
                f"агрегат {machine.machine_number} — плановый ввод в {year + 1}"
            )

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
    logger = _get_logger()
    t0 = time.perf_counter()
    filename = getattr(file, "filename", None)

    logger.info("[IMPORT_STATIONS] start user=%s filename=%s", user, filename)

    xls = pd.ExcelFile(file)
    if 'список' not in xls.sheet_names:
        logger.error("[IMPORT_STATIONS] sheet 'список' not found. sheets=%s", xls.sheet_names)
        raise ValueError("В файле отсутствует лист 'список'.")

    df = xls.parse('список', header=0)
    df = df.dropna(how='all')
    original_columns = list(df.columns)
    df = _apply_station_import_column_aliases(df)
    normalized_columns = list(df.columns)

    required_columns = ["regional_district", "station_name"]
    missing_required = [c for c in required_columns if c not in df.columns]
    if missing_required:
        logger.error(
            "[IMPORT_STATIONS] invalid template filename=%s missing=%s columns_before=%s columns_after=%s",
            filename,
            missing_required,
            original_columns,
            normalized_columns,
        )
        raise ValueError(
            "Неверный шаблон файла для импорта станций: "
            f"не найдены обязательные колонки {missing_required}. "
            f"Найдены колонки: {normalized_columns}. "
            "Проверьте, что загружаете корректный шаблон (лист 'список')."
        )

    current_station = None
    current_machine = None
    start_year, end_year = 2021, 2031

    processed_rows = 0
    skipped_empty_rows = 0
    skipped_unrecognized_rows = 0
    errors = []

    logger.info(
        "[IMPORT_STATIONS] loaded filename=%s rows=%s",
        filename,
        len(df),
    )

    progress_every = 50

    for index, row in df.iterrows():
        if row.isnull().all():
            skipped_empty_rows += 1
            continue

        processed_rows += 1
        if processed_rows % progress_every == 0:
            logger.info(
                "[IMPORT_STATIONS] progress processed=%s errors=%s (last_row=%s)",
                processed_rows,
                len(errors),
                index,
            )

        try:
            # Строка станции
            if not (pd.isna(row.get('regional_district')) and pd.isna(row.get('station_name'))):
                logger.debug(
                    "[IMPORT_STATIONS] row=%s type=station station_name=%s regional_district=%s",
                    index,
                    row.get("station_name"),
                    row.get("regional_district"),
                )
                current_station = handle_station(row, user)
                continue

            # Строка агрегата
            if not pd.isna(row.get('machine_name')) and not pd.isna(row.get('gen_company')):
                if current_station is None:
                    raise ValueError("Строка агрегата встретилась до строки станции (current_station=None)")
                logger.debug(
                    "[IMPORT_STATIONS] row=%s type=machine machine_name=%s gen_company=%s",
                    index,
                    row.get("machine_name"),
                    row.get("gen_company"),
                )
                current_machine = handle_machine(row, current_station, user)
                assign_machine_types(current_machine, row, start_year, end_year, user)
                assign_machine_power_p_ust(current_machine, row, start_year, end_year, user)
                cleanup_machine_fuel_and_tes_type(current_machine, row, start_year, end_year, user)
                continue

            # Строка p_rasp/ограничений
            if not pd.isna(row.get('station_type')) and not pd.isna(row.get('gen_company')):
                if current_machine is None:
                    raise ValueError("Строка p_rasp встретилась до строки агрегата (current_machine=None)")
                logger.debug(
                    "[IMPORT_STATIONS] row=%s type=rasp station_type=%s gen_company=%s",
                    index,
                    row.get("station_type"),
                    row.get("gen_company"),
                )
                assign_machine_power_p_rasp(current_machine, row, start_year, end_year, user)
                update_machine_commission_status(current_machine, start_year, end_year, user)

                has_rasp_values = any(not pd.isna(row.get(f'p_{y}')) for y in range(start_year, end_year + 1))
                if has_rasp_values:
                    update_machine_power_ogr(current_machine, start_year, end_year, user)
                continue

            skipped_unrecognized_rows += 1
            logger.debug("[IMPORT_STATIONS] row=%s skipped (unrecognized)", index)

        except Exception:
            # Откатываем сессию, чтобы продолжать импорт дальше
            try:
                db.session.rollback()
            except Exception:
                pass

            err = {
                "row_index": int(index) if isinstance(index, (int, float)) else str(index),
                "station": getattr(current_station, "name", None),
                "machine": getattr(current_machine, "machine_number", None) if current_machine else None,
                "filename": filename,
            }
            errors.append(err)
            logger.exception("[IMPORT_STATIONS] row failed: %s", err)
            continue

    # После всех строк: расчет агрегированных мощностей по каждой станции
    station_ids = df['station_name'].dropna().unique()
    for name in station_ids:
        try:
            station = (
                versioned_query(Station)
                .filter_by(name=_clean_name(name))
                .first()
            )
            if station:
                update_station_power(station, start_year, end_year, user)
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            err = {
                "stage": "update_station_power",
                "station_name": _clean_name(name),
                "filename": filename,
            }
            errors.append(err)
            logger.exception("[IMPORT_STATIONS] update_station_power failed: %s", err)
            continue

    try:
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        logger.exception("[IMPORT_STATIONS] final commit failed user=%s filename=%s", user, filename)
        raise

    elapsed = time.perf_counter() - t0
    logger.info(
        "[IMPORT_STATIONS] done user=%s filename=%s processed=%s skipped_empty=%s skipped_unrecognized=%s errors=%s time=%.2fs",
        user,
        filename,
        processed_rows,
        skipped_empty_rows,
        skipped_unrecognized_rows,
        len(errors),
        elapsed,
    )
    if errors:
        logger.error("[IMPORT_STATIONS] errors (first 50): %s", errors[:50])

    message = f"Импорт завершён. Обработано строк: {processed_rows}. Ошибок: {len(errors)}. Подробности — в логах."
    return {
        "message": message,
        "processed_rows": processed_rows,
        "skipped_empty_rows": skipped_empty_rows,
        "skipped_unrecognized_rows": skipped_unrecognized_rows,
        "errors_count": len(errors),
    }


# Функция для импорта топлива по СО ЕЭС для станций в базу данных
def import_fuel_tes_station_from_excel(file, user):
    logger = _get_logger()
    t0 = time.perf_counter()
    filename = getattr(file, "filename", None)
    logger.info("[IMPORT_FUEL] start user=%s filename=%s", user, filename)

    xls = pd.ExcelFile(file)

    # Список обрабатываемых листов
    sheet_names = ['Приложение А_ЕЭС', 'Приложение А_ТИТЭС']

    processed_rows = 0
    skipped_empty_rows = 0
    errors = []
    total_updated_machines = 0

    # Доп. аудит: агрегируем причины пропуска/ошибок, чтобы не спамить Log тысячами записей
    audit_counts = {}
    audit_samples = {}  # reason -> [sample strings]

    def _audit_inc(reason: str, sample: str | None = None) -> None:
        audit_counts[reason] = audit_counts.get(reason, 0) + 1
        if sample:
            lst = audit_samples.setdefault(reason, [])
            # ограничиваем примеры, чтобы details не разрастался
            if len(lst) < 50:
                lst.append(sample)

    for sheet in sheet_names:
        logger.info("[IMPORT_FUEL] sheet start: %s", sheet)
        if sheet not in xls.sheet_names:
            logger.warning("[IMPORT_FUEL] sheet '%s' not found. Skipping.", sheet)
            _audit_inc("sheet_missing", f"sheet={sheet}")
            continue

        # Сначала пробуем читать с заголовком в первой строке.
        df = xls.parse(sheet, header=0)
        df = df.dropna(how="all")
        df = _apply_fuel_import_column_aliases(df)

        required_columns = {"name", "gen_company", "fuel"}
        missing = sorted([c for c in required_columns if c not in df.columns])

        # Если обязательных колонок нет — пробуем автоматически найти строку заголовков.
        if missing:
            try:
                df_raw = xls.parse(sheet, header=None)
                # нормализованные "кандидаты" заголовков (синонимы)
                normalized_candidates = {
                    # name
                    _normalize_column_name("name"),
                    _normalize_column_name("station_name"),
                    _normalize_column_name("станция"),
                    _normalize_column_name("электростанция"),
                    _normalize_column_name("наименование_станции"),
                    _normalize_column_name("наименование"),
                    # gen_company
                    _normalize_column_name("gen_company"),
                    _normalize_column_name("генкомпания"),
                    _normalize_column_name("ген_компания"),
                    _normalize_column_name("генерирующая_компания"),
                    _normalize_column_name("собственник"),
                    # fuel
                    _normalize_column_name("fuel"),
                    _normalize_column_name("топливо"),
                    _normalize_column_name("вид_топлива"),
                    _normalize_column_name("топливо_по_со"),
                }
                header_row = _detect_header_row_index(df_raw, normalized_candidates, max_rows=40)
                if header_row is not None:
                    df = xls.parse(sheet, header=header_row)
                    df = df.dropna(how="all")
                    df = _apply_fuel_import_column_aliases(df)
                else:
                    _audit_inc("header_autodetect_failed", f"sheet={sheet}; missing_initial={missing}")
            except Exception:
                logger.exception("[IMPORT_FUEL] header autodetect failed sheet=%s filename=%s", sheet, filename)
                _audit_inc("header_autodetect_exception", f"sheet={sheet}; missing_initial={missing}")

        missing = sorted([c for c in required_columns if c not in df.columns])
        if missing:
            # Важно: не падаем на каждой строке — пропускаем весь лист и пишем понятную диагностику.
            cols = [str(c) for c in list(df.columns)[:60]]
            logger.error(
                "[IMPORT_FUEL] invalid template sheet=%s filename=%s missing=%s columns=%s",
                sheet,
                filename,
                missing,
                cols,
            )
            errors.append({"stage": "missing_columns", "sheet": sheet, "missing": missing, "filename": filename})
            _audit_inc(
                "missing_columns",
                f"sheet={sheet}; missing={missing}; columns={cols}",
            )
            continue

        for index, row in df.iterrows():
            if row.isnull().all():
                skipped_empty_rows += 1
                _audit_inc("row_empty", f"sheet={sheet}; row_index={index}")
                continue

            processed_rows += 1

            try:
                station_cell = row.get("name")
                gen_company_cell = row.get("gen_company")
                fuel_cell = row.get("fuel")

                if not (pd.isna(station_cell) and pd.isna(gen_company_cell)):
                    if not pd.isna(station_cell) and pd.isna(gen_company_cell):
                        logger.warning("[IMPORT_FUEL] row=%s sheet=%s skipped: name present, gen_company missing", index, sheet)
                        _audit_inc(
                            "row_missing_gen_company",
                            f"sheet={sheet}; row_index={index}; station={_clean_name(station_cell)}",
                        )
                        continue

                    station_name = _clean_name(station_cell)
                    gen_company_name = _clean_name(gen_company_cell)

                    if pd.isna(gen_company_name):
                        logger.error("[IMPORT_FUEL] row=%s sheet=%s error: gen_company is NaN", index, sheet)
                        _audit_inc(
                            "row_gen_company_nan",
                            f"sheet={sheet}; row_index={index}; station={station_name}",
                        )
                        continue

                    gen_company_obj = (
                        versioned_query(GenCompany)
                        .filter_by(name=gen_company_name)
                        .first()
                    )
                    if not gen_company_obj:
                        logger.warning("[IMPORT_FUEL] row=%s sheet=%s gen_company '%s' not found", index, sheet, gen_company_name)
                        _audit_inc(
                            "gen_company_not_found",
                            f"sheet={sheet}; row_index={index}; station={station_name}; gen_company={gen_company_name}",
                        )
                        continue

                    fuel_name = _clean_name(fuel_cell) if not pd.isna(fuel_cell) else None
                    if pd.isna(fuel_name) or fuel_name is None:
                        logger.warning("[IMPORT_FUEL] row=%s sheet=%s skipped: fuel not provided", index, sheet)
                        _audit_inc(
                            "fuel_not_provided",
                            f"sheet={sheet}; row_index={index}; station={station_name}; gen_company={gen_company_name}",
                        )
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
                        if station.machines:
                            updated_machines = 0
                            per_machine_changes = []  # [(machine, old, new)]
                            for machine in station.machines:
                                old_val = machine.fuel_so
                                if old_val != fuel_name:
                                    machine.fuel_so = fuel_name
                                    updated_machines += 1
                                    per_machine_changes.append((machine, old_val, fuel_name))

                            if updated_machines > 0:
                                db.session.commit()
                                total_updated_machines += updated_machines
                                # 1) Сводное событие по станции
                                log_to_db(
                                    user,
                                    "Подгрузка топлива (СО): обновление топлива по станции",
                                    details=(
                                        f"station_id={station.id}; station_name={station.name}; "
                                        f"gen_company={gen_company_name}; sheet={sheet}; row_index={index}; "
                                        f"updated_machines={updated_machines}"
                                    ),
                                    entity_type="station",
                                    entity_id=station.id,
                                )

                                # 2) Полное логирование по каждому агрегату (только реально изменённые)
                                for m, old_v, new_v in per_machine_changes:
                                    try:
                                        m_number = (getattr(m, "machine_number", None) or "").strip()
                                        m_group = (getattr(m, "machine_group", None) or "").strip()
                                        m_name = (getattr(m, "machine_name", None) or "").strip()
                                        change_txt = format_field_change("fuel_so", old_v, new_v, entity_type="machine")
                                        details = (
                                            f"station_id={station.id}; station_name={station.name}; "
                                            f"machine_id={m.id}; machine_group={m_group}; machine_number={m_number}; machine_name={m_name}; "
                                            f"source=excel; sheet={sheet}; row_index={index}; "
                                            f"{change_txt}"
                                        )
                                        log_to_db(
                                            user,
                                            "Подгрузка топлива (СО): обновление агрегата",
                                            details=details,
                                            entity_type="station",
                                            entity_id=station.id,
                                        )
                                    except Exception:
                                        logger.exception(
                                            "[IMPORT_FUEL] failed to write per-machine log station_id=%s machine_id=%s",
                                            getattr(station, "id", None),
                                            getattr(m, "id", None),
                                        )

                                # Backward-compatible legacy message (если кто-то ищет по действию)
                                log_to_db(
                                    user,
                                    "Обновление топлива машин",
                                    f"Станция: {station_name}, обновлено агрегатов: {updated_machines}",
                                    entity_type="station",
                                    entity_id=station.id,
                                )
                                logger.info("[IMPORT_FUEL] updated station=%s machines=%s fuel=%s", station_name, updated_machines, fuel_name)
                            else:
                                logger.info("[IMPORT_FUEL] no changes station=%s (already up to date)", station_name)
                                _audit_inc(
                                    "no_changes",
                                    f"sheet={sheet}; row_index={index}; station_id={station.id}; station_name={station.name}; gen_company={gen_company_name}; fuel={fuel_name}",
                                )
                        else:
                            logger.warning("[IMPORT_FUEL] station '%s' has no machines", station_name)
                            _audit_inc(
                                "station_has_no_machines",
                                f"sheet={sheet}; row_index={index}; station_id={station.id}; station_name={station.name}; gen_company={gen_company_name}",
                            )
                    else:
                        logger.error("[IMPORT_FUEL] station '%s' with gen_company '%s' not found", station_name, gen_company_name)
                        _audit_inc(
                            "station_not_found",
                            f"sheet={sheet}; row_index={index}; station={station_name}; gen_company={gen_company_name}; fuel={fuel_name}",
                        )
                else:
                    logger.debug("[IMPORT_FUEL] row=%s sheet=%s skipped: name and gen_company absent", index, sheet)
                    _audit_inc("row_skipped_no_keys", f"sheet={sheet}; row_index={index}")
            except Exception:
                try:
                    db.session.rollback()
                except Exception:
                    pass
                err = {
                    "row_index": int(index) if isinstance(index, (int, float)) else str(index),
                    "sheet": sheet,
                    "filename": filename,
                }
                errors.append(err)
                logger.exception("[IMPORT_FUEL] row failed: %s", err)
                _audit_inc("row_exception", f"sheet={sheet}; row_index={index}")
                continue

    elapsed = time.perf_counter() - t0
    logger.info(
        "[IMPORT_FUEL] done user=%s filename=%s processed=%s skipped_empty=%s errors=%s time=%.2fs",
        user,
        filename,
        processed_rows,
        skipped_empty_rows,
        len(errors),
        elapsed,
    )
    if errors:
        logger.error("[IMPORT_FUEL] errors (first 50): %s", errors[:50])

    # Итоговый аудит в таблицу Log:
    # 1) Сводная запись по всему файлу
    # 2) Отдельная запись Log для каждого "sample" из audit_samples,
    #    чтобы в логах станций было видно построчно, что произошло.
    try:
        # 1) Сводная запись (как и раньше, для совместимости)
        counts_parts = [f"{k}={v}" for k, v in sorted(audit_counts.items(), key=lambda kv: (-kv[1], kv[0]))]
        summary_details_lines = [
            f"filename={filename}",
            f"processed_rows={processed_rows}",
            f"skipped_empty_rows={skipped_empty_rows}",
            f"errors_count={len(errors)}",
            f"total_updated_machines={total_updated_machines}",
            "counts: " + (", ".join(counts_parts) if counts_parts else "нет"),
        ]

        log_to_db(
            user,
            "Подгрузка топлива (СО): итог импорта",
            details="\n".join(summary_details_lines),
            entity_type="import_fuel",
            entity_id=None,
        )

        # 2) Детализированные записи по каждому sample
        for reason in sorted(audit_samples.keys()):
            examples = audit_samples.get(reason) or []
            if not examples:
                continue

            for sample in examples:
                # Пытаемся вытащить station_id из sample, если он там есть,
                # чтобы привязать запись к конкретной станции.
                entity_type = "import_fuel"
                entity_id = None

                marker = "station_id="
                idx = sample.find(marker)
                if idx != -1:
                    # Ищем конец числа (до ';' или конца строки)
                    start = idx + len(marker)
                    end = start
                    while end < len(sample) and sample[end].isdigit():
                        end += 1
                    station_id_str = sample[start:end].strip()
                    if station_id_str.isdigit():
                        entity_type = "station"
                        entity_id = int(station_id_str)

                # Формируем action и details для записи в Log
                action = f"Подгрузка топлива (СО): {reason}"
                details = f"filename={filename}; {sample}"

                log_to_db(
                    user,
                    action,
                    details=details,
                    entity_type=entity_type,
                    entity_id=entity_id,
                )
    except Exception:
        logger.exception("[IMPORT_FUEL] failed to write detailed audit log filename=%s", filename)

    return {
        'message': f'Импорт топлива завершён. Обработано строк: {processed_rows}. Ошибок: {len(errors)}. Подробности — в логах.',
        "processed_rows": processed_rows,
        "skipped_empty_rows": skipped_empty_rows,
        "errors_count": len(errors),
    }



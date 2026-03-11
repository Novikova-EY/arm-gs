# -*- coding: utf-8 -*-
"""Сервис загрузки данных БД Топливо: привязка групп оборудования к агрегатам по external_code."""

from __future__ import annotations

import logging
from collections import defaultdict
from io import BytesIO
import time
import pandas as pd
from sqlalchemy import func
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
import re

from app.extensions import db
from app.logs.services.logging_service import log_to_db
from app.common.services.help_services import _clean_name
from app.common.services.database_version_filter import (
    filter_by_explicit_db_version,
    set_db_version_on_create,
    get_current_db_version_id,
)
from app.generation.models.machine.machine_model import Machine
from app.generation.models.station.station_model import Station
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroupType
from app.common.models.database_version_model import DatabaseVersion
from app.fuel.models.external_mapping.fue_em_equipment_group_model import (
    EquipmentGroupExternalMapping,
)
from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
from app.fuel.models.fue_equipment_group_set_station_model import (
    EquipmentGroupSetStation,
)
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_model import EquipmentGroup


def _get_logger():
    try:
        from flask import current_app, has_app_context
        if has_app_context():
            return current_app.logger
    except Exception:
        pass
    return logging.getLogger(__name__)


def _normalize_column_name(col) -> str:
    s = "" if col is None else str(col)
    s = s.replace("\r", " ").replace("\n", " ").strip().lower()
    s = s.replace("ё", "е")
    s = " ".join(s.split())
    s = s.replace(" ", "_")
    s = "".join(ch for ch in s if ch.isalnum() or ch == "_")
    s = "_".join(filter(None, s.split("_")))
    return s


# Поля EquipmentGroup (v2) для заполнения из Excel (кроме id, database_version_id).
EQUIPMENT_GROUP_UPDATE_FIELDS = [
    "name", "name_ext", "niv", "comp", "main", "d", "r", "forem",
    "vedomstvo", "obl", "dep", "oes", "er", "fo", "numb", "tm",
    "n1", "n2", "p1", "p2", "ordnumb", "addr", "note",
    "codegor", "be", "gk", "gkf",
]

# Поля MachineFuelParam для заполнения из Excel (шаг 4.3)
MACHINE_FUEL_PARAM_UPDATE_FIELDS = [
    "numb1120", "numb", "stnumb", "yearin",
    "dem", "nt", "grcode", "stname",  # grcode -> EquipmentGroupSet.numb (integer)
    "opesname", "note",
]
# Альтернативные имена колонок для поиска (если основное не найдено после алиасов)
MACHINE_FUEL_PARAM_COLUMN_ALIASES: dict[str, list[str]] = {
    "stnumb": ["stnumb", "agr_stnumb", "topl_agr_stnumb", "topl_agr_number", "station_number"],
    "stname": ["stname", "agr_stname", "topl_agr_stname", "topl_agr_station_name", "station_name"],
    "grcode": ["grcode", "agr_grcode", "topl_agr_grcode"],
}
MACHINE_FUEL_PARAM_INTEGER_FIELDS = frozenset([
    "numb1120", "numb", "stnumb", "yearin",
    "dem", "nt", "grcode",
])

# Альтернативные имена колонок для EquipmentGroupSet (если canonical пустой — пробуем эти)
EQUIPMENT_GROUP_SET_FIELD_ALTERNATES: dict[str, list[str]] = {
    "note": ["Прим.", "примечание"],
    "obl": ["Субъект РФ"],
    "oes": ["ОЭС"],
}

# Поля, значения которых Excel часто отдаёт как float (1.0) — нормализуем в целочисленную строку ("1")
EQUIPMENT_GROUP_SET_INTEGER_FIELDS = frozenset([
    "comp", "niv", "main", "numb", "ordnumb", "d", "r", "forem",
    "vedomstvo", "obl", "dep", "oes", "er", "fo",
    "tm", "n1", "n2", "p1", "p2",
    "codegor", "be", "gk", "gkf",
])


def _apply_column_aliases(df: pd.DataFrame) -> pd.DataFrame:
    """Переименовывает колонки по алиасам для id_machine, equipment_group и полей EquipmentGroupSet."""
    alias_to_canonical: dict[str, str] = {}

    def add_aliases(canonical: str, aliases: list[str]) -> None:
        for a in aliases:
            alias_to_canonical[_normalize_column_name(a)] = canonical

    add_aliases("id_machine", ["id_machine", "id_machi", "machine_id", "id_агрегата", "id_агрегат"])
    add_aliases("id_station", ["id_station", "id_stat", "station_id", "id_станции"])
    add_aliases("equipment_group", [
        "equipment_group", "group", "equipment_group_name", "group_name",
        "группа_оборудования", "группа", "наименование_группы",
    ])
    # Поля EquipmentGroupSet — одноимённые и русские алиасы (canonical = имя поля в модели)
    add_aliases("name_ext", ["name_ext", "topl_name", "topl_название", "название_топливо"])
    add_aliases("niv", ["niv", "topl_niv", "нив", "признак_группы"])
    add_aliases("comp", ["comp", "topl_comp", "комп", "признак_станции"])
    add_aliases("main", ["main", "topl_main", "главный"])
    add_aliases("d", ["d", "topl_d", "действующая", "признак_д"])
    add_aliases("r", ["r", "topl_r", "расширяемая", "признак_р"])
    add_aliases("forem", ["forem", "topl_forem", "topl_form", "form", "форэм"])
    add_aliases("vedomstvo", ["vedomstvo", "topl_vedomstvo", "ведомство"])
    add_aliases("obl", ["obl", "topl_obl", "обл", "субъект", "код_субъекта", "субъект_рф"])
    add_aliases("dep", ["dep", "topl_dep", "департамент"])
    add_aliases("oes", ["oes", "topl_oes", "оэс"])
    add_aliases("er", ["er", "topl_er", "эр", "эконом_район"])
    add_aliases("fo", ["fo", "topl_fo", "фо", "фед_округ"])
    add_aliases("numb", ["topl_numb", "Код станции"])  # topl_NUMB или экспорт "Код станции"
    add_aliases("tm", ["tm", "topl_tm", "турбины"])
    add_aliases("n1", ["n1", "topl_n1", "мощность_1", "мощность_ввод"])
    add_aliases("n2", ["n2", "topl_n2", "мощность_2", "мощность_вывод"])
    add_aliases("p1", ["p1", "topl_p1", "давление_1", "давление_ввод"])
    add_aliases("p2", ["p2", "topl_p2", "давление_2", "давление_вывод"])
    add_aliases("ordnumb", ["ordnumb", "topl_ordnumb", "порядковый_номер", "порядковый_номер_станции"])
    add_aliases("addr", ["addr", "topl_addr", "адрес"])
    add_aliases("note", ["note", "topl_note", "примечание", "прим"])
    add_aliases("codegor", ["codegor", "topl_codegor", "код_города"])
    add_aliases("be", ["be", "topl_be", "тип_генерирующей", "тип_генерирующей_компании"])
    add_aliases("gk", ["gk", "topl_gk", "код_гк", "код_генерирующей_компании", "генерирующая_компания"])
    add_aliases("gkf", ["gkf", "topl_gkf", "код_филиала", "филиал_гк"])
    add_aliases("name", ["name", "название", "название_группы"])
    # MachineFuelParam (шаг 4.3)
    add_aliases("numb1120", ["numb1120", "agr_numb1120", "topl_agr_numb1120"])
    add_aliases("numb", ["topl_numb", "Код станции"])  # MachineFuelParam
    add_aliases("stnumb", [
        "stnumb", "agr_stnumb", "topl_agr_stnumb", "topl_agr_number", "station_number",
        "номер_станции", "номер_агрегата", "agr_number",
    ])
    add_aliases("yearin", ["yearin", "agr_yearin", "topl_agr_yearin"])
    add_aliases("dem", ["dem", "agr_dem", "topl_agr_dem"])
    add_aliases("nt", ["nt", "agr_nt", "topl_agr_nt"])
    add_aliases("grcode", ["grcode", "agr_grcode", "topl_agr_grcode"])
    add_aliases("stname", [
        "stname", "agr_stname", "topl_agr_stname", "topl_agr_station_name", "station_name",
        "название_станции", "наименование_станции", "имя_станции",
    ])
    add_aliases("opesname", ["opesname", "agr_opesname", "topl_agr_opesname"])
    add_aliases("note", ["note", "agr_note", "topl_agr_note", "note_agr"])

    rename_map: dict[str, str] = {}
    already_canonical: set[str] = set()
    for col in df.columns:
        normalized = _normalize_column_name(col)
        canonical = alias_to_canonical.get(normalized)
        if not canonical or canonical == col:
            if canonical:
                already_canonical.add(canonical)
            continue
        # Не переименовываем, если целевое имя уже есть — избегаем дублирования столбцов
        if canonical in df.columns or canonical in rename_map.values() or canonical in already_canonical:
            continue
        rename_map[col] = canonical
        already_canonical.add(canonical)

    if rename_map:
        df = df.rename(columns=rename_map)
    return df


# Колонки, откуда берётся название группы оборудования (по приоритету)
EQUIPMENT_GROUP_COLUMN_NAMES = ("equipment_group", "Группа оборудования", "OBOR Станции")

# Значение "Котельные" — группа без привязки к станции (EquipmentGroup напрямую)
KOTELNYE_GROUP_NAME = "Котельные"


def _is_kotelnye_group(group_text: str | None) -> bool:
    """
    Проверяет, является ли группа котельной (объект без машины).
    Совпадение: «Котельные» или название, содержащее «котельн» (напр. «котельная», «Архангельские котельные»).
    """
    if not group_text or not isinstance(group_text, str):
        return False
    cleaned = _clean_name(group_text)
    if not cleaned:
        return False
    name_lower = cleaned.strip().lower()
    return name_lower == KOTELNYE_GROUP_NAME.lower() or "котельн" in name_lower


def _find_or_create_standalone_equipment_group(
    group_name: str,
    db_version_id: int | None,
    valid_version_ids: set[int],
) -> tuple[EquipmentGroup, bool]:
    """
    Ищет EquipmentGroup без привязки к станции (без EquipmentGroupSet) по name.
    Если не найдена — создаёт и возвращает. Возвращает (eg, was_created).
    """
    name_norm = (group_name or "").strip().lower().replace("\xa0", " ").replace("\u00a0", " ")
    if not name_norm:
        name_norm = KOTELNYE_GROUP_NAME.lower()

    # Ищем EquipmentGroup без связей с EquipmentGroupSet (standalone)
    # db.session.query — без автоматической фильтрации по версии
    eg_query = db.session.query(EquipmentGroup).outerjoin(
        EquipmentGroupSet, EquipmentGroup.id == EquipmentGroupSet.equipment_group_id
    ).filter(
        EquipmentGroupSet.id.is_(None),
        func.lower(func.trim(func.replace(EquipmentGroup.name, "\xa0", " "))) == name_norm,
    )
    if db_version_id is not None:
        eg_query = eg_query.filter(EquipmentGroup.database_version_id == db_version_id)
    else:
        eg_query = eg_query.filter(EquipmentGroup.database_version_id.is_(None))
    eg = eg_query.first()

    if eg:
        return eg, False

    eg = EquipmentGroup(name=group_name.strip() or KOTELNYE_GROUP_NAME)
    if db_version_id is not None and db_version_id in valid_version_ids:
        eg.database_version_id = db_version_id
    else:
        set_db_version_on_create(eg)
    db.session.add(eg)
    db.session.flush()
    return eg, True


def _get_equipment_group_from_row(row, df_columns) -> str | None:
    """Извлекает equipment_group из строки. Пробует колонки по приоритету (equipment_group часто пуста в Excel)."""
    for col in EQUIPMENT_GROUP_COLUMN_NAMES:
        if col in df_columns:
            val = _extract_cell_value(row, col)
            if val is not None and not (isinstance(val, float) and pd.isna(val)):
                s = (val if isinstance(val, str) else str(val)).strip()
                if s:
                    return s
    return None


def _get_equipment_group_for_kotelnye(row, df_columns) -> str | None:
    """
    Для строк котельных: ищет «Котельные» в equipment_group, «Группа оборудования», «OBOR Станции».
    Регистронезависимый поиск. Fallback: поиск во всех колонках.
    """
    def _check_val(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        s = (val if isinstance(val, str) else str(val)).strip()
        if not s:
            return None
        s_lower = s.lower()
        if "котельн" not in s_lower and s_lower != KOTELNYE_GROUP_NAME.lower():
            return None
        return s

    # 1. equipment_group (регистронезависимо)
    target = "equipment_group"
    col = next((c for c in df_columns if isinstance(c, str) and c.strip().lower() == target.lower()), None)
    if col is not None:
        val = _extract_cell_value(row, col)
        result = _check_val(val)
        if result is not None:
            return result

    # 2. «Группа оборудования», «OBOR Станции»
    for fallback_col in ("Группа оборудования", "OBOR Станции"):
        if fallback_col in df_columns:
            val = _extract_cell_value(row, fallback_col)
            result = _check_val(val)
            if result is not None:
                return result

    # 3. Fallback: поиск во всех колонках (разные шаблоны Excel)
    for c in df_columns:
        val = _extract_cell_value(row, c)
        result = _check_val(val)
        if result is not None:
            return result
    return None


def _extract_cell_value(row, field: str):
    """
    Извлекает скалярное значение из ячейки. При дублировании столбцов row[field]
    возвращает Series — берём первый непустой элемент.
    """
    val = row.get(field)
    if isinstance(val, pd.Series):
        for v in val:
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                if isinstance(v, str) and not v.strip():
                    continue
                return v
        return None
    return val


def _safe_str(value) -> str | None:
    """Извлекает строку из ячейки Excel (pd.NA, NaN, None -> None)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    s = str(value).strip()
    return s if s else None


def _safe_str_int(value) -> str | None:
    """
    Для числовых значений (1.0, 2.0) возвращает целочисленную строку ("1", "2").
    Остальное — как _safe_str.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        if isinstance(value, int):
            return str(value)
        return str(value)  # нецелое float — как есть
    s = str(value).strip()
    if not s:
        return None
    try:
        f = float(s)
        if f.is_integer():
            return str(int(f))
    except ValueError:
        pass
    return s


def _safe_int(value) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    try:
        f = float(s)
        if f.is_integer():
            return int(f)
    except Exception:
        return None
    return None


def _equipment_group_name_sql_normalized():
    return func.lower(func.trim(func.replace(EquipmentGroupType.name, "\xa0", " ")))


def _normalize_for_mapping(text: str | None) -> str:
    """Нормализация для сравнения с name_topl/gruppa_oborud в EquipmentGroupExternalMapping."""
    if not text or (isinstance(text, str) and not text.strip()):
        return ""
    s = str(text).strip().lower().replace("\xa0", " ").replace("\u00a0", " ")
    # В БД Топливо часто используются дефисы/тире, точки и др. знаки,
    # а в Excel — пробелы. Для устойчивого совпадения приводим всё к
    # буквенно-цифровым токенам, разделённым одиночными пробелами.
    s = re.sub(r"[-–—]+", " ", s)  # дефисы и тире -> пробел
    s = re.sub(r"[^\w\s]+", " ", s, flags=re.UNICODE)  # прочую пунктуацию убираем
    return " ".join(s.split())


def _find_equipment_group_by_name_or_mapping(
    group_text: str, db_version_id: int | None,
    mappings_cache: list | None = None,
) -> EquipmentGroupType | None:
    """
    Поиск EquipmentGroupType по тексту из Excel.
    1) По имени EquipmentGroupType.name (с учётом database_version_id)
    2) Fallback: по EquipmentGroupExternalMapping (name_topl, gruppa_oborud) -> ref_uuid -> EquipmentGroupType
    3) Fallback без фильтра версии (если группа есть только в одной версии)
    mappings_cache: предзагруженный список маппингов (избегает повторной загрузки при импорте).
    """
    group_norm_sql = (
        str(group_text or "").strip().lower().replace("\xa0", " ").replace("\u00a0", " ")
    )
    if not group_norm_sql:
        return None

    # 1. Поиск по EquipmentGroupType.name (нормализация как в SQL)
    eq_query = EquipmentGroupType.query.filter(
        _equipment_group_name_sql_normalized() == group_norm_sql
    )
    eq_query = filter_by_explicit_db_version(eq_query, EquipmentGroupType, db_version_id)
    eq = eq_query.first()
    if eq:
        return eq

    group_norm_digits = group_norm_sql.replace(" ", "")
    if group_norm_digits.isdigit():
        eq_query = EquipmentGroupType.query.filter(EquipmentGroupType.id == int(group_norm_digits))
        eq_query = filter_by_explicit_db_version(eq_query, EquipmentGroupType, db_version_id)
        eq = eq_query.first()
        if eq:
            return eq

    # 2. Fallback: поиск через EquipmentGroupExternalMapping (name_topl, gruppa_oborud) -> ref_uuid
    group_norm_map = _normalize_for_mapping(group_text)
    if group_norm_map:
        if mappings_cache is None:
            mappings_cache = EquipmentGroupExternalMapping.query.filter(
                EquipmentGroupExternalMapping.equipment_group_ref_uuid.isnot(None),
            ).all()
        ref_uuid = None
        for m in mappings_cache:
            for field in ("name_topl", "gruppa_oborud"):
                val = getattr(m, field, None)
                if val and _normalize_for_mapping(val) == group_norm_map:
                    ref_uuid = m.equipment_group_ref_uuid
                    break
            if ref_uuid:
                break

        if ref_uuid:
            eq_query = EquipmentGroupType.query.filter(EquipmentGroupType.ref_uuid == ref_uuid)
            eq_query = filter_by_explicit_db_version(eq_query, EquipmentGroupType, db_version_id)
            eg = eq_query.first()
            if eg:
                return eg

    # 3. Fallback без фильтра версии (если группа есть только в одной версии)
    eq_query = EquipmentGroupType.query.filter(
        _equipment_group_name_sql_normalized() == group_norm_sql
    )
    eq = eq_query.first()
    if eq:
        return eq
    if group_norm_digits.isdigit():
        return EquipmentGroupType.query.filter(
            EquipmentGroupType.id == int(group_norm_digits)
        ).first()
    return None


def _build_import_report_excel(df: pd.DataFrame, row_results: dict) -> BytesIO:
    """Формирует Excel-файл с исходными данными и результатами обработки по каждой строке."""
    buf = BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Результат импорта"

    # Заголовки: № + исходные колонки + колонки результатов
    result_cols = [
        "результат_привязка_группы",
        "результат_EquipmentGroupSet",
        "результат_MachineFuelParam",
    ]
    headers = ["№"] + list(df.columns) + result_cols
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")

    # Данные
    for row_idx, (index, row) in enumerate(df.iterrows(), 2):
        ws.cell(row=row_idx, column=1, value=row_idx - 1)  # № (1-based)
        for col_idx, col_name in enumerate(df.columns, 2):
            val = row.get(col_name)
            if pd.isna(val):
                val = ""
            ws.cell(row=row_idx, column=col_idx, value=val)
        res = row_results.get(index, {})
        for res_idx, key in enumerate(["step3", "step4_2", "step4_3"], 1):
            val = res.get(key) or ""
            ws.cell(row=row_idx, column=1 + len(df.columns) + res_idx, value=val)

    wb.save(buf)
    buf.seek(0)
    return buf


def import_fuel_db_equipment_groups_from_excel(file, user: str, *, build_report: bool = True) -> dict:
    """
    Шаг 1: строки с id_station и id_machine — привязка EquipmentGroupType к Machine.
    По id_machine находим агрегат, по Machine.external_code — все агрегаты с тем же кодом,
    и назначаем Machine.id_equipment_group в зависимости от версии БД.

    Шаг 2: после прохода по найденным id_machine создаём EquipmentGroupSetStation
    и EquipmentGroupSet (с EquipmentGroup).

    Шаг 3: второй проход:
      - строки без id_machine (есть id_station): обновление EquipmentGroup (v2) по полям из Excel
      - строки с id_machine: заполнение MachineFuelParam по полям из Excel
    """
    logger = _get_logger()
    t0 = time.perf_counter()
    filename = getattr(file, "filename", None)

    print(f"[IMPORT_FUEL_DB] Шаг 0: Старт. user={user} filename={filename}")
    logger.info("[IMPORT_FUEL_DB_EQUIPMENT_GROUPS] start user=%s filename=%s", user, filename)
    print("[IMPORT_FUEL_DB] Шаг 1: Чтение Excel...")
    xls = pd.ExcelFile(file)
    sheet_name = xls.sheet_names[0]
    print(f"[IMPORT_FUEL_DB]   Лист: {sheet_name}")

    # Поиск строки заголовка: ищем строку с equipment_group, id_station или Группа оборудования
    header_row = 0
    df_preview = xls.parse(sheet_name, header=None, nrows=25)
    header_markers = ("equipment_group", "id_station", "id_machine", "группа_оборудования")
    for try_row in range(min(20, len(df_preview))):
        row_vals = [str(c).strip() for c in df_preview.iloc[try_row] if pd.notna(c)]
        row_norm = [_normalize_column_name(str(c)) for c in df_preview.iloc[try_row] if pd.notna(c)]
        combined = " ".join(row_norm) + " " + " ".join(v.lower() for v in row_vals)
        if any(m in combined for m in header_markers):
            header_row = try_row
            break
    df = xls.parse(sheet_name, header=header_row)
    if header_row > 0:
        print(f"[IMPORT_FUEL_DB]   Строка заголовка: {header_row + 1} (пропущено {header_row} строк)")
    df = df.dropna(how="all")
    print(f"[IMPORT_FUEL_DB]   Строк после dropna: {len(df)}")
    df = _apply_column_aliases(df)
    print(f"[IMPORT_FUEL_DB]   Колонки после алиасов: {list(df.columns)}")

    if not any(c in df.columns for c in EQUIPMENT_GROUP_COLUMN_NAMES):
        raise ValueError(
            "Неверный шаблон файла: отсутствует колонка equipment_group, «Группа оборудования» или «OBOR Станции»."
        )
    has_machine = "id_machine" in df.columns
    has_station = "id_station" in df.columns
    if not has_station:
        raise ValueError(
            "Неверный шаблон файла: необходима колонка id_station. "
            "Строки с id_machine обрабатываются только при наличии id_station."
        )
    if not has_machine:
        print("[IMPORT_FUEL_DB]   Колонка id_machine отсутствует — шаг 1 пропускается")
    print(f"[IMPORT_FUEL_DB] Шаг 2: Проверка колонок OK (id_machine={has_machine}, id_station={has_station})")

    processed_rows = 0
    skipped_empty = 0
    skipped_invalid = 0
    updated_machines = 0
    errors = []
    audit_counts: dict[str, int] = {}
    audit_samples: dict[str, list[str]] = {}
    # Результат по каждой строке для отчёта: index -> {step3, step4_2, step4_3}
    row_results: dict[int | float, dict[str, str]] = defaultdict(
        lambda: {"step3": None, "step4_2": None, "step4_3": None}
    )

    def _audit_inc(reason: str, sample: str | None = None) -> None:
        audit_counts[reason] = audit_counts.get(reason, 0) + 1
        if sample:
            lst = audit_samples.setdefault(reason, [])
            if len(lst) < 30:
                lst.append(sample)

    def _set_row_result(index, step: str, value: str) -> None:
        row_results[index][step] = value

    # Кэш (group_text, db_version_id) -> EquipmentGroupType | None — избегаем тысяч повторных запросов к БД
    _eg_cache: dict[tuple[str, int | None], EquipmentGroupType | None] = {}
    _mappings_cache = EquipmentGroupExternalMapping.query.filter(
        EquipmentGroupExternalMapping.equipment_group_ref_uuid.isnot(None),
    ).all()

    def _find_eg_cached(gt: str, vid: int | None) -> EquipmentGroupType | None:
        key = (_normalize_for_mapping(gt) or "", vid)
        if key not in _eg_cache:
            _eg_cache[key] = _find_equipment_group_by_name_or_mapping(gt, vid, _mappings_cache)
        return _eg_cache[key]

    current_version = get_current_db_version_id()
    all_db_versions = DatabaseVersion.query.filter(
        DatabaseVersion.id.isnot(None),
        DatabaseVersion.id > 0,
    ).all()
    valid_version_ids = {v.id for v in all_db_versions}

    def _resolve_version_id(entity) -> int | None:
        version_id = getattr(entity, "database_version_id", None)
        if version_id is None:
            version_id = current_version
        if version_id is not None and version_id not in valid_version_ids:
            if current_version in valid_version_ids:
                return current_version
            return None
        return version_id

    STEP3_COMMIT_EVERY = 25
    last_step3_commit_at = 0
    processed_pairs: set[tuple[int, int, int | None]] = set()

    # [ВЫКЛ] Проверка дублей по numb — отключена
    # seen_numb: set[str] = set()
    # has_numb_col = "numb" in df.columns

    print("[IMPORT_FUEL_DB] Шаг 3: Обработка строк (id_machine + id_station) — привязка групп к агрегатам...")
    for index, row in df.iterrows():
        if row.isnull().all():
            skipped_empty += 1
            _audit_inc("row_empty", f"row_index={index}")
            _set_row_result(index, "step3", "Пропуск: пустая строка")
            if skipped_empty <= 5:
                print(f"[IMPORT_FUEL_DB]   Строка {index}: пропуск (пустая)")
            continue

        processed_rows += 1
        try:
            # [ВЫКЛ] Пропуск дублей по numb
            # if has_numb_col:
            #     numb_val = _extract_cell_value(row, "numb")
            #     numb_key = _safe_str_int(numb_val) if numb_val is not None else None
            #     if numb_key is not None:
            #         if numb_key in seen_numb:
            #             _audit_inc("numb_duplicate", f"row_index={index}; numb={numb_key}")
            #             _set_row_result(index, "step3", f"Пропуск: дубль по numb={numb_key}")
            #             continue
            #         seen_numb.add(numb_key)

            machine_id = _safe_int(row.get("id_machine")) if has_machine else None
            station_id_row = _safe_int(row.get("id_station")) if has_station else None
            if station_id_row is None:
                _audit_inc("row_skip_step3", f"row_index={index}; нет id_station")
                _set_row_result(index, "step3", "Пропуск: нет id_station")
                continue
            if machine_id is None:
                _set_row_result(index, "step3", "Пропуск: нет id_machine")
                continue

            group_text = _get_equipment_group_from_row(row, df.columns)
            if group_text:
                group_text = _clean_name(group_text)

            if not group_text:
                skipped_invalid += 1
                _audit_inc("row_missing_required", f"row_index={index}")
                _set_row_result(index, "step3", "Пропуск: нет equipment_group")
                if processed_rows <= 30:
                    print(f"[IMPORT_FUEL_DB]     -> пропуск: нет equipment_group")
                continue

            # По id_machine находим агрегат
            machine = Machine.query.get(machine_id)
            if not machine or not machine.external_code:
                skipped_invalid += 1
                _audit_inc("machine_not_found", f"row_index={index}; id_machine={machine_id}")
                _set_row_result(index, "step3", f"Пропуск: агрегат id={machine_id} не найден или нет external_code")
                continue

            machines_same_code = Machine.query.filter(
                Machine.external_code == machine.external_code
            ).all()
            if not machines_same_code:
                _set_row_result(index, "step3", "Пропуск: нет агрегатов с таким external_code")
                continue

            step3_updated_count = 0
            step3_not_found = False

            for m in machines_same_code:
                db_version_id = _resolve_version_id(m)
                equipment_group = _find_eg_cached(group_text, db_version_id)
                if not equipment_group:
                    _audit_inc(
                        "equipment_group_not_found",
                        f"row_index={index}; group={group_text}; version={db_version_id}",
                    )
                    step3_not_found = True
                    continue

                if m.id_equipment_group != equipment_group.id:
                    m.id_equipment_group = equipment_group.id
                    db.session.add(m)
                    updated_machines += 1
                    step3_updated_count += 1

                if m.id_station:
                    processed_pairs.add((m.id_station, equipment_group.id, db_version_id))

                if updated_machines - last_step3_commit_at >= STEP3_COMMIT_EVERY:
                    try:
                        db.session.commit()
                        db.session.expire_all()
                        last_step3_commit_at = updated_machines
                    except Exception as commit_err:
                        try:
                            db.session.rollback()
                        except Exception:
                            pass
                        logger.warning("[IMPORT_FUEL_DB] промежуточный commit: %s", commit_err)

            if step3_updated_count > 0:
                _set_row_result(
                    index,
                    "step3",
                    f"ОБНОВЛЕНО: привязано {step3_updated_count} агрегат(ов) к группе '{group_text}'",
                )
            elif step3_not_found:
                _set_row_result(
                    index,
                    "step3",
                    f"Пропуск: группа оборудования '{group_text}' не найдена в справочнике",
                )
            else:
                _set_row_result(index, "step3", "Без изменений (привязки уже актуальны)")

        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
            err = {"row_index": int(index) if isinstance(index, (int, float)) else str(index), "filename": filename}
            errors.append(err)
            err_msg = str(e)[:200] if e else "Неизвестная ошибка"
            _set_row_result(index, "step3", f"ОШИБКА: {err_msg}")
            logger.exception("[IMPORT_FUEL_DB_EQUIPMENT_GROUPS] row failed: %s", err)
            _audit_inc("row_exception", str(err))
            continue

    print(
        f"[IMPORT_FUEL_DB] Шаг 4: Commit в БД... (обработано={processed_rows}, обновлено={updated_machines}, ошибок={len(errors)})"
    )
    try:
        db.session.commit()
        print("[IMPORT_FUEL_DB]   Commit OK")
    except Exception as e:
        print(f"[IMPORT_FUEL_DB]   Commit ОШИБКА: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass
        logger.exception("[IMPORT_FUEL_DB_EQUIPMENT_GROUPS] commit failed user=%s filename=%s", user, filename)
        raise

    created_links = 0
    created_sets = 0
    created_groups = 0
    print("[IMPORT_FUEL_DB] Шаг 4.1: Формирование EquipmentGroupSetStation и EquipmentGroupSet...")
    try:
        # Собираем (station_id, equipment_group_type_id, version_id) с учётом сводных станций
        # (same external_code): для каждой версии станции создаём связь если её нет
        expanded_pairs: set[tuple[int, int, int | None]] = set()
        type_ref_uuid_cache: dict[int, str | None] = {}

        for station_id, equipment_group_type_id, version_id in processed_pairs:
            expanded_pairs.add((station_id, equipment_group_type_id, version_id))
            station = Station.query.get(station_id)
            if not station or not station.external_code:
                continue
            # Получаем ref_uuid типа для поиска эквивалента в других версиях
            if equipment_group_type_id not in type_ref_uuid_cache:
                eg_type = EquipmentGroupType.query.get(equipment_group_type_id)
                type_ref_uuid_cache[equipment_group_type_id] = getattr(eg_type, "ref_uuid", None) if eg_type else None
            ref_uuid = type_ref_uuid_cache[equipment_group_type_id]
            if not ref_uuid:
                continue
            # Сводные станции (тот же external_code)
            siblings = Station.query.filter(Station.external_code == station.external_code).all()
            for sib in siblings:
                if sib.id == station_id:
                    continue
                sib_version = getattr(sib, "database_version_id", None)
                # Ищем EquipmentGroupType с тем же ref_uuid для версии сводной станции
                sib_type_query = EquipmentGroupType.query.filter(EquipmentGroupType.ref_uuid == ref_uuid)
                sib_type_query = filter_by_explicit_db_version(sib_type_query, EquipmentGroupType, sib_version)
                sib_type = sib_type_query.first()
                if sib_type:
                    expanded_pairs.add((sib.id, sib_type.id, sib_version))

        for station_id, equipment_group_type_id, version_id in sorted(expanded_pairs):
            link_query = EquipmentGroupSetStation.query.filter(
                EquipmentGroupSetStation.station_id == station_id,
                EquipmentGroupSetStation.equipment_group_type_id == equipment_group_type_id,
            )
            if version_id is None:
                link_query = link_query.filter(EquipmentGroupSetStation.database_version_id.is_(None))
            else:
                link_query = link_query.filter(EquipmentGroupSetStation.database_version_id == version_id)
            link = link_query.first()

            if not link:
                link = EquipmentGroupSetStation(
                    station_id=station_id,
                    equipment_group_type_id=equipment_group_type_id,
                )
                if version_id is not None:
                    link.database_version_id = version_id
                elif current_version is not None:
                    set_db_version_on_create(link)
                db.session.add(link)
                db.session.flush()
                created_links += 1

            set_v2 = EquipmentGroupSet.query.filter_by(
                equipment_group_set_station_id=link.id
            ).first()
            if not set_v2:
                station = Station.query.get(station_id)
                group_type = EquipmentGroupType.query.get(equipment_group_type_id)
                group_name = None
                if station and station.name and group_type and group_type.name:
                    group_name = f"{station.name} ({group_type.name})"
                equipment_group = EquipmentGroup(name=group_name)
                if version_id is not None:
                    equipment_group.database_version_id = version_id
                elif current_version is not None:
                    set_db_version_on_create(equipment_group)
                db.session.add(equipment_group)
                db.session.flush()
                created_groups += 1

                set_v2 = EquipmentGroupSet(
                    equipment_group_id=equipment_group.id,
                    equipment_group_set_station_id=link.id,
                )
                db.session.add(set_v2)
                db.session.flush()
                created_sets += 1
                equipment_group._populate_regional_ids()

        if created_links or created_sets or created_groups:
            db.session.commit()
            print(
                f"[IMPORT_FUEL_DB]   Создано: links={created_links}, groups={created_groups}, sets={created_sets}"
            )
        else:
            print("[IMPORT_FUEL_DB]   Изменений нет (все связи уже существуют)")
    except Exception as e:
        print(f"[IMPORT_FUEL_DB]   ОШИБКА при формировании EquipmentGroupSet: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass
        logger.exception("[IMPORT_FUEL_DB_EQUIPMENT_GROUPS] EquipmentGroupSet step failed: %s", e)
        raise

    updated_groups_fields = 0
    print("[IMPORT_FUEL_DB] Шаг 4.2: Обновление EquipmentGroup (v2) из строк без id_machine...")
    try:
        for index, row in df.iterrows():
            if row.isnull().all():
                continue
            # [ВЫКЛ] Пропуск дублей по numb
            # if has_numb_col:
            #     numb_val = _extract_cell_value(row, "numb")
            #     numb_key = _safe_str_int(numb_val) if numb_val is not None else None
            #     if numb_key is not None and numb_key in seen_numb:
            #         _audit_inc("numb_duplicate", f"row_index={index}; numb={numb_key}")
            #         _set_row_result(index, "step4_2", f"Пропуск: дубль по numb={numb_key}")
            #         continue
            #     if numb_key is not None:
            #         seen_numb.add(numb_key)
            machine_id = _safe_int(row.get("id_machine")) if has_machine else None
            station_id_row = _safe_int(row.get("id_station")) if has_station else None
            if station_id_row is None:
                continue
            if machine_id is not None:
                _set_row_result(index, "step4_2", "Пропуск: строка с id_machine")
                continue

            group_text = _get_equipment_group_from_row(row, df.columns)
            if group_text:
                group_text = _clean_name(group_text)
            if not group_text:
                _set_row_result(index, "step4_2", "Пропуск: нет equipment_group")
                continue
            if _is_kotelnye_group(group_text):
                _set_row_result(index, "step4_2", "Пропуск: «Котельные» обрабатываются в шаге 4.2.5")
                continue

            station = Station.query.get(station_id_row)
            if not station or not station.external_code:
                _set_row_result(index, "step4_2", "Пропуск: станция не найдена или нет external_code")
                continue

            stations_same_code = Station.query.filter(
                Station.external_code == station.external_code
            ).all()
            if not stations_same_code:
                _set_row_result(index, "step4_2", "Пропуск: нет станций с таким external_code")
                continue

            base_row_values: dict[str, str | None] = {}
            for field in EQUIPMENT_GROUP_UPDATE_FIELDS:
                raw = None
                if field in df.columns:
                    raw = _extract_cell_value(row, field)
                if raw is None and field in EQUIPMENT_GROUP_SET_FIELD_ALTERNATES:
                    for alt in EQUIPMENT_GROUP_SET_FIELD_ALTERNATES[field]:
                        if alt in df.columns:
                            raw = _extract_cell_value(row, alt)
                            if raw is not None:
                                break
                if raw is None:
                    continue
                if field in EQUIPMENT_GROUP_SET_INTEGER_FIELDS:
                    val = _safe_str_int(raw)
                else:
                    val = _safe_str(raw)
                if val is not None:
                    if field == "note" and len(val) > 1000:
                        val = val[:1000]
                    base_row_values[field] = val

            row_updated = 0
            row_missing_links = 0
            row_missing_group_type = 0
            for st in stations_same_code:
                db_version_id = _resolve_version_id(st)
                group_type = _find_eg_cached(group_text, db_version_id)
                if not group_type:
                    row_missing_group_type += 1
                    continue

                link_query = EquipmentGroupSetStation.query.filter(
                    EquipmentGroupSetStation.station_id == st.id,
                    EquipmentGroupSetStation.equipment_group_type_id == group_type.id,
                )
                if db_version_id is None:
                    link_query = link_query.filter(EquipmentGroupSetStation.database_version_id.is_(None))
                else:
                    link_query = link_query.filter(EquipmentGroupSetStation.database_version_id == db_version_id)
                link = link_query.first()
                if not link:
                    row_missing_links += 1
                    continue

                sets = EquipmentGroupSet.query.filter_by(
                    equipment_group_set_station_id=link.id
                ).all()
                if not sets:
                    row_missing_links += 1
                    continue

                row_values = dict(base_row_values)
                if st.name and group_type and group_type.name:
                    row_values["name"] = f"{st.name} ({group_type.name})"

                if not row_values:
                    continue

                for set_v2 in sets:
                    equipment_group = set_v2.equipment_group
                    if not equipment_group:
                        continue
                    changed = False
                    for field, val in row_values.items():
                        if hasattr(equipment_group, field) and getattr(equipment_group, field) != val:
                            setattr(equipment_group, field, val)
                            changed = True
                    if changed:
                        equipment_group.regional_district_id = None
                        equipment_group.regional_energy_system_id = None
                    # Заполняем regional_district_id и regional_energy_system_id из Station
                    # через EquipmentGroupSet -> EquipmentGroupSetStation
                    old_rd, old_res = (
                        equipment_group.regional_district_id,
                        equipment_group.regional_energy_system_id,
                    )
                    equipment_group._populate_regional_ids()
                    regional_changed = (
                        equipment_group.regional_district_id,
                        equipment_group.regional_energy_system_id,
                    ) != (old_rd, old_res)
                    if changed or regional_changed:
                        updated_groups_fields += 1
                        row_updated += 1

            if row_updated > 0:
                _set_row_result(index, "step4_2", f"ОБНОВЛЕНО: EquipmentGroup для {row_updated} записей")
            elif row_missing_group_type and not row_missing_links:
                _set_row_result(index, "step4_2", f"Пропуск: группа '{group_text}' не найдена в справочнике")
            elif row_missing_links and row_updated == 0:
                _set_row_result(index, "step4_2", "Пропуск: нет EquipmentGroupSetStation/Set")
            else:
                _set_row_result(index, "step4_2", "Без изменений (поля уже актуальны)")

        if updated_groups_fields:
            db.session.commit()
            print(f"[IMPORT_FUEL_DB]   Обновлено записей EquipmentGroup: {updated_groups_fields}")
        else:
            print("[IMPORT_FUEL_DB]   Нет изменений в EquipmentGroup")
    except Exception as e:
        print(f"[IMPORT_FUEL_DB]   ОШИБКА при заполнении полей EquipmentGroup: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass
        logger.exception("[IMPORT_FUEL_DB_EQUIPMENT_GROUPS] Step 4.2 failed: %s", e)
        raise

    updated_kotelnye = 0
    created_kotelnye = 0
    # Котельные сохраняются во всех версиях БД (все записи DatabaseVersion без фильтра id>0)
    kotelnye_all_versions = DatabaseVersion.query.filter(
        DatabaseVersion.id.isnot(None),
    ).order_by(DatabaseVersion.id).all()
    kotelnye_version_ids: list[int] = [v.id for v in kotelnye_all_versions if v.id]
    if not kotelnye_version_ids and current_version:
        kotelnye_version_ids = [current_version]
    valid_version_ids_kotelnye = valid_version_ids | set(kotelnye_version_ids)
    print("[IMPORT_FUEL_DB] Шаг 4.2.5: Обработка «Котельные» — EquipmentGroup без привязки к станции...")
    try:
        for index, row in df.iterrows():
            if row.isnull().all():
                continue

            # Для котельных: ищем «Котельные» в equipment_group (регистронезависимо) или во всех колонках
            group_text = _get_equipment_group_for_kotelnye(row, df.columns)
            if group_text:
                group_text = _clean_name(group_text)
            # Проверка: в equipment_group / Группа оборудования / OBOR Станции указано «Котельные» (или содержит «котельные»)
            if not group_text or not _is_kotelnye_group(group_text):
                continue

            base_row_values: dict[str, str | None] = {}
            for field in EQUIPMENT_GROUP_UPDATE_FIELDS:
                raw = None
                if field in df.columns:
                    raw = _extract_cell_value(row, field)
                if raw is None and field in EQUIPMENT_GROUP_SET_FIELD_ALTERNATES:
                    for alt in EQUIPMENT_GROUP_SET_FIELD_ALTERNATES[field]:
                        if alt in df.columns:
                            raw = _extract_cell_value(row, alt)
                            if raw is not None:
                                break
                if raw is None:
                    continue
                if field in EQUIPMENT_GROUP_SET_INTEGER_FIELDS:
                    val = _safe_str_int(raw)
                else:
                    val = _safe_str(raw)
                if val is not None:
                    if field == "note" and len(val) > 1000:
                        val = val[:1000]
                    base_row_values[field] = val

            if "name" not in base_row_values:
                base_row_values["name"] = KOTELNYE_GROUP_NAME

            row_created = 0
            row_updated = 0
            for db_version_id in kotelnye_version_ids:
                eg, was_created = _find_or_create_standalone_equipment_group(
                    group_text, db_version_id, valid_version_ids_kotelnye
                )
                if was_created:
                    created_kotelnye += 1
                    row_created += 1

                changed = False
                for field, val in base_row_values.items():
                    if hasattr(eg, field) and getattr(eg, field) != val:
                        setattr(eg, field, val)
                        changed = True
                if changed:
                    eg.regional_district_id = None
                    eg.regional_energy_system_id = None
                # Заполняем regional_district_id и regional_energy_system_id из Station
                # через EquipmentGroupSet -> EquipmentGroupSetStation
                old_rd, old_res = eg.regional_district_id, eg.regional_energy_system_id
                eg._populate_regional_ids()
                regional_changed = (
                    eg.regional_district_id,
                    eg.regional_energy_system_id,
                ) != (old_rd, old_res)
                if changed or regional_changed:
                    db.session.add(eg)
                    updated_kotelnye += 1
                    row_updated += 1
                # Flush после каждой версии — чтобы INSERT выполнился до поиска в следующей
                db.session.flush()

            result_msg = (
                f"ОБНОВЛЕНО: EquipmentGroup «Котельные» (standalone) во {len(kotelnye_version_ids)} версиях"
                if row_updated
                else (
                    f"Создано: «Котельные» в {row_created} версиях"
                    if row_created
                    else "Без изменений: «Котельные»"
                )
            )
            _set_row_result(index, "step4_2", result_msg)

        if updated_kotelnye or created_kotelnye:
            db.session.commit()
            print(
                f"[IMPORT_FUEL_DB]   Обработано «Котельные»: обновлено={updated_kotelnye}, создано={created_kotelnye}"
            )
        else:
            print("[IMPORT_FUEL_DB]   Строк «Котельные» нет или без изменений")
    except Exception as e:
        print(f"[IMPORT_FUEL_DB]   ОШИБКА при обработке «Котельные»: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass
        logger.exception("[IMPORT_FUEL_DB_EQUIPMENT_GROUPS] Step 4.2.5 (Котельные) failed: %s", e)
        raise

    updated_fuel_params = 0
    print("[IMPORT_FUEL_DB] Шаг 4.3: Заполнение MachineFuelParam (строки с id_machine и id_station)...")
    try:
        for index, row in df.iterrows():
            if row.isnull().all():
                continue
            # [ВЫКЛ] Пропуск дублей по numb
            # if has_numb_col:
            #     numb_val = _extract_cell_value(row, "numb")
            #     numb_key = _safe_str_int(numb_val) if numb_val is not None else None
            #     if numb_key is not None and numb_key in seen_numb:
            #         _audit_inc("numb_duplicate", f"row_index={index}; numb={numb_key}")
            #         _set_row_result(index, "step4_3", f"Пропуск: дубль по numb={numb_key}")
            #         continue
            #     if numb_key is not None:
            #         seen_numb.add(numb_key)
            machine_id = _safe_int(row.get("id_machine")) if has_machine else None
            station_id_row = _safe_int(row.get("id_station")) if has_station else None
            if machine_id is None or station_id_row is None:
                continue

            machine = Machine.query.get(machine_id)
            if not machine or not machine.external_code:
                _set_row_result(index, "step4_3", "Пропуск: агрегат не найден или нет external_code")
                continue

            machines_same_code = Machine.query.filter(
                Machine.external_code == machine.external_code
            ).all()
            if not machines_same_code:
                _set_row_result(index, "step4_3", "Пропуск: нет агрегатов с таким external_code")
                continue

            row_values: dict[str, int | str | None] = {}
            for field in MACHINE_FUEL_PARAM_UPDATE_FIELDS:
                col_names_to_try = [field]
                if field in MACHINE_FUEL_PARAM_COLUMN_ALIASES:
                    col_names_to_try = MACHINE_FUEL_PARAM_COLUMN_ALIASES[field]
                raw = None
                for col_name in col_names_to_try:
                    if col_name in df.columns:
                        raw = _extract_cell_value(row, col_name)
                        break
                if raw is None and field in df.columns:
                    raw = _extract_cell_value(row, field)
                if field in MACHINE_FUEL_PARAM_INTEGER_FIELDS:
                    val = _safe_int(raw)
                else:
                    val = _safe_str(raw)
                    if val is not None and len(val) > 80:
                        val = val[:80]
                if val is not None:
                    row_values[field] = val

            raw_grcode = None
            for col in ("grcode", "agr_grcode", "topl_agr_grcode"):
                if col in df.columns:
                    raw_grcode = _extract_cell_value(row, col)
                    break
            if raw_grcode is not None and not (isinstance(raw_grcode, float) and pd.isna(raw_grcode)):
                val = _safe_int(raw_grcode)
                if val is not None:
                    row_values["grcode"] = val

            if not row_values:
                _set_row_result(index, "step4_3", "Пропуск: нет данных для заполнения MachineFuelParam")
                continue

            row_fuel_param_count = 0
            for m in machines_same_code:
                mtp = MachineFuelParam.query.filter_by(machine_id=m.id).first()
                if mtp is None:
                    mtp = MachineFuelParam(machine_id=m.id)
                    db_version_id = _resolve_version_id(m)
                    if db_version_id is not None and db_version_id in valid_version_ids:
                        mtp.database_version_id = db_version_id
                    db.session.add(mtp)
                    db.session.flush()

                changed = False
                for field, val in row_values.items():
                    if hasattr(mtp, field) and getattr(mtp, field) != val:
                        setattr(mtp, field, val)
                        changed = True
                if changed:
                    db.session.add(mtp)
                    updated_fuel_params += 1
                    row_fuel_param_count += 1

            if row_fuel_param_count > 0:
                _set_row_result(
                    index,
                    "step4_3",
                    f"ОБНОВЛЕНО: MachineFuelParam для {row_fuel_param_count} агрегат(ов)",
                )
            else:
                _set_row_result(index, "step4_3", "Без изменений (данные уже актуальны)")

        if updated_fuel_params:
            db.session.commit()
            print(f"[IMPORT_FUEL_DB]   Обновлено/создано MachineFuelParam: {updated_fuel_params}")
        else:
            print("[IMPORT_FUEL_DB]   Нет изменений в MachineFuelParam")
    except Exception as e:
        print(f"[IMPORT_FUEL_DB]   ОШИБКА при заполнении MachineFuelParam: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass
        logger.exception("[IMPORT_FUEL_DB_EQUIPMENT_GROUPS] Step 4.3 failed: %s", e)
        raise

    elapsed = time.perf_counter() - t0
    print(
        f"[IMPORT_FUEL_DB] Шаг 5: ИТОГ. processed_rows={processed_rows} skipped_empty={skipped_empty} "
        f"skipped_invalid={skipped_invalid} updated_machines={updated_machines} "
        f"created_links={created_links} created_groups={created_groups} created_sets={created_sets} "
        f"updated_groups_fields={updated_groups_fields} updated_kotelnye={updated_kotelnye} "
        f"created_kotelnye={created_kotelnye} updated_fuel_params={updated_fuel_params} "
        f"errors={len(errors)} time={elapsed:.2f}s"
    )
    print(f"[IMPORT_FUEL_DB] audit_counts: {audit_counts}")
    logger.info(
        "[IMPORT_FUEL_DB_EQUIPMENT_GROUPS] done user=%s filename=%s processed=%s updated=%s errors=%s time=%.2fs",
        user,
        filename,
        processed_rows,
        updated_machines,
        len(errors),
        elapsed,
    )

    try:
        log_to_db(
            user,
            "Загрузка данных БД Топливо: итог импорта",
            details=(
                f"filename={filename}; processed_rows={processed_rows}; "
                f"skipped_empty={skipped_empty}; skipped_invalid={skipped_invalid}; "
                f"updated_machines={updated_machines}; "
                f"created_links={created_links}; created_groups={created_groups}; created_sets={created_sets}; "
                f"updated_groups_fields={updated_groups_fields}; "
                f"updated_kotelnye={updated_kotelnye}; created_kotelnye={created_kotelnye}; "
                f"updated_fuel_params={updated_fuel_params}; "
                f"errors_count={len(errors)}; audit_counts={audit_counts}"
            ),
            entity_type="import_fuel_db_equipment_groups",
            entity_id=None,
        )
    except Exception:
        logger.exception("[IMPORT_FUEL_DB_EQUIPMENT_GROUPS] failed to write log filename=%s", filename)

    report_bytes = _build_import_report_excel(df, dict(row_results)) if build_report else None

    numb_duplicates = audit_counts.get("numb_duplicate", 0)
    message = (
        "Загрузка данных БД Топливо завершена. "
        f"Обработано строк: {processed_rows}. "
        + (f"Пропущено дублей по numb: {numb_duplicates}. " if numb_duplicates else "")
        + f"Обновлено агрегатов: {updated_machines}. "
        f"Создано EquipmentGroupSetStation: {created_links}, EquipmentGroup: {created_groups}, "
        f"EquipmentGroupSet: {created_sets}. "
        f"Обновлено EquipmentGroup: {updated_groups_fields}. "
        f"«Котельные» (standalone): обновлено {updated_kotelnye}, создано {created_kotelnye}. "
        f"Обновлено MachineFuelParam: {updated_fuel_params}. "
        f"Ошибок: {len(errors)}. Подробности — в логах."
    )
    return {
        "message": message,
        "processed_rows": processed_rows,
        "skipped_empty": skipped_empty,
        "skipped_invalid": skipped_invalid,
        "updated_machines": updated_machines,
        "created_links": created_links,
        "created_groups": created_groups,
        "created_sets": created_sets,
        "updated_groups_fields": updated_groups_fields,
        "updated_kotelnye": updated_kotelnye,
        "created_kotelnye": created_kotelnye,
        "updated_fuel_params": updated_fuel_params,
        "errors_count": len(errors),
        "report_bytes": report_bytes,
    }

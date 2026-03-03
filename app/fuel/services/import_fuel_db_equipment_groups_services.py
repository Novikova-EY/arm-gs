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
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroup
from app.common.models.database_version_model import DatabaseVersion
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.external_mapping.fue_em_equipment_group_model import (
    EquipmentGroupExternalMapping,
)
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam


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


# Поля EquipmentGroupSet для заполнения из Excel (кроме id, id_equipment_group, external_code, database_version_id).
# name формируется как f"{station.name} ({equipment_group.name})" и НЕ берётся из Excel.
EQUIPMENT_GROUP_SET_UPDATE_FIELDS = [
    "name_ext", "niv", "comp", "main", "d", "r", "forem",
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

    add_aliases("id_machine", ["id_machine", "machine_id", "id_агрегата", "id_агрегат"])
    add_aliases("id_station", ["id_station", "station_id", "id_станции"])
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
    add_aliases("numb", ["numb", "topl_numb", "номер"])
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
    add_aliases("numb", ["numb", "agr_numb", "topl_agr_numb"])
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
    return func.lower(func.trim(func.replace(EquipmentGroup.name, "\xa0", " ")))


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
) -> EquipmentGroup | None:
    """
    Поиск EquipmentGroup по тексту из Excel.
    1) По имени EquipmentGroup.name (с учётом database_version_id)
    2) Fallback: по EquipmentGroupExternalMapping (name_topl, gruppa_oborud) -> ref_uuid -> EquipmentGroup
    3) Fallback без фильтра версии (если группа есть только в одной версии)
    mappings_cache: предзагруженный список маппингов (избегает повторной загрузки при импорте).
    """
    group_norm_sql = (
        str(group_text or "").strip().lower().replace("\xa0", " ").replace("\u00a0", " ")
    )
    if not group_norm_sql:
        return None

    # 1. Поиск по EquipmentGroup.name (нормализация как в SQL)
    eq_query = EquipmentGroup.query.filter(
        _equipment_group_name_sql_normalized() == group_norm_sql
    )
    eq_query = filter_by_explicit_db_version(eq_query, EquipmentGroup, db_version_id)
    eq = eq_query.first()
    if eq:
        return eq

    group_norm_digits = group_norm_sql.replace(" ", "")
    if group_norm_digits.isdigit():
        eq_query = EquipmentGroup.query.filter(EquipmentGroup.id == int(group_norm_digits))
        eq_query = filter_by_explicit_db_version(eq_query, EquipmentGroup, db_version_id)
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
            eq_query = EquipmentGroup.query.filter(EquipmentGroup.ref_uuid == ref_uuid)
            eq_query = filter_by_explicit_db_version(eq_query, EquipmentGroup, db_version_id)
            eg = eq_query.first()
            if eg:
                return eg

    # 3. Fallback без фильтра версии (если группа есть только в одной версии)
    eq_query = EquipmentGroup.query.filter(
        _equipment_group_name_sql_normalized() == group_norm_sql
    )
    eq = eq_query.first()
    if eq:
        return eq
    if group_norm_digits.isdigit():
        return EquipmentGroup.query.filter(
            EquipmentGroup.id == int(group_norm_digits)
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


def _resolve_equipment_group_for_version(
    equipment_group_id: int, target_db_version_id: int | None
) -> int | None:
    """
    Возвращает id EquipmentGroup с тем же ref_uuid/именем, привязанный к target_db_version_id.
    Сначала по ref_uuid (если есть), иначе по имени.
    """
    eg = EquipmentGroup.query.get(equipment_group_id)
    if not eg:
        return None
    # 1. По ref_uuid — стабильная связь между версиями
    if getattr(eg, "ref_uuid", None):
        eq_query = EquipmentGroup.query.filter(EquipmentGroup.ref_uuid == eg.ref_uuid)
        eq_query = filter_by_explicit_db_version(eq_query, EquipmentGroup, target_db_version_id)
        resolved = eq_query.first()
        if resolved:
            return resolved.id
    # 2. По имени (если ref_uuid нет или не найден в целевой версии)
    if eg.name:
        name_norm = eg.name.strip().lower().replace("\xa0", " ")
        eq_query = EquipmentGroup.query.filter(
            func.lower(func.trim(func.replace(EquipmentGroup.name, "\xa0", " "))) == name_norm
        )
        eq_query = filter_by_explicit_db_version(eq_query, EquipmentGroup, target_db_version_id)
        resolved = eq_query.first()
        if resolved:
            return resolved.id
    return None


def import_fuel_db_equipment_groups_from_excel(file, user: str, *, build_report: bool = True) -> dict:
    """
    Шаг 3: Строки с id_machine и id_station — привязка групп оборудования к агрегатам.
    По id_machine находим агрегат, по external_code станции — все станции с тем же кодом,
    берём все машины этих станций, по equipment_group обновляем Machine.id_equipment_group.

    Шаг 4.2: Строки без id_machine, с id_station — заполнение полей EquipmentGroupSet (topl_*).
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
    df = xls.parse(sheet_name, header=0)
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
    # Шаг 3 требует id_machine и id_station. Шаг 4.2 требует только id_station.
    if not has_station:
        raise ValueError(
            "Неверный шаблон файла: необходима колонка id_station. "
            "Шаг 3 (привязка групп) требует id_machine и id_station. "
            "Шаг 4.2 (заполнение полей EquipmentGroupSet) требует id_station."
        )
    if not has_machine:
        print("[IMPORT_FUEL_DB]   Колонка id_machine отсутствует — шаг 3 (привязка групп) пропускается")
    print(f"[IMPORT_FUEL_DB] Шаг 2: Проверка колонок OK (id_machine={has_machine}, id_station={has_station})")

    processed_rows = 0
    skipped_empty = 0
    skipped_invalid = 0
    updated_machines = 0
    errors = []
    audit_counts: dict[str, int] = {}
    audit_samples: dict[str, list[str]] = {}
    # Результат по каждой строке для отчёта: index -> {step3, step4_2, step4_3}
    row_results: dict[int | float, dict[str, str]] = defaultdict(lambda: {"step3": None, "step4_2": None, "step4_3": None})

    def _audit_inc(reason: str, sample: str | None = None) -> None:
        audit_counts[reason] = audit_counts.get(reason, 0) + 1
        if sample:
            lst = audit_samples.setdefault(reason, [])
            if len(lst) < 30:
                lst.append(sample)

    def _set_row_result(index, step: str, value: str) -> None:
        row_results[index][step] = value

    # Пары (station_id, id_equipment_group), обработанные в файле — для шага 4.1
    file_processed_pairs: set[tuple[int, int]] = set()

    # Кэш (group_text, db_version_id) -> EquipmentGroup | None — избегаем тысяч повторных запросов к БД
    _eg_cache: dict[tuple[str, int | None], EquipmentGroup | None] = {}
    # Маппинги загружаем один раз — иначе при каждом cache miss повторная загрузка тормозит импорт
    _mappings_cache = EquipmentGroupExternalMapping.query.filter(
        EquipmentGroupExternalMapping.equipment_group_ref_uuid.isnot(None),
    ).all()

    def _find_eg_cached(gt: str, vid: int | None) -> EquipmentGroup | None:
        key = (_normalize_for_mapping(gt) or "", vid)
        if key not in _eg_cache:
            _eg_cache[key] = _find_equipment_group_by_name_or_mapping(gt, vid, _mappings_cache)
        return _eg_cache[key]

    STEP3_COMMIT_EVERY = 15  # Частый commit — при 600+ строках без него воркер зависает
    last_step3_commit_at = 0

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
            machine_id = _safe_int(row.get("id_machine")) if has_machine else None
            station_id_row = _safe_int(row.get("id_station")) if has_station else None
            group_text = _get_equipment_group_from_row(row, df.columns)
            if group_text:
                group_text = _clean_name(group_text)

            if processed_rows <= 20 or (processed_rows % 100 == 0):
                print(f"[IMPORT_FUEL_DB]   Строка {index}: id_machine={machine_id} id_station={station_id_row} equipment_group={group_text} "
                      f"(прогресс: {processed_rows}/{len(df)})", flush=True)

            if not group_text:
                skipped_invalid += 1
                _audit_inc("row_missing_required", f"row_index={index}")
                _set_row_result(index, "step3", "Пропуск: нет equipment_group")
                if processed_rows <= 30:
                    print(f"[IMPORT_FUEL_DB]     -> пропуск: нет equipment_group")
                continue

            # Шаг 3: обрабатываем только строки с id_machine И id_station
            if machine_id is None or station_id_row is None:
                _audit_inc("row_skip_step3", f"row_index={index}; нужны id_machine и id_station")
                _set_row_result(index, "step3", "Пропуск: нужны id_machine и id_station")
                if processed_rows <= 20:
                    print(f"[IMPORT_FUEL_DB]     -> пропуск шага 3: нужны id_machine и id_station")
                continue

            # По id_machine находим агрегат
            machine = Machine.query.get(machine_id)
            if not machine or not machine.id_station:
                skipped_invalid += 1
                _audit_inc("machine_not_found", f"row_index={index}; id_machine={machine_id}")
                _set_row_result(index, "step3", f"Пропуск: агрегат id={machine_id} не найден")
                print(f"[IMPORT_FUEL_DB]     -> пропуск: агрегат id={machine_id} не найден")
                continue

            station = Station.query.get(machine.id_station)
            if not station or not station.external_code:
                skipped_invalid += 1
                _audit_inc("station_not_found_or_no_code", f"row_index={index}; id_station={machine.id_station}")
                _set_row_result(index, "step3", "Пропуск: станция не найдена или нет external_code")
                print(f"[IMPORT_FUEL_DB]     -> пропуск: станция агрегата не найдена или нет external_code")
                continue

            # По external_code находим все станции с тем же кодом
            stations_same_code = Station.query.filter(Station.external_code == station.external_code).all()
            station_ids = [s.id for s in stations_same_code]
            # Все машины (агрегаты) этих станций
            machines_with_code = (
                Machine.query.filter(Machine.id_station.in_(station_ids)).all()
                if station_ids else []
            )
            if processed_rows <= 20 or (processed_rows % 100 == 0):
                print(f"[IMPORT_FUEL_DB]     -> id_machine={machine_id} external_code={station.external_code}, "
                      f"станций: {len(station_ids)}, машин: {len(machines_with_code)}")

            step3_updated_count = 0
            step3_not_found = False

            for m in machines_with_code:
                db_version_id = getattr(m, "database_version_id", None)
                equipment_group = _find_eg_cached(group_text, db_version_id)

                if not equipment_group:
                    _audit_inc("equipment_group_not_found", f"row_index={index}; group={group_text}; version={db_version_id}")
                    step3_not_found = True
                    if processed_rows <= 20:
                        print(f"[IMPORT_FUEL_DB]     -> машина id={m.id} version={db_version_id}: группа '{group_text}' не найдена")
                    continue

                file_processed_pairs.add((m.id_station, equipment_group.id))
                if m.id_equipment_group != equipment_group.id:
                    old_id = m.id_equipment_group
                    m.id_equipment_group = equipment_group.id
                    db.session.add(m)
                    updated_machines += 1
                    step3_updated_count += 1
                    if processed_rows <= 20 or updated_machines <= 50:
                        print(f"[IMPORT_FUEL_DB]     -> ОБНОВЛЕНО: машина id={m.id} version={db_version_id} id_equipment_group {old_id} -> {equipment_group.id} ({equipment_group.name})")
                    # Коммит внутри цикла — иначе при 40+ машинах на строку сессия раздувается и воркер зависает
                    if updated_machines - last_step3_commit_at >= STEP3_COMMIT_EVERY:
                        try:
                            # Логируем перед/после commit для диагностики зависаний (при прогресс 100/688 и т.п.)
                            _log_commit = updated_machines <= 60 or (updated_machines % 75) < STEP3_COMMIT_EVERY
                            if _log_commit:
                                print(f"[IMPORT_FUEL_DB]     -> перед commit (строка {index}, updated={updated_machines})...", flush=True)
                            db.session.commit()
                            db.session.expire_all()
                            last_step3_commit_at = updated_machines
                            if _log_commit:
                                print(f"[IMPORT_FUEL_DB]     -> после commit OK ({updated_machines} агрегатов)", flush=True)
                            elif updated_machines % 75 < STEP3_COMMIT_EVERY:
                                print(f"[IMPORT_FUEL_DB]     -> commit: {updated_machines} агрегатов ({processed_rows}/{len(df)})")
                        except Exception as commit_err:
                            logger.warning("[IMPORT_FUEL_DB] промежуточный commit: %s", commit_err)

            if step3_updated_count > 0:
                _set_row_result(index, "step3", f"ОБНОВЛЕНО: привязано {step3_updated_count} агрегат(ов) к группе '{group_text}'")
            elif step3_not_found:
                _set_row_result(index, "step3", f"Пропуск: группа оборудования '{group_text}' не найдена в справочнике")

            # Периодический commit: при 600+ строках сессия переполняется — воркер зависает
            if updated_machines > last_step3_commit_at and (
                updated_machines - last_step3_commit_at >= STEP3_COMMIT_EVERY or processed_rows % 50 == 0
            ):
                try:
                    _log_commit = updated_machines <= 60 or (updated_machines % 75) < STEP3_COMMIT_EVERY
                    if _log_commit:
                        print(f"[IMPORT_FUEL_DB]     -> перед commit (строка {index}, updated={updated_machines})...", flush=True)
                    db.session.commit()
                    db.session.expire_all()  # Освобождаем память от загруженных объектов
                    last_step3_commit_at = updated_machines
                    if _log_commit:
                        print(f"[IMPORT_FUEL_DB]     -> после commit OK ({updated_machines} агрегатов)", flush=True)
                    elif updated_machines % 75 < STEP3_COMMIT_EVERY:
                        print(f"[IMPORT_FUEL_DB]     -> commit: {updated_machines} агрегатов ({processed_rows}/{len(df)})")
                except Exception as commit_err:
                    logger.warning("[IMPORT_FUEL_DB] промежуточный commit не удался: %s", commit_err)

        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
            err = {"row_index": int(index) if isinstance(index, (int, float)) else str(index), "filename": filename}
            errors.append(err)
            err_msg = str(e)[:200] if e else "Неизвестная ошибка"
            _set_row_result(index, "step3", f"ОШИБКА: {err_msg}")
            print(f"[IMPORT_FUEL_DB]   Строка {index}: ИСКЛЮЧЕНИЕ - {err}")
            logger.exception("[IMPORT_FUEL_DB_EQUIPMENT_GROUPS] row failed: %s", err)
            _audit_inc("row_exception", str(err))
            continue

    print(f"[IMPORT_FUEL_DB] Шаг 4: Commit в БД... (обработано={processed_rows}, обновлено={updated_machines}, ошибок={len(errors)})")
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

    # Шаг 4.1: Формирование EquipmentGroupSet и EquipmentGroupSetStation.
    # Уникальность: один EquipmentGroupSet на (external_code, equipment_group, database_version_id).
    # Это предотвращает дубликаты, когда одна станция имеет несколько Station-записей в одной версии.
    created_sets = 0
    created_links = 0
    updated_machine_set_ids = 0
    print("[IMPORT_FUEL_DB] Шаг 4.1: Формирование EquipmentGroupSet (по external_code, без дубликатов)...")
    try:
        # (external_code, equipment_group_id) из файла
        ec_eg_pairs: set[tuple[str, int]] = set()
        for (station_id, equipment_group_id) in file_processed_pairs:
            st = Station.query.get(station_id)
            if st and st.external_code:
                ec_eg_pairs.add((st.external_code, equipment_group_id))

        machines_with_group = (
            Machine.query
            .filter(Machine.id_equipment_group.isnot(None))
            .filter(Machine.id_station.isnot(None))
            .all()
        )
        groups: dict[tuple[int, int], list[Machine]] = defaultdict(list)
        for m in machines_with_group:
            key = (m.id_station, m.id_equipment_group)
            if key in file_processed_pairs:
                groups[key].append(m)

        machine_version_ids: set[int | None] = {getattr(m, "database_version_id", None) for m in machines_with_group}
        all_db_versions = DatabaseVersion.query.filter(
            DatabaseVersion.id.isnot(None),
            DatabaseVersion.id > 0,
        ).all()
        valid_version_ids = {v.id for v in all_db_versions}
        # Используем только версии, существующие в gs_database_versions (FK constraint).
        # Иначе INSERT в gs_fue_equipment_group_sets падает, если machine/station
        # ссылается на удалённую или несуществующую версию.
        db_version_ids: set[int | None] = valid_version_ids.copy()
        db_version_ids.add(None)
        for mid in machine_version_ids:
            if mid is not None and mid in valid_version_ids:
                db_version_ids.add(mid)
        orphaned = {m for m in machine_version_ids if m is not None and m not in valid_version_ids}
        if orphaned:
            logger.warning(
                "[IMPORT_FUEL_DB_EQUIPMENT_GROUPS] machine/station ссылаются на несуществующие database_version_id=%s "
                "(отсутствуют в gs_database_versions) — записи для этих версий не создаются",
                sorted(orphaned),
            )
        db_version_list = list(db_version_ids)
        print(f"[IMPORT_FUEL_DB]   Пар (external_code, equipment_group): {len(ec_eg_pairs)}, версий: {len(db_version_list)}")

        # Кэш: (external_code, resolved_eg_id, db_version_id) -> EquipmentGroupSet
        seg_cache: dict[tuple[str, int, int | None], EquipmentGroupSet] = {}
        BATCH_COMMIT_SIZE = 250  # Периодический commit, чтобы не зависать на одном большом
        last_batch_commit_at = 0
        pair_index = 0
        total_pairs = len(ec_eg_pairs)

        for (external_code, equipment_group_id) in ec_eg_pairs:
            pair_index += 1
            if pair_index % 50 == 0 or pair_index == total_pairs:
                print(f"[IMPORT_FUEL_DB]   Прогресс: {pair_index}/{total_pairs} пар, создано sets={created_sets}")
            for db_version_id in db_version_list:
                resolved_eg_id = _resolve_equipment_group_for_version(equipment_group_id, db_version_id)
                if resolved_eg_id is None:
                    continue

                cache_key = (external_code, resolved_eg_id, db_version_id)
                if cache_key in seg_cache:
                    seg = seg_cache[cache_key]
                else:
                    # Все станции с этим external_code и database_version_id
                    st_query = Station.query.filter(Station.external_code == external_code)
                    if db_version_id is None:
                        st_query = st_query.filter(Station.database_version_id.is_(None))
                    else:
                        st_query = st_query.filter(Station.database_version_id == db_version_id)
                    stations_in_version = st_query.all()
                    station_ids = [s.id for s in stations_in_version]
                    if not station_ids:
                        continue

                    # Есть ли уже EquipmentGroupSet для (external_code, equipment_group, version)?
                    # Поиск 1: через EquipmentGroupSetStation (станции с нашим external_code)
                    link_query = (
                        EquipmentGroupSetStation.query
                        .join(EquipmentGroupSet, EquipmentGroupSetStation.equipment_group_set_id == EquipmentGroupSet.id)
                        .join(Station, EquipmentGroupSetStation.station_id == Station.id)
                        .filter(
                            Station.external_code == external_code,
                            EquipmentGroupSet.id_equipment_group == resolved_eg_id,
                        )
                    )
                    if db_version_id is None:
                        link_query = link_query.filter(
                            EquipmentGroupSetStation.database_version_id.is_(None),
                            EquipmentGroupSet.database_version_id.is_(None),
                        )
                    else:
                        link_query = link_query.filter(
                            EquipmentGroupSetStation.database_version_id == db_version_id,
                            EquipmentGroupSet.database_version_id == db_version_id,
                        )
                    link = link_query.first()

                    if link:
                        seg = link.equipment_group_set
                        # Корректируем name: название станции (тип группы оборудования)
                        station = stations_in_version[0] if stations_in_version else None
                        equipment_group = EquipmentGroup.query.get(resolved_eg_id)
                        expected_name = None
                        if station and station.name and equipment_group and equipment_group.name:
                            expected_name = f"{station.name} ({equipment_group.name})"
                        if expected_name and seg.name != expected_name:
                            seg.name = expected_name
                            db.session.add(seg)
                        # Создаём недостающие связи для остальных станций
                        current_version = get_current_db_version_id()
                        for sid in station_ids:
                            eq_query = EquipmentGroupSetStation.query.filter(
                                EquipmentGroupSetStation.equipment_group_set_id == seg.id,
                                EquipmentGroupSetStation.station_id == sid,
                            )
                            if db_version_id is None:
                                eq_query = eq_query.filter(EquipmentGroupSetStation.database_version_id.is_(None))
                            else:
                                eq_query = eq_query.filter(EquipmentGroupSetStation.database_version_id == db_version_id)
                            exists = eq_query.first()
                            if not exists:
                                extra_link = EquipmentGroupSetStation(
                                    equipment_group_set_id=seg.id,
                                    station_id=sid,
                                )
                                if db_version_id == current_version:
                                    set_db_version_on_create(extra_link)
                                else:
                                    extra_link.database_version_id = db_version_id
                                db.session.add(extra_link)
                                db.session.flush()
                                created_links += 1
                    else:
                        # Логика как в _get_or_create_equipment_group_set (machine_services.py):
                        # group_name = f"{station.name} ({equipment_group.name})"
                        station = stations_in_version[0] if stations_in_version else None
                        equipment_group = EquipmentGroup.query.get(resolved_eg_id)
                        group_name = None
                        if station and station.name and equipment_group and equipment_group.name:
                            group_name = f"{station.name} ({equipment_group.name})"
                        seg = EquipmentGroupSet(
                            id_equipment_group=resolved_eg_id,
                            name=group_name,
                        )
                        seg._station_external_code_for_key = external_code
                        current_version = get_current_db_version_id()
                        if db_version_id == current_version:
                            set_db_version_on_create(seg)
                        else:
                            seg.database_version_id = db_version_id
                        db.session.add(seg)
                        db.session.flush()
                        created_sets += 1
                        for sid in station_ids:
                            lnk = EquipmentGroupSetStation(
                                equipment_group_set_id=seg.id,
                                station_id=sid,
                            )
                            if db_version_id == current_version:
                                set_db_version_on_create(lnk)
                            else:
                                lnk.database_version_id = db_version_id
                            db.session.add(lnk)
                            db.session.flush()
                            created_links += 1
                        if created_sets <= 10 or created_sets % 100 == 0:
                            print(f"[IMPORT_FUEL_DB]     Создан: EquipmentGroupSet id={seg.id} ... (всего {created_sets})")

                    seg_cache[cache_key] = seg

            # Привязка машин к set
            for (station_id, equipment_group_id), machines in groups.items():
                st = Station.query.get(station_id)
                if not st or not st.external_code:
                    continue
                for m in machines:
                    m_version = getattr(m, "database_version_id", None)
                    resolved_eg_id = _resolve_equipment_group_for_version(equipment_group_id, m_version)
                    if resolved_eg_id is None:
                        continue
                    cache_key = (st.external_code, resolved_eg_id, m_version)
                    seg = seg_cache.get(cache_key)
                    if seg:
                        changed = False
                        if m.equipment_group_set_id != seg.id:
                            m.equipment_group_set_id = seg.id
                            updated_machine_set_ids += 1
                            changed = True
                        if m.id_equipment_group != resolved_eg_id:
                            m.id_equipment_group = resolved_eg_id
                            changed = True
                        if changed:
                            db.session.add(m)

            # Периодический commit, чтобы не зависать на одном большом (3000+ записей)
            if created_sets >= last_batch_commit_at + BATCH_COMMIT_SIZE:
                db.session.commit()
                last_batch_commit_at = created_sets
                print(f"[IMPORT_FUEL_DB]   Batch commit OK (создано sets={created_sets}, links={created_links})")

        if created_sets or created_links or updated_machine_set_ids:
            if last_batch_commit_at < created_sets:
                print(f"[IMPORT_FUEL_DB]   Финальный commit... (осталось ~{created_sets - last_batch_commit_at} новых записей)")
            db.session.commit()
            print(f"[IMPORT_FUEL_DB]   EquipmentGroupSet: создано {created_sets}, "
                  f"EquipmentGroupSetStation: создано {created_links}, "
                  f"машин привязано к set: {updated_machine_set_ids}")
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

    # Шаг 4.2: Заполнение полей EquipmentGroupSet из файла.
    # Обрабатываем ТОЛЬКО строки без id_machine (есть id_station).
    # В файле реальными данными для полей topl_* (name_ext, niv, comp и др.)
    # заполняются только «станционные» строки, где указан id_station и НЕТ id_machine.
    # Строки с id_machine содержат только привязку агрегатов и не должны перетирать поля EquipmentGroupSet.
    # Для каждой строки: по station находим external_code, все станции с тем же кодом,
    # по equipment_group — группу. Заполняем поля name_ext, niv, comp и др.
    updated_sets_fields = 0
    step4_2_rows_with_data = 0
    step4_2_rows_no_links = 0
    step4_2_rows_no_changes = 0
    print("[IMPORT_FUEL_DB] Шаг 4.2: Заполнение полей EquipmentGroupSet из файла...")
    try:
        for index, row in df.iterrows():
            if row.isnull().all():
                continue
            machine_id = _safe_int(row.get("id_machine")) if has_machine else None
            station_id_row = _safe_int(row.get("id_station")) if has_station else None
            # Для шага 4.2 используем только строки БЕЗ id_machine.
            # В них заданы поля topl_*; строки с id_machine могут содержать пустые значения и
            # не должны перезаписывать уже заполненные поля EquipmentGroupSet.
            if machine_id is not None:
                _set_row_result(index, "step4_2", "Пропуск: шаг 4.2 только для строк без id_machine")
                continue
            if station_id_row is None:
                continue

            group_text = _get_equipment_group_from_row(row, df.columns)
            if group_text:
                group_text = _clean_name(group_text)
            if not group_text:
                _set_row_result(index, "step4_2", "Пропуск: нет equipment_group")
                continue

            # По id_station находим станцию
            station = Station.query.get(station_id_row)
            if not station or not station.external_code:
                _set_row_result(index, "step4_2", "Пропуск: станция не найдена или нет external_code")
                continue
            # По external_code находим все станции с тем же кодом
            stations_same_code = Station.query.filter(Station.external_code == station.external_code).all()
            if not stations_same_code:
                _set_row_result(index, "step4_2", "Пропуск: нет станций с таким external_code")
                continue

            # По equipment_group ищем группу оборудования.
            # Ищем по версии каждой станции — иначе resolved_eg_id может не совпасть с id в EquipmentGroupSet.
            # Шаг 4.1 создаёт EquipmentGroupSet с id_equipment_group = resolved для каждой версии из file_processed_pairs.
            equipment_group_id = None
            for st0 in stations_same_code:
                vid = getattr(st0, "database_version_id", None)
                eq = _find_equipment_group_by_name_or_mapping(group_text, vid, _mappings_cache)
                if eq:
                    equipment_group_id = eq.id
                    break
            if equipment_group_id is None:
                _set_row_result(index, "step4_2", f"Пропуск: группа '{group_text}' не найдена в справочнике")
                continue

            # Собираем значения из строки (name_ext, niv, comp и др.)
            # Пробуем canonical и альтернативные колонки (Прим., Субъект РФ и т.д.)
            row_values: dict[str, str | None] = {}
            for field in EQUIPMENT_GROUP_SET_UPDATE_FIELDS:
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
                    row_values[field] = val

            if not row_values:
                _set_row_result(index, "step4_2", "Пропуск: нет данных для заполнения полей")
                if index < 3:
                    sample_cols = [c for c in EQUIPMENT_GROUP_SET_UPDATE_FIELDS[:6] if c in df.columns]
                    sample_vals = {c: _extract_cell_value(row, c) for c in sample_cols}
                    print(f"[IMPORT_FUEL_DB]     [4.2] Строка {index}: row_values пуст. Примеры: {sample_vals}")
                continue

            step4_2_rows_with_data += 1
            # Для каждой станции с этим external_code: у станции может быть одна или несколько групп.
            # Ищем все EquipmentGroupSet, связанные со станцией и matching equipment_group.
            updated_seg_ids: set[int] = set()
            row_updated_count = 0
            found_links_in_row = False
            for st in stations_same_code:
                sid = st.id
                db_version_id = getattr(st, "database_version_id", None)
                resolved_eg_id = _resolve_equipment_group_for_version(equipment_group_id, db_version_id)
                if resolved_eg_id is None:
                    continue
                # Все связи станции с EquipmentGroupSet для этой группы (на случай нескольких)
                link_query = (
                    EquipmentGroupSetStation.query
                    .join(EquipmentGroupSet, EquipmentGroupSetStation.equipment_group_set_id == EquipmentGroupSet.id)
                    .filter(
                        EquipmentGroupSetStation.station_id == sid,
                        EquipmentGroupSet.id_equipment_group == resolved_eg_id,
                    )
                )
                if db_version_id is None:
                    link_query = link_query.filter(
                        EquipmentGroupSetStation.database_version_id.is_(None),
                        EquipmentGroupSet.database_version_id.is_(None),
                    )
                else:
                    link_query = link_query.filter(
                        EquipmentGroupSetStation.database_version_id == db_version_id,
                        EquipmentGroupSet.database_version_id == db_version_id,
                    )
                links = link_query.all()
                if links:
                    found_links_in_row = True
                elif step4_2_rows_with_data <= 3:
                    print(f"[IMPORT_FUEL_DB]     [4.2] Строка {index} st.id={sid} version={db_version_id} "
                          f"resolved_eg={resolved_eg_id}: ссылок EquipmentGroupSetStation не найдено")
                for link in links:
                    seg = link.equipment_group_set
                    if seg.id in updated_seg_ids:
                        continue
                    changed = False
                    for field, val in row_values.items():
                        if hasattr(seg, field) and getattr(seg, field) != val:
                            setattr(seg, field, val)
                            changed = True
                    if changed:
                        db.session.add(seg)
                        updated_sets_fields += 1
                        row_updated_count += 1
                        updated_seg_ids.add(seg.id)

            if row_updated_count > 0:
                _set_row_result(index, "step4_2", f"ОБНОВЛЕНО: заполнено полей EquipmentGroupSet для {row_updated_count} записей")
            else:
                if not found_links_in_row:
                    step4_2_rows_no_links += 1
                else:
                    step4_2_rows_no_changes += 1
                _set_row_result(index, "step4_2", "Без изменений (поля уже актуальны)")

        if step4_2_rows_with_data > 0 and updated_sets_fields == 0:
            print(f"[IMPORT_FUEL_DB]   [4.2] Диагностика: строк с данными={step4_2_rows_with_data}, "
                  f"без ссылок={step4_2_rows_no_links}, без изменений={step4_2_rows_no_changes}")
        if updated_sets_fields:
            db.session.commit()
            print(f"[IMPORT_FUEL_DB]   Обновлено записей EquipmentGroupSet: {updated_sets_fields}")
        else:
            print("[IMPORT_FUEL_DB]   Нет изменений в полях EquipmentGroupSet")
    except Exception as e:
        print(f"[IMPORT_FUEL_DB]   ОШИБКА при заполнении полей EquipmentGroupSet: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass
        logger.exception("[IMPORT_FUEL_DB_EQUIPMENT_GROUPS] Step 4.2 failed: %s", e)
        raise

    # Шаг 4.3: Заполнение MachineFuelParam для строк с id_machine и id_station.
    # По id_machine находим агрегат, по external_code — все агрегаты с тем же кодом.
    # Для каждого агрегата заполняем MachineFuelParam данными из Excel.
    # database_version_id должен существовать в gs_database_versions (FK constraint).
    updated_fuel_params = 0
    print("[IMPORT_FUEL_DB] Шаг 4.3: Заполнение MachineFuelParam (строки с id_machine и id_station)...")
    try:
        all_db_versions = DatabaseVersion.query.filter(
            DatabaseVersion.id.isnot(None),
            DatabaseVersion.id > 0,
        ).all()
        valid_version_ids = {v.id for v in all_db_versions}
        for index, row in df.iterrows():
            if row.isnull().all():
                continue
            machine_id = _safe_int(row.get("id_machine")) if has_machine else None
            station_id_row = _safe_int(row.get("id_station")) if has_station else None
            if machine_id is None or station_id_row is None:
                continue

            # По id_machine находим агрегат
            machine = Machine.query.get(machine_id)
            if not machine or not machine.external_code:
                _set_row_result(index, "step4_3", "Пропуск: агрегат не найден или нет external_code")
                continue

            # По external_code находим все агрегаты с таким же кодом
            machines_same_code = Machine.query.filter(Machine.external_code == machine.external_code).all()
            if not machines_same_code:
                _set_row_result(index, "step4_3", "Пропуск: нет агрегатов с таким external_code")
                continue

            # Собираем значения из строки (пробуем основное имя и альтернативы)
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

            # grcode: значения из столбца grcode → MachineFuelParam.grcode (EquipmentGroupSet.numb, integer)
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

            current_version = get_current_db_version_id()
            row_fuel_param_count = 0
            for m in machines_same_code:
                # MachineFuelParam: одна запись на одну машину (UniqueConstraint machine_id)
                mtp = MachineFuelParam.query.filter_by(machine_id=m.id).first()
                if mtp is None:
                    mtp = MachineFuelParam(machine_id=m.id)
                    db_version_id = getattr(m, "database_version_id", None)
                    # database_version_id должен существовать в gs_database_versions (FK constraint)
                    if db_version_id is not None and db_version_id not in valid_version_ids:
                        logger.warning(
                            "[IMPORT_FUEL_DB_EQUIPMENT_GROUPS] machine id=%s version=%s не в gs_database_versions, "
                            "используем current_version=%s",
                            m.id, db_version_id, current_version,
                        )
                        db_version_id = current_version
                    # Явно задаём только валидную версию (FK в gs_database_versions)
                    if db_version_id is not None and db_version_id in valid_version_ids:
                        mtp.database_version_id = db_version_id
                    elif current_version is not None and current_version in valid_version_ids:
                        mtp.database_version_id = current_version
                    else:
                        # Не используем set_db_version_on_create — current_version может быть невалидной
                        set_db_version_on_create(mtp)
                        if (
                            getattr(mtp, "database_version_id", None) is not None
                            and mtp.database_version_id not in valid_version_ids
                        ):
                            mtp.database_version_id = None
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
                _set_row_result(index, "step4_3", f"ОБНОВЛЕНО: MachineFuelParam для {row_fuel_param_count} агрегат(ов)")
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
    print(f"[IMPORT_FUEL_DB] Шаг 5: ИТОГ. processed_rows={processed_rows} skipped_empty={skipped_empty} "
          f"skipped_invalid={skipped_invalid} updated_machines={updated_machines} "
          f"created_sets={created_sets} created_links={created_links} machine_set_ids={updated_machine_set_ids} "
          f"updated_sets_fields={updated_sets_fields} updated_fuel_params={updated_fuel_params} "
          f"errors={len(errors)} time={elapsed:.2f}s")
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
                f"created_equipment_group_sets={created_sets}; created_links={created_links}; "
                f"machine_set_ids_updated={updated_machine_set_ids}; "
                f"updated_sets_fields={updated_sets_fields}; "
                f"updated_fuel_params={updated_fuel_params}; "
                f"errors_count={len(errors)}; audit_counts={audit_counts}"
            ),
            entity_type="import_fuel_db_equipment_groups",
            entity_id=None,
        )
    except Exception:
        logger.exception("[IMPORT_FUEL_DB_EQUIPMENT_GROUPS] failed to write log filename=%s", filename)

    # Формируем отчёт только если запрошен — экономит время и память при большом файле
    report_bytes = _build_import_report_excel(df, dict(row_results)) if build_report else None

    message = (
        "Загрузка данных БД Топливо завершена. "
        f"Обработано строк: {processed_rows}. Обновлено агрегатов: {updated_machines}. "
        f"Создано EquipmentGroupSet: {created_sets}, связей со станциями: {created_links}. "
        f"Обновлено полей EquipmentGroupSet: {updated_sets_fields}. "
        f"Обновлено MachineFuelParam: {updated_fuel_params}. "
        f"Ошибок: {len(errors)}. Подробности — в логах."
    )
    return {
        "message": message,
        "processed_rows": processed_rows,
        "skipped_empty": skipped_empty,
        "skipped_invalid": skipped_invalid,
        "updated_machines": updated_machines,
        "created_equipment_group_sets": created_sets,
        "created_links": created_links,
        "machine_set_ids_updated": updated_machine_set_ids,
        "updated_sets_fields": updated_sets_fields,
        "updated_fuel_params": updated_fuel_params,
        "errors_count": len(errors),
        "report_bytes": report_bytes,
    }

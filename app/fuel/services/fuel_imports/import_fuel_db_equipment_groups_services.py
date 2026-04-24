# -*- coding: utf-8 -*-
"""Сервис загрузки данных БД Топливо: привязка групп оборудования к агрегатам по external_code."""

from __future__ import annotations

import logging
import re
import uuid
from collections import defaultdict
from io import BytesIO
import time
import pandas as pd
from sqlalchemy import func
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

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
from app.refdata.models.gen_companies.gen_company_model import GenCompany
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroupType
from app.common.models.database_version_model import DatabaseVersion
from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
from app.fuel.models.fue_equipment_group_set_station_model import (
    EquipmentGroupSetStation,
)
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_consumption_recalc_services import (
    recalculate_all_specific_fuel_consumption_calc,
)


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
    s = s.replace("\r", " ").replace("\n", " ").replace("\u00a0", " ").replace("\xa0", " ").strip().lower()
    s = s.replace("е", "е")
    s = " ".join(s.split())
    s = s.replace(" ", "_")
    s = "".join(ch for ch in s if ch.isalnum() or ch == "_")
    s = "_".join(filter(None, s.split("_")))
    return s


# Нормализованные заголовки столбцов, из которых берётся EquipmentGroup.numb (как в экспорте со страницы).
_GE_NUMB_SOURCE_COLUMN_NORMALS = frozenset(
    (
        "numb1120",
        "topl_numb",
        _normalize_column_name("Код станции (numb)"),
    )
)

# После алиасов: заголовок Excel «Группа оборудования» → это имя столбца (распознавание «Котельные»).
GE_GRUPPA_OBORUDOVANIYA_COLUMN = "ge_gruppa_oborudovaniya"


def _detect_header_row_and_parse_excel(xls: pd.ExcelFile, sheet_name: str) -> tuple[pd.DataFrame, int]:
    """
    Основная функция разбора Excel для импорта stations_equipment_groups.
    Сначала четко определяем строку с заголовками и перечень столбцов, затем читаем данные.

    Строка считается заголовком, если хотя бы в одной ячейке (нормализованное значение)
    точно совпадает с одним из маркеров: id_station, id_machine, equipment_group, equipment_group_id.
    Это исключает ложное срабатывание, когда маркер встречается внутри текста в данных.

    Returns:
        (df, header_row_index) — DataFrame с данными и индекс строки заголовка (0-based).
    """
    df_preview = xls.parse(sheet_name, header=None, nrows=30)
    header_markers = {
        "id_station",
        "id_machine",
        "equipment_group",
        "equipment_group_id",
        "группа_оборудования",
    }
    header_row = 0

    for try_row in range(min(25, len(df_preview))):
        row_cells = df_preview.iloc[try_row]
        normalized_cells = set()
        for c in row_cells:
            if pd.notna(c) and str(c).strip():
                norm = _normalize_column_name(str(c))
                if norm:
                    normalized_cells.add(norm)
        if normalized_cells & header_markers:
            header_row = try_row
            break

    df = xls.parse(sheet_name, header=header_row)
    df = df.dropna(how="all")
    return df, header_row


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
    "dem", "nt", "grcode", "stname",
    "opesname", "note",
]
# Маппинг MachineFuelParam: столбец Excel (после алиасов) -> поле таблицы.
# Excel: topl_agr_numb1120->machine_numb1120, topl_agr_number->machine_number и т.д.
MACHINE_FUEL_PARAM_COLUMN_ALIASES: dict[str, list[str]] = {
    "numb1120": ["machine_numb1120"],
    "numb": ["machine_numb"],
    "stnumb": ["machine_number"],
    "yearin": ["machine_yearin"],
    "dem": ["machine_dem"],
    "nt": ["machine_nt"],
    "grcode": ["machine_grcode"],
    "stname": ["machine_station_name"],
    "opesname": ["machine_opesname"],
    "note": ["machine_note"],
}

# Маппинг: колонка Excel (после алиасов ge_*) -> поле модели EquipmentGroup
# topl_name -> ge_name_ext используется для name и name_ext
EQUIPMENT_GROUP_COLUMN_TO_FIELD: dict[str, str] = {
    "ge_name_ext": "name_ext",
    "ge_niv": "niv",
    "ge_comp": "comp",
    "ge_main": "main",
    "ge_numb": "numb",
    "ge_ordnumb": "ordnumb",
    "ge_d": "d",
    "ge_r": "r",
    "ge_forem": "forem",
    "ge_vedomstvo": "vedomstvo",
    "ge_obl": "obl",
    "ge_dep": "dep",
    "ge_oes": "oes",
    "ge_er": "er",
    "ge_fo": "fo",
    "ge_tm": "tm",
    "ge_n1": "n1",
    "ge_n2": "n2",
    "ge_p1": "p1",
    "ge_p2": "p2",
    "ge_addr": "addr",
    "ge_note": "note",
    "ge_codegor": "codegor",
    "ge_be": "be",
    "ge_gk": "gk",
    "ge_gkf": "gkf",
}

# Обратный маппинг: поле модели -> колонки для поиска (ge_* после алиасов)
EQUIPMENT_GROUP_FIELD_TO_COLUMNS: dict[str, list[str]] = {}
for _col, _fld in EQUIPMENT_GROUP_COLUMN_TO_FIELD.items():
    EQUIPMENT_GROUP_FIELD_TO_COLUMNS.setdefault(_fld, []).append(_col)
for _fld in EQUIPMENT_GROUP_UPDATE_FIELDS:
    lst = EQUIPMENT_GROUP_FIELD_TO_COLUMNS.setdefault(_fld, [])
    if _fld not in lst:
        lst.append(_fld)
# name и name_ext оба берут значение из topl_name (ge_name_ext)
EQUIPMENT_GROUP_FIELD_TO_COLUMNS.setdefault("name", []).insert(0, "ge_name_ext")
# numb только из ge_numb (источники: topl_NUMB, numb1120, «Код станции (numb)» — см. _coalesce_ge_numb_source_columns)
EQUIPMENT_GROUP_FIELD_TO_COLUMNS["numb"] = ["ge_numb"]
MACHINE_FUEL_PARAM_INTEGER_FIELDS = frozenset([
    "numb1120", "numb", "stnumb", "yearin",
    "dem", "nt", "grcode",
])

# Поля, значения которых Excel часто отдает как float (1.0) — нормализуем в целочисленную строку ("1")
EQUIPMENT_GROUP_SET_INTEGER_FIELDS = frozenset([
    "comp", "niv", "main", "numb", "ordnumb", "d", "r", "forem",
    "vedomstvo", "obl", "dep", "oes", "er", "fo",
    "tm", "n1", "n2", "p1", "p2",
    "codegor", "be", "gk", "gkf",
])

# Строгие integer-поля: нечисловые строки не записываем (иначе psycopg2.InvalidTextRepresentation)
EQUIPMENT_GROUP_STRICT_INTEGER_FIELDS = frozenset([
    "comp", "niv", "main", "numb", "d", "r", "forem",
    "vedomstvo", "obl", "dep", "oes", "er", "fo",
    "codegor", "be", "gk", "gkf",
])


def _import_cell_is_empty(value) -> bool:
    """Пустая ячейка для слияния колонок id_station / id_machine (в т.ч. «—» из экспорта)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return True
    s = str(value).strip()
    return s == "" or s in ("—", "-", "–", "−")


def _collect_rows_with_empty_station_and_machine_ids(df: pd.DataFrame) -> set[int | float]:
    """
    Возвращает индексы строк, где в строке (после алиасов колонок) одновременно пусты
    id_station и id_machine и которые не являются строками standalone-котельных.

    Такие строки полностью исключаются из обработки (нет построчного протягивания значений).
    Исключение — «Котельные»: для них обе колонки ID могут быть пустыми по дизайну, и такие
    строки должны обрабатываться отдельным шагом импорта standalone-групп.
    """
    if "id_station" not in df.columns and "id_machine" not in df.columns:
        return set()

    skipped_indexes: set[int | float] = set()
    for index, row in df.iterrows():
        station_value = _extract_cell_value(row, "id_station") if "id_station" in df.columns else None
        machine_value = _extract_cell_value(row, "id_machine") if "id_machine" in df.columns else None
        if not (
            _import_cell_is_empty(station_value) and _import_cell_is_empty(machine_value)
        ):
            continue

        group_text = _get_equipment_group_for_kotelnye(row, df.columns)
        if group_text and _is_kotelnye_group(_clean_name(group_text)):
            continue

        if _import_cell_is_empty(station_value) and _import_cell_is_empty(machine_value):
            skipped_indexes.add(index)
    return skipped_indexes


def _coalesce_duplicate_station_machine_id_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Если одновременно есть каноническое имя (id_station) и русский заголовок (ID станции),
    шаблон часто оставляет пустой id_station — тогда переименование второй колонки
    блокировалось already_canonical и данные терялись при cols_to_keep.
    Объединяем значения в одну колонку с каноническим именем.
    """
    def _find_col_by_norm(target_norm: str) -> str | None:
        for c in df.columns:
            if _normalize_column_name(str(c)) == target_norm:
                return str(c)
        return None

    pairs = (
        ("id_station", "id_станции"),
        ("id_machine", "id_агрегата"),
    )
    for canonical, ru_norm in pairs:
        ru_col = _find_col_by_norm(ru_norm)
        if not ru_col:
            continue
        if canonical in df.columns and ru_col != canonical:
            s_en = df[canonical]
            s_ru = df[ru_col]
            merged = []
            for i in range(len(df)):
                a, b = s_en.iloc[i], s_ru.iloc[i]
                merged.append(b if _import_cell_is_empty(a) and not _import_cell_is_empty(b) else a)
            df[canonical] = merged
            df.drop(columns=[ru_col], inplace=True)
        elif canonical not in df.columns:
            df.rename(columns={ru_col: canonical}, inplace=True)
    return df


def _coalesce_equipment_group_name_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Сливаем в equipment_group только дубликаты equipment_group / ge_equipment_group (старые шаблоны).
    Столбец «Группа оборудования» не сливается: он нужен отдельно для распознавания строк «Котельные».
    """
    norms_en = frozenset({"equipment_group", "ge_equipment_group"})
    norm_ru = "группа_оборудования"
    cols_en = [c for c in df.columns if _normalize_column_name(str(c)) in norms_en]
    cols_ru = [c for c in df.columns if _normalize_column_name(str(c)) == norm_ru]

    if len(cols_ru) > 1:
        merged_ru = df[cols_ru[0]].copy()
        for other in cols_ru[1:]:
            s_o = df[other]
            for i in range(len(df)):
                a, b = merged_ru.iloc[i], s_o.iloc[i]
                if _import_cell_is_empty(a) and not _import_cell_is_empty(b):
                    merged_ru.iloc[i] = b
                elif isinstance(a, str) and isinstance(b, str) and (not a.strip()) and b.strip():
                    merged_ru.iloc[i] = b
        df.drop(columns=cols_ru, inplace=True)
        df[cols_ru[0]] = merged_ru
        cols_ru = [cols_ru[0]]

    if len(cols_en) <= 1:
        if len(cols_en) == 1 and _normalize_column_name(str(cols_en[0])) != "equipment_group":
            df.rename(columns={cols_en[0]: "equipment_group"}, inplace=True)
        return df
    merged = df[cols_en[0]].copy()
    for other in cols_en[1:]:
        s_o = df[other]
        for i in range(len(df)):
            a, b = merged.iloc[i], s_o.iloc[i]
            if _import_cell_is_empty(a) and not _import_cell_is_empty(b):
                merged.iloc[i] = b
            elif isinstance(a, str) and isinstance(b, str) and (not a.strip()) and b.strip():
                merged.iloc[i] = b
    df.drop(columns=cols_en, inplace=True)
    df["equipment_group"] = merged
    return df


def _coalesce_ge_numb_source_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    numb1120, topl_NUMB и «Код станции (numb)» (экспорт /fuel/stations_equipment_groups) → одна колонка ge_numb.

    В экспорте нет topl_NUMB: numb дублируется в numb1120 и в «Код станции (numb)»; без слияния импорт
    не получал ge_numb и шаг 4.2 не сопоставлял строки с EquipmentGroup.numb в БД.
    """
    norms = _GE_NUMB_SOURCE_COLUMN_NORMALS | {"ge_numb"}
    cols = [c for c in df.columns if _normalize_column_name(str(c)) in norms]
    if len(cols) == 0:
        return df
    if len(cols) == 1:
        if _normalize_column_name(str(cols[0])) != "ge_numb":
            df.rename(columns={cols[0]: "ge_numb"}, inplace=True)
        return df
    merged = df[cols[0]].copy()
    for other in cols[1:]:
        s_o = df[other]
        for i in range(len(df)):
            a, b = merged.iloc[i], s_o.iloc[i]
            if _import_cell_is_empty(a) and not _import_cell_is_empty(b):
                merged.iloc[i] = b
            elif isinstance(a, str) and isinstance(b, str) and (not a.strip()) and b.strip():
                merged.iloc[i] = b
    df.drop(columns=cols, inplace=True)
    df["ge_numb"] = merged
    return df


def _apply_column_aliases(df: pd.DataFrame) -> pd.DataFrame:
    """Переименовывает колонки по алиасам для id_machine, equipment_group и полей EquipmentGroupSet."""
    df = _coalesce_duplicate_station_machine_id_columns(df)
    df = _coalesce_equipment_group_name_columns(df)
    df = _coalesce_ge_numb_source_columns(df)
    alias_to_canonical: dict[str, str] = {}

    def add_aliases(canonical: str, aliases: list[str]) -> None:
        for a in aliases:
            alias_to_canonical[_normalize_column_name(a)] = canonical

    add_aliases("id_machine", ["id_machine", "ID агрегата"])
    add_aliases("id_station", ["id_station", "ID станции"])
    add_aliases("equipment_group_id", ["equipment_group_id", "id_equipment_group", "ID группы оборудования"])
    add_aliases("ge_name_ext", ["topl_name", "name_ext"])
    add_aliases("ge_niv", ["topl_niv"])
    add_aliases("ge_comp", ["topl_comp"])
    add_aliases("ge_main", ["topl_main"])
    add_aliases("ge_numb", ["topl_numb"])
    add_aliases("ge_ordnumb", ["topl_ordnumb"])
    add_aliases("ge_d", ["topl_d"])
    add_aliases("ge_r", ["topl_r"])
    add_aliases("ge_forem", ["topl_forem"])
    add_aliases(
        GE_GRUPPA_OBORUDOVANIYA_COLUMN,
        ["\u0413\u0440\u0443\u043f\u043f\u0430 \u043e\u0431\u043e\u0440\u0443\u0434\u043e\u0432\u0430\u043d\u0438\u044f"],
    )
    add_aliases("ge_obl", ["topl_obl"])
    add_aliases("ge_oes", ["topl_oes"])
    add_aliases("ge_vedomstvo", ["topl_vedomstvo"])
    add_aliases("ge_dep", ["topl_dep"])
    add_aliases("ge_er", ["topl_er"])
    add_aliases("ge_fo", ["topl_fo"])
    add_aliases("ge_tm", ["topl_tm"])
    add_aliases("ge_n1", ["topl_n1"])
    add_aliases("ge_n2", ["topl_n2"])
    add_aliases("ge_p1", ["topl_p1"])
    add_aliases("ge_p2", ["topl_p2"])
    add_aliases("ge_addr", ["topl_addr"])
    add_aliases("ge_note", ["topl_note"])
    add_aliases("ge_codegor", ["topl_codegor"])
    add_aliases("ge_be", ["topl_be"])
    add_aliases("ge_gk", ["topl_gk"])
    add_aliases("ge_gkf", ["topl_gkf"])
    add_aliases("machine_numb1120", ["topl_agr_numb1120"])
    add_aliases("machine_numb", ["topl_agr_numb"])
    add_aliases("machine_number", ["topl_agr_number"])
    add_aliases("machine_yearin", ["topl_agr_yearin"])
    add_aliases("machine_dem", ["topl_agr_dem"])
    add_aliases("machine_nt", ["topl_agr_nt"])
    add_aliases("machine_grcode", ["topl_agr_grcode"])
    add_aliases("machine_station_name", ["topl_agr_station_name"])
    add_aliases("machine_opesname", ["topl_agr_opesname"])
    add_aliases("machine_note", ["topl_agr_note"])

    rename_map: dict[str, str] = {}
    for col in df.columns:
        normalized = _normalize_column_name(col)
        canonical = alias_to_canonical.get(normalized)
        if not canonical or canonical == col:
            continue
        # Не переименовываем, если целевое имя уже есть как столбец или уже занято другим переименованием
        if canonical in df.columns or canonical in rename_map.values():
            continue
        rename_map[col] = canonical

    if rename_map:
        df = df.rename(columns=rename_map)
    return df


# Тип группы оборудования для сопоставления со справочником — только столбец equipment_group.
# «Котельные» смотрят только GE_GRUPPA_OBORUDOVANIYA_COLUMN — см. _get_equipment_group_for_kotelnye.
EQUIPMENT_GROUP_COLUMN_NAMES = ("equipment_group",)

# Разрешённые колонки после алиасов (лишние — type, Unnamed и т.д. — отбрасываются)
ALLOWED_IMPORT_COLUMNS = frozenset([
    "equipment_group_id", "id_station", "id_machine", "ge_name_ext", "ge_comp", "ge_niv", "ge_main",
    "ge_numb", "ge_ordnumb", "ge_d", "ge_r", "ge_forem", "equipment_group",
    GE_GRUPPA_OBORUDOVANIYA_COLUMN,
    "ge_vedomstvo", "ge_obl",
    "ge_dep", "ge_oes", "ge_er", "ge_fo", "ge_tm", "ge_n1", "ge_n2", "ge_p1", "ge_p2", "ge_addr",
    "ge_note", "ge_codegor", "ge_be", "ge_gk", "ge_gkf",
    "machine_numb1120", "machine_numb", "machine_number", "machine_yearin", "machine_dem",
    "machine_nt", "machine_grcode", "machine_station_name", "machine_opesname", "machine_note",
])

# Значение "Котельные" — группа без привязки к станции (EquipmentGroup напрямую)
KOTELNYE_GROUP_NAME = "Котельные"
NEW_EQUIPMENT_GROUP_SUFFIX = " (нов)"


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


def _generate_stable_external_code_equipment_group(
    station_external_code: str | None,
    type_ref_uuid: str | None,
    numb: int | str | None,
    group_variant: str | None = None,
) -> str:
    """
    Генерирует стабильный external_code для группы оборудования при импорте из Excel.
    Одинаковый ключ для всех версий БД обеспечивает одинаковый external_code.
    """
    key = (
        f"import|equipment_group|station|{station_external_code or ''}"
        f"|type|{type_ref_uuid or ''}|numb|{numb or ''}"
        f"|variant|{group_variant or 'base'}"
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def _compose_equipment_group_name(
    station: Station | None,
    group_type: EquipmentGroupType | None,
    *,
    is_new_group: bool,
) -> str | None:
    if not station or not station.name or not group_type or not group_type.name:
        return None
    base_name = f"{station.name} ({group_type.name})"
    if is_new_group:
        return f"{base_name}{NEW_EQUIPMENT_GROUP_SUFFIX}"
    return base_name


def _year_has_plan_feature(year_number: int | None, version_id: int | None) -> bool:
    """Проверяет, что год в справочнике Years помечен признаком «план»."""
    if year_number is None:
        return False
    from app.common.services.get_services.years.year_feature_services import (
        get_year_feature_dict_for_version,
    )

    year_features = get_year_feature_dict_for_version(version_id)
    return str(year_features.get(year_number) or "").strip().lower() == "план"


def _machine_requires_new_equipment_group(
    machine: Machine | None,
    version_id: int | None,
) -> bool:
    """
    Новый отдельный fuel EquipmentGroup нужен, если у агрегата ожидаемый ввод
    попадает в год с признаком «план».
    """
    if machine is None:
        return False
    year_number = getattr(machine, "date_exploitation_expected", None)
    if year_number is None:
        return False
    try:
        year_number = int(year_number)
    except (TypeError, ValueError):
        return False
    return _year_has_plan_feature(year_number, version_id)


def _find_equipment_group_by_external_code(
    external_code: str | None,
    version_id: int | None,
) -> EquipmentGroup | None:
    """Ищет EquipmentGroup по стабильному external_code в пределах версии БД."""
    if not external_code:
        return None

    query = EquipmentGroup.query.filter(EquipmentGroup.external_code == external_code)
    if version_id is None:
        query = query.filter(EquipmentGroup.database_version_id.is_(None))
    else:
        query = query.filter(EquipmentGroup.database_version_id == version_id)
    return query.order_by(EquipmentGroup.id.asc()).first()


def _equipment_group_matches_station_link(
    equipment_group_id: int,
    station_id: int,
    equipment_group_type_id: int,
    version_id: int | None,
    *,
    allow_cross_station_merge: bool = False,
    is_new_group: bool | None = None,
) -> bool:
    """
    Проверяет, что EquipmentGroup уже связана именно с той станцией/типом/версией,
    для которых сейчас обрабатывается строка импорта.

    Если в Excel попал equipment_group_id от одноименной станции из другого региона,
    слепое переиспользование этой группы создаёт вторую связь EquipmentGroupSet и
    переносит субъект/РЭС в карточке группы на "чужую" станцию.

    Для сценария ручного объединения нескольких станций в одну группу разрешаем
    принять equipment_group_id из Excel и дозавести недостающую связь на текущую
    станцию, если у группы уже есть совместимая связь того же типа и версии.
    """
    exact_query = (
        db.session.query(EquipmentGroupSet.id)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSetStation.id == EquipmentGroupSet.equipment_group_set_station_id,
        )
        .filter(
            EquipmentGroupSet.equipment_group_id == equipment_group_id,
            EquipmentGroupSetStation.station_id == station_id,
            EquipmentGroupSetStation.equipment_group_type_id == equipment_group_type_id,
        )
    )
    if version_id is None:
        exact_query = exact_query.filter(EquipmentGroupSetStation.database_version_id.is_(None))
    else:
        exact_query = exact_query.filter(EquipmentGroupSetStation.database_version_id == version_id)
    if exact_query.first() is not None:
        return True

    if not allow_cross_station_merge:
        return False

    compatible_query = (
        db.session.query(EquipmentGroupSet.id)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSetStation.id == EquipmentGroupSet.equipment_group_set_station_id,
        )
        .filter(
            EquipmentGroupSet.equipment_group_id == equipment_group_id,
            EquipmentGroupSetStation.equipment_group_type_id == equipment_group_type_id,
        )
    )
    if version_id is None:
        compatible_query = compatible_query.filter(
            EquipmentGroupSetStation.database_version_id.is_(None)
        )
    else:
        compatible_query = compatible_query.filter(
            EquipmentGroupSetStation.database_version_id == version_id
        )
    if compatible_query.first() is None:
        return False

    if is_new_group is None:
        return True

    equipment_group = EquipmentGroup.query.get(equipment_group_id)
    if equipment_group is None:
        return False

    group_name = (getattr(equipment_group, "name", None) or "").strip()
    has_new_suffix = group_name.endswith(NEW_EQUIPMENT_GROUP_SUFFIX)
    return has_new_suffix if is_new_group else not has_new_suffix


def _generate_stable_external_code_standalone_equipment_group(
    name: str | None,
    numb: int | str | None,
) -> str:
    """
    Генерирует стабильный external_code для standalone-группы (напр. «Котельные») при импорте.
    """
    key = f"import|standalone|equipment_group|name|{name or ''}|numb|{numb or ''}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def _standalone_equipment_group_query(
    db_version_id: int | None,
):
    """
    Базовый запрос standalone-групп: без station-bound связей.

    Группы с EquipmentGroupSet -> EquipmentGroupSetStation, у которых
    `station_id = NULL`, продолжаем считать standalone-котельными.
    """
    station_linked_subq = (
        db.session.query(EquipmentGroupSet.equipment_group_id)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSet.equipment_group_set_station_id == EquipmentGroupSetStation.id,
        )
        .filter(EquipmentGroupSetStation.station_id.isnot(None))
        .distinct()
    )
    query = db.session.query(EquipmentGroup).filter(
        ~EquipmentGroup.id.in_(station_linked_subq)
    )
    if db_version_id is not None:
        query = query.filter(EquipmentGroup.database_version_id == db_version_id)
    else:
        query = query.filter(EquipmentGroup.database_version_id.is_(None))
    return query


def _find_or_create_standalone_equipment_group(
    group_name: str,
    db_version_id: int | None,
    valid_version_ids: set[int],
    numb: int | None = None,
) -> tuple[EquipmentGroup, bool]:
    """
    Ищет standalone EquipmentGroup без реальных station-bound привязок по
    name или (database_version_id, numb).
    Если не найдена — создает и возвращает. Возвращает (eg, was_created).
    При numb: сначала ищет по (database_version_id, numb) для предотвращения дублей.
    """
    if numb is not None and db_version_id is not None:
        eg_by_numb = (
            _standalone_equipment_group_query(db_version_id)
            .filter(EquipmentGroup.numb == str(numb))  # numb в БД может быть VARCHAR
            .first()
        )
        if eg_by_numb:
            return eg_by_numb, False

    name_norm = (group_name or "").strip().lower().replace("\xa0", " ").replace("\u00a0", " ")
    if not name_norm:
        name_norm = KOTELNYE_GROUP_NAME.lower()

    eg_query = _standalone_equipment_group_query(db_version_id).filter(
        func.lower(func.trim(func.replace(EquipmentGroup.name, "\xa0", " "))) == name_norm,
    )
    eg = eg_query.first()

    if eg:
        return eg, False

    eg = EquipmentGroup(name=group_name.strip() or KOTELNYE_GROUP_NAME)
    if numb is not None:
        eg.numb = str(numb)
    eg.external_code = _generate_stable_external_code_standalone_equipment_group(
        group_name.strip() or KOTELNYE_GROUP_NAME, numb
    )
    if db_version_id is not None and db_version_id in valid_version_ids:
        eg.database_version_id = db_version_id
    else:
        set_db_version_on_create(eg)
    db.session.add(eg)
    db.session.flush()
    return eg, True


def _find_kotelnaya_equipment_group_type_for_version(
    db_version_id: int | None,
) -> EquipmentGroupType | None:
    """Ищет refdata-тип группы оборудования `котельная` в заданной версии БД."""
    return _find_equipment_group_by_name_or_mapping("котельная", db_version_id)


def _find_or_create_kotelnaya_type_station_link(
    db_version_id: int | None,
    valid_version_ids: set[int],
) -> tuple[EquipmentGroupSetStation | None, bool]:
    """
    Обеспечивает наличие записи в gs_fue_equipment_group_type_stations для
    standalone-котельной: station_id = NULL, equipment_group_type_id = `котельная`.
    """
    kotelnaya_type = _find_kotelnaya_equipment_group_type_for_version(db_version_id)
    if kotelnaya_type is None:
        return None, False

    link_query = EquipmentGroupSetStation.query.filter(
        EquipmentGroupSetStation.station_id.is_(None),
        EquipmentGroupSetStation.equipment_group_type_id == kotelnaya_type.id,
    )
    if db_version_id is not None:
        link_query = link_query.filter(
            EquipmentGroupSetStation.database_version_id == db_version_id
        )
    else:
        link_query = link_query.filter(
            EquipmentGroupSetStation.database_version_id.is_(None)
        )
    link = link_query.order_by(EquipmentGroupSetStation.id.asc()).first()
    if link is not None:
        return link, False

    link = EquipmentGroupSetStation(
        station_id=None,
        equipment_group_type_id=kotelnaya_type.id,
    )
    if db_version_id is not None and db_version_id in valid_version_ids:
        link.database_version_id = db_version_id
    else:
        set_db_version_on_create(link)
    db.session.add(link)
    db.session.flush()
    return link, True


def _get_equipment_group_from_row(row, df_columns) -> str | None:
    """Извлекает тип группы оборудования только из столбца equipment_group."""
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
    Для строк «Котельные»: текст берётся только из столбца Excel «Группа оборудования»
    (после алиасов — GE_GRUPPA_OBORUDOVANIYA_COLUMN), не из equipment_group.
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

    if GE_GRUPPA_OBORUDOVANIYA_COLUMN not in df_columns:
        return None
    val = _extract_cell_value(row, GE_GRUPPA_OBORUDOVANIYA_COLUMN)
    return _check_val(val)


def _extract_cell_value(row, field: str):
    """
    Извлекает скалярное значение из ячейки. При дублировании столбцов row[field]
    возвращает Series — берем первый непустой элемент.
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
    Остальное — как _safe_str (для строковых колонок ordnumb, tm, n1, n2, p1, p2).
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


def _safe_str_int_strict(value) -> str | None:
    """
    Для integer-колонок: возвращает целочисленную строку или None.
    Нечисловые строки (напр. названия станций) не записываются — иначе psycopg2.InvalidTextRepresentation.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        if isinstance(value, int):
            return str(value)
        return None  # нецелое float для integer-колонки
    s = str(value).strip()
    if not s:
        return None
    try:
        f = float(s)
        if f.is_integer():
            return str(int(f))
    except ValueError:
        return None
    return None


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


def _normalize_eg_numb_from_db(equipment_group: EquipmentGroup | None) -> str | None:
    """Тот же вид, что numb из Excel в шаге 4.2 (_safe_str_int_strict)."""
    if not equipment_group:
        return None
    return _safe_str_int_strict(getattr(equipment_group, "numb", None))


def _extract_equipment_group_numb_from_import_row(row, df_columns) -> str | None:
    """Numb только из столбца topl_NUMB в Excel (после алиасов — ge_numb)."""
    if "ge_numb" not in df_columns:
        return None
    raw = _extract_cell_value(row, "ge_numb")
    if raw is None:
        return None
    return _safe_str_int_strict(raw)


def _find_equipment_group_by_numb_for_station_external_code(
    numb: int,
    station_id: int,
    equipment_group_type_id: int,
    version_id: int | None,
) -> EquipmentGroup | None:
    """
    Ищет EquipmentGroup с заданным numb, уже связанную через EquipmentGroupSet
    со станцией из того же «семейства», что и station_id (см. _get_station_family_for_import),
    и только для того же типа группы оборудования.

    Глобальный поиск только по numb и external_code давал .first() по «любой» станции
    с тем же кодом — в т.ч. одноимённые станции в разных субъектах. Ограничение по
    family_ids сохраняет перенос между версиями одной станции и не подтягивает группу
    «соседней» станции с тем же external_code. Дополнительная фильтрация по
    equipment_group_type_id не дает склеивать в одну EquipmentGroup разные типы
    оборудования с одинаковым numb на одной станции.
    """
    station = Station.query.get(station_id)
    if not station:
        return None
    ext = (station.external_code or "").strip()
    if not ext:
        return None
    family = _get_station_family_for_import(station)
    family_ids = [s.id for s in family] if family else [station_id]
    q = (
        db.session.query(EquipmentGroup)
        .join(EquipmentGroupSet, EquipmentGroupSet.equipment_group_id == EquipmentGroup.id)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSetStation.id == EquipmentGroupSet.equipment_group_set_station_id,
        )
        .join(Station, Station.id == EquipmentGroupSetStation.station_id)
        .filter(
            EquipmentGroup.numb == str(numb),
            Station.external_code == ext,
            Station.id.in_(family_ids),
            EquipmentGroupSetStation.equipment_group_type_id == equipment_group_type_id,
        )
    )
    if version_id is not None:
        q = q.filter(EquipmentGroup.database_version_id == version_id)
    else:
        q = q.filter(EquipmentGroup.database_version_id.is_(None))

    candidates = q.order_by(EquipmentGroup.id.asc()).all()
    for candidate in candidates:
        linked_type_ids = {
            linked.equipment_group_set_station.equipment_group_type_id
            for linked in getattr(candidate, "equipment_group_links_v2", [])
            if getattr(linked, "equipment_group_set_station", None) is not None
        }
        # Автоподбор по numb допустим только для групп одного типа.
        if linked_type_ids == {equipment_group_type_id}:
            return candidate
    return None


def _find_equipment_groups_by_numb_for_station_external_code(
    numb: int | str,
    station_id: int,
    version_id: int | None,
    equipment_group_type_id: int | None = None,
) -> list[EquipmentGroup]:
    """
    Ищет все EquipmentGroup с заданным numb, уже связанные со станцией из того же
    семейства, что и station_id. При необходимости дополнительно ограничивает выборку
    конкретным типом группы оборудования.
    """
    station = Station.query.get(station_id)
    if not station:
        return []
    ext = (station.external_code or "").strip()
    if not ext:
        return []
    family = _get_station_family_for_import(station)
    family_ids = [s.id for s in family] if family else [station_id]
    q = (
        db.session.query(EquipmentGroup)
        .join(EquipmentGroupSet, EquipmentGroupSet.equipment_group_id == EquipmentGroup.id)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSetStation.id == EquipmentGroupSet.equipment_group_set_station_id,
        )
        .join(Station, Station.id == EquipmentGroupSetStation.station_id)
        .filter(
            EquipmentGroup.numb == str(numb),
            Station.external_code == ext,
            Station.id.in_(family_ids),
        )
    )
    if equipment_group_type_id is not None:
        q = q.filter(EquipmentGroupSetStation.equipment_group_type_id == equipment_group_type_id)
    if version_id is not None:
        q = q.filter(EquipmentGroup.database_version_id == version_id)
    else:
        q = q.filter(EquipmentGroup.database_version_id.is_(None))

    seen_ids: set[int] = set()
    result: list[EquipmentGroup] = []
    for candidate in q.order_by(EquipmentGroup.id.asc()).all():
        if candidate.id in seen_ids:
            continue
        seen_ids.add(candidate.id)
        result.append(candidate)
    return result


def _normalize_equipment_group_text_for_match(value) -> str:
    if value is None:
        return ""
    s = _safe_str(value)
    if not s:
        return ""
    cleaned = _clean_name(s)
    return _normalize_equipment_group_name(cleaned)


def _filter_equipment_groups_by_topl_name(
    candidates: list[EquipmentGroup],
    topl_name_value: str | None,
) -> list[EquipmentGroup]:
    """
    При неоднозначном совпадении по station+numb пытается сузить выборку по topl_name,
    сравнивая его с name_ext / name существующей группы.
    """
    target = _normalize_equipment_group_text_for_match(topl_name_value)
    if not target:
        return candidates
    matched = [
        candidate
        for candidate in candidates
        if target in {
            _normalize_equipment_group_text_for_match(getattr(candidate, "name_ext", None)),
            _normalize_equipment_group_text_for_match(getattr(candidate, "name", None)),
        }
    ]
    return matched or candidates


def _normalized_station_identity_name(station: Station | None) -> str:
    if not station:
        return ""
    for value in (
        getattr(station, "name", None),
        getattr(station, "name_combined", None),
        getattr(station, "name_so", None),
        getattr(station, "name_archive", None),
    ):
        cleaned = _clean_name(value) if value else ""
        if cleaned:
            return cleaned.lower()
    return ""


def _get_station_family_for_import(station: Station | None) -> list[Station]:
    """
    Возвращает "семейство" одной станции для переноса между версиями.

    Ранее логика брала все станции с тем же external_code, из-за чего станции
    из разных субъектов с одинаковым кодом считались одной и той же станцией.
    Это приводило к созданию пустых лишних групп и переносу параметров не туда.

    Сиблинг с пустым субъектом/РЭС при заполненном субъекте/РЭС у источника
    отбрасывается, если нормализованное имя не совпадает (иначе в семью попадали
    одноимённые станции в разных регионах).
    """
    if not station or not station.external_code:
        return []

    siblings = Station.query.filter(Station.external_code == station.external_code).all()
    if not siblings:
        return []

    source_rd_id = getattr(station, "id_regional_district", None)
    source_res_id = getattr(station, "id_regional_energy_system", None)
    source_name = _normalized_station_identity_name(station)
    matched = []
    for sibling in siblings:
        sibling_rd_id = getattr(sibling, "id_regional_district", None)
        sibling_res_id = getattr(sibling, "id_regional_energy_system", None)
        sibling_name = _normalized_station_identity_name(sibling)

        if source_rd_id is not None and sibling_rd_id is not None and sibling_rd_id != source_rd_id:
            continue
        # У субъекта задано, у «сиблинга» нет — не смешиваем разные одноимённые станции
        if source_rd_id is not None and sibling_rd_id is None and source_name:
            if sibling_name and sibling_name != source_name:
                continue

        if source_res_id is not None and sibling_res_id is not None and sibling_res_id != source_res_id:
            continue
        if source_res_id is not None and sibling_res_id is None and source_name:
            if sibling_name and sibling_name != source_name:
                continue

        if source_rd_id is None and source_name:
            if sibling_name and sibling_name != source_name:
                continue
        matched.append(sibling)

    return matched or [station]


def _machine_import_sort_key(machine: Machine | None) -> tuple:
    if machine is None:
        return (1, "", "", 0)

    machine_number = (getattr(machine, "machine_number", None) or "").strip()
    machine_name = (getattr(machine, "machine_name", None) or "").strip().lower()
    numeric_part = "".join(ch for ch in machine_number if ch.isdigit())
    if numeric_part:
        try:
            return (0, int(numeric_part), machine_number.lower(), machine_name, getattr(machine, "id", 0) or 0)
        except (TypeError, ValueError):
            pass
    return (1, machine_number.lower(), machine_name, getattr(machine, "id", 0) or 0)


def _normalize_machine_number_for_import(value: str | None) -> str:
    return " ".join(
        str(value or "")
        .replace("–", "-")
        .replace("—", "-")
        .replace("−", "-")
        .split()
    ).strip().lower()


def _normalize_machine_name_for_import(value: str | None) -> str:
    return " ".join(str(value or "").split()).strip().lower()


def _get_station_machines_for_import(
    station_id: int | None,
    company_identity_keys: set[str] | None = None,
) -> list[Machine]:
    if station_id is None:
        return []
    machines = Machine.query.filter(Machine.id_station == station_id).all()
    if company_identity_keys:
        filtered_machines = []
        for machine in machines:
            company_key = _get_company_identity_key_for_import(getattr(machine, "id_gen_company", None))
            if company_key and company_key in company_identity_keys:
                filtered_machines.append(machine)
        if filtered_machines:
            machines = filtered_machines
    return sorted(machines, key=_machine_import_sort_key)


def _normalize_company_identity_for_import(value: str | None) -> str:
    return " ".join(str(value or "").split()).strip().lower()


def _extract_machine_gtp_codes_for_import(machine_name: str | None) -> tuple[str, ...]:
    if not machine_name:
        return ()
    codes = re.findall(r"код\s+гтп\s+([A-Za-zА-Яа-я0-9_-]+)", str(machine_name), flags=re.IGNORECASE)
    normalized_codes = sorted({" ".join(str(code).split()).strip().upper() for code in codes if str(code).strip()})
    return tuple(normalized_codes)


def _get_company_identity_key_for_import(company_id: int | None) -> str:
    if company_id is None:
        return ""
    company = db.session.get(GenCompany, company_id)
    if company is None:
        return ""
    company_key = (getattr(company, "ref_uuid", None) or "").strip()
    if not company_key:
        company_key = _normalize_company_identity_for_import(getattr(company, "name", None))
    return company_key


def _get_station_machine_company_ids_for_import(station_id: int | None) -> set[str]:
    if station_id is None:
        return set()
    rows = (
        db.session.query(Machine.id_gen_company)
        .filter(Machine.id_station == station_id, Machine.id_gen_company.isnot(None))
        .distinct()
        .all()
    )
    company_keys: set[str] = set()
    for (company_id,) in rows:
        if company_id is None:
            continue
        company_key = _get_company_identity_key_for_import(company_id)
        if company_key:
            company_keys.add(company_key)
    return company_keys


def _get_machine_company_identity_keys_for_import(
    machine: Machine | None,
    *,
    use_external_code_hints: bool = True,
) -> set[str]:
    if machine is None:
        return set()

    machine_company_key = _get_company_identity_key_for_import(getattr(machine, "id_gen_company", None))
    if machine_company_key:
        return {machine_company_key}

    if not use_external_code_hints:
        return set()
    machine_external_code = (getattr(machine, "external_code", None) or "").strip()
    if not machine_external_code:
        return set()

    company_keys: set[str] = set()
    same_code_machines = Machine.query.filter(Machine.external_code == machine_external_code).all()
    for candidate in same_code_machines:
        candidate_company_key = _get_company_identity_key_for_import(getattr(candidate, "id_gen_company", None))
        if candidate_company_key:
            company_keys.add(candidate_company_key)
    return company_keys


def _get_relaxed_station_family_for_import(station: Station | None) -> list[Station]:
    if not station or not getattr(station, "external_code", None):
        return []

    anchor_name = _normalized_station_identity_name(station)
    relaxed_station_family = []
    for sibling_station in Station.query.filter(
        Station.external_code == station.external_code
    ).all():
        sibling_name = _normalized_station_identity_name(sibling_station)
        if anchor_name and sibling_name and sibling_name != anchor_name:
            continue
        relaxed_station_family.append(sibling_station)
    return relaxed_station_family


def _match_station_machine_by_gtp_codes_for_import(
    station_machines: list[Machine],
    anchor_gtp_codes: tuple[str, ...],
) -> Machine | None:
    if not anchor_gtp_codes:
        return None
    matched = [
        item
        for item in station_machines
        if _extract_machine_gtp_codes_for_import(getattr(item, "machine_name", None)) == anchor_gtp_codes
    ]
    if len(matched) == 1:
        return matched[0]
    return None


def _match_station_machine_by_signature_for_import(
    station_machines: list[Machine],
    machine: Machine | None,
) -> Machine | None:
    if machine is None:
        return None

    anchor_number = _normalize_machine_number_for_import(getattr(machine, "machine_number", None))
    anchor_name = _normalize_machine_name_for_import(getattr(machine, "machine_name", None))
    anchor_year = getattr(machine, "date_exploitation", None)

    def _filter_matches(*, require_number: bool, require_name: bool, require_year: bool) -> list[Machine]:
        matched = []
        for item in station_machines:
            if require_number and _normalize_machine_number_for_import(getattr(item, "machine_number", None)) != anchor_number:
                continue
            if require_name and _normalize_machine_name_for_import(getattr(item, "machine_name", None)) != anchor_name:
                continue
            if require_year and getattr(item, "date_exploitation", None) != anchor_year:
                continue
            matched.append(item)
        return matched

    match_strategies = [
        (True, True, True),
        (True, False, True),
        (True, True, False),
        (True, False, False),
        (False, True, True),
        (False, True, False),
    ]
    for require_number, require_name, require_year in match_strategies:
        if require_number and not anchor_number:
            continue
        if require_name and not anchor_name:
            continue
        if require_year and anchor_year is None:
            continue
        matched = _filter_matches(
            require_number=require_number,
            require_name=require_name,
            require_year=require_year,
        )
        if len(matched) == 1:
            return matched[0]
    return None


def _station_machines_have_gtp_codes_for_import(station_machines: list[Machine]) -> bool:
    return any(
        _extract_machine_gtp_codes_for_import(getattr(item, "machine_name", None))
        for item in station_machines
    )


def _get_machine_family_for_import(
    machine: Machine | None,
    *,
    anchor_station_id: int | None = None,
    use_external_code_hints: bool = True,
) -> list[Machine]:
    """
    Агрегаты с тем же external_code, что у machine, но только на станциях из «семейства»
    якорной станции.

    anchor_station_id: id станции из Excel (id_station). Если задан, семейство берётся по
    этой станции — иначе по станции агрегата в БД. Иначе при расхождении id_station в
    файле и id_station у машины группа и связи создавались по «чужой» станции.
    """
    if not machine:
        return []

    if anchor_station_id is not None:
        anchor = Station.query.get(anchor_station_id)
        if not anchor:
            return []
        stations_for_ids = _get_station_family_for_import(anchor)
        anchor_station = anchor
    else:
        source_station = getattr(machine, "machine_station", None)
        stations_for_ids = _get_station_family_for_import(source_station)
        anchor_station = source_station

    anchor_station_id_effective = getattr(anchor_station, "id", None)
    anchor_company_ids = _get_machine_company_identity_keys_for_import(
        machine,
        use_external_code_hints=use_external_code_hints,
    )
    if not anchor_company_ids:
        anchor_company_ids = _get_station_machine_company_ids_for_import(anchor_station_id_effective)
    if (
        anchor_station is not None
        and getattr(anchor_station, "external_code", None)
        and (anchor_company_ids or len(stations_for_ids) <= 1)
    ):
        relaxed_station_family = _get_relaxed_station_family_for_import(anchor_station)
        if relaxed_station_family:
            stations_for_ids = relaxed_station_family

    allowed_station_ids = {
        st.id for st in stations_for_ids if getattr(st, "id", None)
    }
    if not allowed_station_ids:
        return [machine]

    if anchor_company_ids:
        company_filtered_station_ids = {
            station_id
            for station_id in allowed_station_ids
            if not _get_station_machine_company_ids_for_import(station_id).isdisjoint(anchor_company_ids)
        }
        # Не смешиваем одноимённые станции с одинаковым external_code, если у них
        # полностью разные генкомпании: это разные семейства, как у ТЭС-2 в Карелии.
        if company_filtered_station_ids:
            allowed_station_ids = company_filtered_station_ids

    same_code_candidates_by_station: dict[int, list[Machine]] = {}
    machine_external_code = (getattr(machine, "external_code", None) or "").strip()
    anchor_gtp_codes = _extract_machine_gtp_codes_for_import(getattr(machine, "machine_name", None))
    if use_external_code_hints and machine_external_code:
        same_code_machines = Machine.query.filter(
            Machine.external_code == machine_external_code
        ).all()
        for candidate in same_code_machines:
            candidate_station_id = getattr(candidate, "id_station", None)
            if candidate_station_id in allowed_station_ids:
                same_code_candidates_by_station.setdefault(candidate_station_id, []).append(
                    candidate
                )

    anchor_station_machines = _get_station_machines_for_import(
        anchor_station_id_effective,
        company_identity_keys=anchor_company_ids or None,
    )
    anchor_index = None
    for idx, candidate in enumerate(anchor_station_machines):
        if getattr(candidate, "id", None) == getattr(machine, "id", None):
            anchor_index = idx
            break
    if use_external_code_hints and anchor_index is None and machine_external_code:
        for idx, candidate in enumerate(anchor_station_machines):
            if (getattr(candidate, "external_code", None) or "").strip() == machine_external_code:
                anchor_index = idx
                break

    resolved: list[Machine] = []
    seen_machine_ids: set[int] = set()
    for station in sorted(
        [st for st in stations_for_ids if getattr(st, "id", None) in allowed_station_ids],
        key=lambda item: ((getattr(item, "database_version_id", 0) or 0), getattr(item, "id", 0) or 0),
    ):
        station_id = getattr(station, "id", None)
        if station_id is None:
            continue

        if station_id == anchor_station_id_effective:
            matched_machine = machine
            matched_machine_id = getattr(matched_machine, "id", None)
            if matched_machine_id is None or matched_machine_id in seen_machine_ids:
                continue
            seen_machine_ids.add(matched_machine_id)
            resolved.append(matched_machine)
            continue

        same_code_candidates = sorted(
            same_code_candidates_by_station.get(station_id, []),
            key=_machine_import_sort_key,
        )
        station_machines = _get_station_machines_for_import(
            station_id,
            company_identity_keys=anchor_company_ids or None,
        )
        matched_machine = _match_station_machine_by_gtp_codes_for_import(
            same_code_candidates,
            anchor_gtp_codes,
        )
        if matched_machine is None:
            matched_machine = _match_station_machine_by_signature_for_import(
                station_machines,
                machine,
            )
        if matched_machine is None:
            matched_machine = _match_station_machine_by_gtp_codes_for_import(
                station_machines,
                anchor_gtp_codes,
            )
        if (
            matched_machine is None
            and anchor_gtp_codes
            and _station_machines_have_gtp_codes_for_import(station_machines)
        ):
            continue
        if matched_machine is None and use_external_code_hints:
            matched_machine = same_code_candidates[0] if same_code_candidates else None

        allow_anchor_index_fallback = (
            anchor_index is not None
            and (
                use_external_code_hints
                or (
                    not anchor_gtp_codes
                    and not _normalize_machine_number_for_import(getattr(machine, "machine_number", None))
                    and not _normalize_machine_name_for_import(getattr(machine, "machine_name", None))
                )
            )
        )
        if matched_machine is None and allow_anchor_index_fallback:
            if anchor_index < len(station_machines):
                matched_machine = station_machines[anchor_index]

        if matched_machine is None:
            continue

        matched_machine_id = getattr(matched_machine, "id", None)
        if matched_machine_id is None or matched_machine_id in seen_machine_ids:
            continue
        seen_machine_ids.add(matched_machine_id)
        resolved.append(matched_machine)

    return resolved or [machine]


def _equipment_group_name_sql_normalized():
    return func.lower(func.trim(func.replace(EquipmentGroupType.name, "\xa0", " ")))


def _normalize_equipment_group_name(text: str | None) -> str:
    """Нормализация имени для прямого сравнения с EquipmentGroupType.name."""
    if not text or (isinstance(text, str) and not text.strip()):
        return ""
    return str(text).strip().lower().replace("\xa0", " ").replace("\u00a0", " ")


def _find_equipment_group_by_name_or_mapping(
    group_text: str,
    db_version_id: int | None,
) -> EquipmentGroupType | None:
    """
    Ищет EquipmentGroupType по прямому совпадению имени
    в явно заданной версии БД. Если версия не передана,
    используется текущая версия, выбранная пользователем.
    """
    group_norm_sql = _normalize_equipment_group_name(group_text)
    if not group_norm_sql:
        return None

    target_version_id = db_version_id
    if target_version_id is None:
        target_version_id = get_current_db_version_id()
    eq_query = EquipmentGroupType.query.filter(
        _equipment_group_name_sql_normalized() == group_norm_sql
    )
    if target_version_id is not None:
        eq_query = filter_by_explicit_db_version(
            eq_query, EquipmentGroupType, target_version_id
        )
    return eq_query.order_by(EquipmentGroupType.id.asc()).first()


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

    Шаг 2: после прохода по найденным id_machine создаем EquipmentGroupSetStation
    и EquipmentGroupSet (с EquipmentGroup).

    Шаг 3: второй проход:
      - строки без id_machine (есть id_station, ge_numb и ge_name_ext/topl_name):
        обновление EquipmentGroup (v2) по полям из Excel
      - строки с id_machine: заполнение MachineFuelParam по полям из Excel
    """
    logger = _get_logger()
    t0 = time.perf_counter()
    filename = getattr(file, "filename", None)

    print(f"[IMPORT_FUEL_DB] Шаг 0: Старт. user={user} filename={filename}")
    logger.info("[IMPORT_FUEL_DB_EQUIPMENT_GROUPS] start user=%s filename=%s", user, filename)
    print("[IMPORT_FUEL_DB] Шаг 1: Чтение Excel — определение заголовков и колонок...")
    xls = pd.ExcelFile(file)
    sheet_name = xls.sheet_names[0]
    print(f"[IMPORT_FUEL_DB]   Лист: {sheet_name}")

    df, header_row = _detect_header_row_and_parse_excel(xls, sheet_name)
    if header_row > 0:
        print(f"[IMPORT_FUEL_DB]   Строка заголовка: {header_row + 1} (пропущено {header_row} строк)")
    print(f"[IMPORT_FUEL_DB]   Исходные колонки: {list(df.columns)}")
    print(f"[IMPORT_FUEL_DB]   Строк после dropna: {len(df)}")
    df = _apply_column_aliases(df)
    rows_with_empty_source_ids = _collect_rows_with_empty_station_and_machine_ids(df)
    # Импорт строго построчно: значения не протягиваются из слитых ячеек (без ffill).
    cols_to_keep = [c for c in df.columns if c in ALLOWED_IMPORT_COLUMNS]
    df = df[cols_to_keep]
    print(f"[IMPORT_FUEL_DB]   Колонки после алиасов: {list(df.columns)}")

    if "equipment_group" not in df.columns:
        raise ValueError(
            "Неверный шаблон файла: отсутствует колонка equipment_group."
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
    # Результат по каждой строке для отчета: index -> {step3, step4_2, step4_3}
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

    # Кэш по имени группы и версии БД.
    _eg_cache: dict[tuple[str, int | None], EquipmentGroupType | None] = {}

    def _find_eg_cached(gt: str, vid: int | None) -> EquipmentGroupType | None:
        key = (_normalize_equipment_group_name(gt), vid)
        if key not in _eg_cache:
            _eg_cache[key] = _find_equipment_group_by_name_or_mapping(gt, vid)
        return _eg_cache[key]

    current_version = get_current_db_version_id()
    all_db_versions = DatabaseVersion.query.filter(
        DatabaseVersion.id.isnot(None),
        DatabaseVersion.id > 0,
    ).all()
    valid_version_ids = {v.id for v in all_db_versions}

    def _find_import_anchor_equipment_group_type(
        group_text: str,
        fallback_version_id: int | None = None,
    ) -> EquipmentGroupType | None:
        """
        При импорте считаем текущую выбранную версию канонической.
        Если в ней тип не найден, допускаем fallback к версии исходной станции.
        """
        if current_version in valid_version_ids:
            canonical_type = _find_eg_cached(group_text, current_version)
            if canonical_type is not None:
                return canonical_type
        if (
            fallback_version_id in valid_version_ids
            and fallback_version_id != current_version
        ):
            return _find_eg_cached(group_text, fallback_version_id)
        return None

    def _resolve_forced_equipment_group_type_for_version(
        group_text: str,
        target_version_id: int | None,
        fallback_version_id: int | None = None,
    ) -> EquipmentGroupType | None:
        """
        Берёт канонический тип из текущей версии импорта и раскладывает
        его по нужной версии БД через ref_uuid.
        """
        anchor_type = _find_import_anchor_equipment_group_type(
            group_text,
            fallback_version_id=fallback_version_id,
        )
        if anchor_type is None:
            return None

        anchor_version_id = getattr(anchor_type, "database_version_id", None)
        if target_version_id == anchor_version_id or target_version_id is None:
            return anchor_type

        if target_version_id in valid_version_ids:
            return _get_equipment_group_type_for_version(anchor_type, target_version_id)

        return None

    def _resolve_version_id(entity) -> int | None:
        version_id = getattr(entity, "database_version_id", None)
        if version_id is None:
            version_id = current_version
        if version_id is not None and version_id not in valid_version_ids:
            if current_version in valid_version_ids:
                return current_version
            return None
        return version_id

    station_variants_cache: dict[int, list[Station]] = {}
    equipment_group_type_version_cache: dict[
        tuple[int, int], EquipmentGroupType | None
    ] = {}
    expanded_station_type_pairs_cache: dict[
        tuple[int, int], list[tuple[int, int, int | None]]
    ] = {}

    def _get_station_variants_for_all_versions(anchor_station: Station | None) -> list[Station]:
        """
        Возвращает по одной станции на каждую версию БД для того же объекта.

        Сохраняем текущую защиту от legacy-коллизий по external_code: сначала
        предпочитаем станции из _get_station_family_for_import, а если в версии
        такой станции нет, берем лучший кандидат с тем же external_code.
        """
        anchor_station_id = getattr(anchor_station, "id", None)
        if anchor_station_id is None:
            return []
        if anchor_station_id in station_variants_cache:
            return station_variants_cache[anchor_station_id]

        station_variants_cache[anchor_station_id] = []
        station_external_code = (getattr(anchor_station, "external_code", None) or "").strip()
        if not station_external_code:
            return station_variants_cache[anchor_station_id]

        family = _get_station_family_for_import(anchor_station)
        family_ids = {
            station.id for station in family if getattr(station, "id", None) is not None
        }
        same_code_stations = Station.query.filter(
            Station.external_code == station_external_code
        ).all()

        source_rd_id = getattr(anchor_station, "id_regional_district", None)
        source_res_id = getattr(anchor_station, "id_regional_energy_system", None)
        source_name = _normalized_station_identity_name(anchor_station)
        best_station_by_version: dict[int, tuple[tuple[int, int, int, int], Station]] = {}

        for candidate in same_code_stations:
            candidate_version = getattr(candidate, "database_version_id", None)
            if candidate_version not in valid_version_ids:
                continue

            score = (
                0 if candidate.id in family_ids else 1,
                0
                if source_rd_id is not None
                and getattr(candidate, "id_regional_district", None) == source_rd_id
                else 1,
                0
                if source_res_id is not None
                and getattr(candidate, "id_regional_energy_system", None) == source_res_id
                else 1,
                0
                if source_name and _normalized_station_identity_name(candidate) == source_name
                else 1,
                candidate.id or 0,
            )
            current_best = best_station_by_version.get(candidate_version)
            if current_best is None or score < current_best[0]:
                best_station_by_version[candidate_version] = (score, candidate)

        station_variants_cache[anchor_station_id] = [
            scored_candidate[1]
            for _, scored_candidate in sorted(
                best_station_by_version.items(), key=lambda item: item[0]
            )
        ]
        return station_variants_cache[anchor_station_id]

    def _get_equipment_group_type_for_version(
        anchor_type: EquipmentGroupType | None,
        version_id: int | None,
    ) -> EquipmentGroupType | None:
        if anchor_type is None or version_id not in valid_version_ids:
            return None
        cache_key = (anchor_type.id, version_id)
        if cache_key in equipment_group_type_version_cache:
            return equipment_group_type_version_cache[cache_key]

        query = EquipmentGroupType.query
        ref_uuid = getattr(anchor_type, "ref_uuid", None)
        if ref_uuid:
            query = query.filter(EquipmentGroupType.ref_uuid == ref_uuid)
        else:
            query = query.filter(
                _equipment_group_name_sql_normalized()
                == _normalize_equipment_group_name(getattr(anchor_type, "name", None))
            )
        query = filter_by_explicit_db_version(query, EquipmentGroupType, version_id)
        equipment_group_type_version_cache[cache_key] = query.order_by(
            EquipmentGroupType.id.asc()
        ).first()
        return equipment_group_type_version_cache[cache_key]

    def _expand_station_type_pairs_all_versions(
        station_id: int,
        equipment_group_type_id: int,
    ) -> list[tuple[int, int, int | None]]:
        """
        Возвращает пары (station_id, equipment_group_type_id, version_id) для всех версий БД,
        где найдены эквиваленты станции и типа группы оборудования.
        """
        cache_key = (station_id, equipment_group_type_id)
        if cache_key in expanded_station_type_pairs_cache:
            return expanded_station_type_pairs_cache[cache_key]

        result: list[tuple[int, int, int | None]] = []
        anchor_station = Station.query.get(station_id)
        anchor_type = EquipmentGroupType.query.get(equipment_group_type_id)
        if anchor_station and anchor_type:
            for station_variant in _get_station_variants_for_all_versions(anchor_station):
                version_id = _resolve_version_id(station_variant)
                if version_id not in valid_version_ids:
                    continue
                equipment_group_type_variant = _get_equipment_group_type_for_version(
                    anchor_type, version_id
                )
                if equipment_group_type_variant is None:
                    continue
                result.append(
                    (station_variant.id, equipment_group_type_variant.id, version_id)
                )

        if not result and anchor_station and anchor_type:
            version_id = _resolve_version_id(anchor_station)
            result.append((station_id, equipment_group_type_id, version_id))

        seen_pairs: set[tuple[int, int, int | None]] = set()
        deduped_result: list[tuple[int, int, int | None]] = []
        for pair in sorted(result, key=lambda item: ((item[2] or 0), item[0], item[1])):
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            deduped_result.append(pair)

        expanded_station_type_pairs_cache[cache_key] = deduped_result
        return deduped_result

    def _equipment_group_types_equivalent(
        left_type: EquipmentGroupType | None,
        right_type: EquipmentGroupType | None,
    ) -> bool:
        if left_type is None or right_type is None:
            return False
        left_ref_uuid = getattr(left_type, "ref_uuid", None)
        right_ref_uuid = getattr(right_type, "ref_uuid", None)
        if left_ref_uuid and right_ref_uuid:
            return left_ref_uuid == right_ref_uuid
        return _normalize_equipment_group_name(getattr(left_type, "name", None)) == (
            _normalize_equipment_group_name(getattr(right_type, "name", None))
        )

    def _get_links_for_station_and_version(
        station_id: int,
        version_id: int | None,
    ) -> list[EquipmentGroupSetStation]:
        query = EquipmentGroupSetStation.query.filter(
            EquipmentGroupSetStation.station_id == station_id
        )
        if version_id is None:
            query = query.filter(EquipmentGroupSetStation.database_version_id.is_(None))
        else:
            query = query.filter(EquipmentGroupSetStation.database_version_id == version_id)
        return query.order_by(EquipmentGroupSetStation.id.asc()).all()

    def _merge_equipment_group_set_station_links(
        source_link: EquipmentGroupSetStation,
        target_link: EquipmentGroupSetStation,
    ) -> int:
        """
        Переносит EquipmentGroupSet со source_link на target_link и удаляет дубликаты.
        Возвращает число изменённых/deleted EquipmentGroupSet.
        """
        moved_sets = 0
        source_sets = EquipmentGroupSet.query.filter(
            EquipmentGroupSet.equipment_group_set_station_id == source_link.id
        ).all()
        for source_set in source_sets:
            duplicate = EquipmentGroupSet.query.filter_by(
                equipment_group_id=source_set.equipment_group_id,
                equipment_group_set_station_id=target_link.id,
            ).first()
            if duplicate is not None:
                db.session.delete(source_set)
                moved_sets += 1
                continue
            source_set.equipment_group_set_station_id = target_link.id
            db.session.add(source_set)
            moved_sets += 1
        db.session.flush()
        db.session.delete(source_link)
        db.session.flush()
        return moved_sets

    def _ensure_compatible_equipment_group_set_station_link(
        station_id: int,
        equipment_group_type_id: int,
        version_id: int | None,
    ) -> tuple[EquipmentGroupSetStation | None, bool, int]:
        """
        Возвращает корректный EquipmentGroupSetStation для станции/типа/версии.

        Если в БД уже есть "битый" link той же станции и версии, но с type_id из другой
        версии (при этом ref_uuid типа совпадает), link чинится автоматически.
        """
        desired_type = EquipmentGroupType.query.get(equipment_group_type_id)
        if desired_type is None:
            return None, False, 0

        exact_link = (
            EquipmentGroupSetStation.query.filter(
                EquipmentGroupSetStation.station_id == station_id,
                EquipmentGroupSetStation.equipment_group_type_id == equipment_group_type_id,
                (
                    EquipmentGroupSetStation.database_version_id.is_(None)
                    if version_id is None
                    else EquipmentGroupSetStation.database_version_id == version_id
                ),
            )
            .order_by(EquipmentGroupSetStation.id.asc())
            .first()
        )

        repaired_sets = 0
        repaired = False
        station_version_links = _get_links_for_station_and_version(station_id, version_id)

        if exact_link is not None:
            for candidate_link in station_version_links:
                if candidate_link.id == exact_link.id:
                    continue
                candidate_type = EquipmentGroupType.query.get(
                    candidate_link.equipment_group_type_id
                )
                if not _equipment_group_types_equivalent(candidate_type, desired_type):
                    continue
                repaired_sets += _merge_equipment_group_set_station_links(
                    candidate_link, exact_link
                )
                repaired = True
            return exact_link, repaired, repaired_sets

        for candidate_link in station_version_links:
            candidate_type = EquipmentGroupType.query.get(candidate_link.equipment_group_type_id)
            if not _equipment_group_types_equivalent(candidate_type, desired_type):
                continue
            candidate_link.equipment_group_type_id = equipment_group_type_id
            db.session.add(candidate_link)
            db.session.flush()
            return candidate_link, True, 0

        return None, False, 0

    STEP3_COMMIT_EVERY = 25
    last_step3_commit_at = 0
    processed_pairs: set[tuple[int, int, int | None]] = set()
    # Карта (station_id, equipment_group_type_id, version_id, is_new_group) -> equipment_group_id из Excel.
    pair_variant_to_equipment_group_id: dict[tuple[int, int, int | None, bool], int] = {}
    requested_group_variants: set[tuple[int, int, int | None, bool]] = set()
    machine_to_group_variant: dict[int, tuple[int, int, int | None, bool]] = {}
    pair_variant_to_created_equipment_group_id: dict[tuple[int, int, int | None, bool], int] = {}
    has_equipment_group_id_col = "equipment_group_id" in df.columns
    ignored_excel_equipment_group_ids_by_reason: dict[str, set[tuple]] = {
        "wrong_version": set(),
        "wrong_link": set(),
        "not_found": set(),
    }

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
        if index in rows_with_empty_source_ids:
            skipped_empty += 1
            _audit_inc("row_skip_empty_source_ids", f"row_index={index}")
            skip_message = "Пропуск: в исходной строке пусты id_station и id_machine"
            _set_row_result(index, "step3", skip_message)
            _set_row_result(index, "step4_2", skip_message)
            _set_row_result(index, "step4_3", skip_message)
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

            # Строка только со станцией (без id_machine): создаём связи в шаге 4.1 без привязки агрегатов
            if machine_id is None:
                anchor_station = Station.query.get(station_id_row)
                if not anchor_station:
                    skipped_invalid += 1
                    _audit_inc("station_not_found", f"row_index={index}; id_station={station_id_row}")
                    _set_row_result(
                        index,
                        "step3",
                        f"Пропуск: станция id_station={station_id_row} не найдена",
                    )
                    continue
                db_version_st = _resolve_version_id(anchor_station)
                group_type = _resolve_forced_equipment_group_type_for_version(
                    group_text,
                    db_version_st,
                    fallback_version_id=db_version_st,
                )
                if not group_type:
                    _audit_inc(
                        "equipment_group_not_found",
                        f"row_index={index}; group={group_text}; version={db_version_st}",
                    )
                    _set_row_result(
                        index,
                        "step3",
                        f"Пропуск: группа оборудования '{group_text}' не найдена в справочнике",
                    )
                    continue
                pair = (station_id_row, group_type.id, db_version_st)
                processed_pairs.add(pair)
                pair_variant_key = (station_id_row, group_type.id, db_version_st, False)
                requested_group_variants.add(pair_variant_key)
                row_eg_id = _safe_int(row.get("equipment_group_id")) if has_equipment_group_id_col else None
                if row_eg_id is not None:
                    pair_variant_to_equipment_group_id[pair_variant_key] = row_eg_id
                _set_row_result(
                    index,
                    "step3",
                    f"Зарегистрирована связь станция–тип группы (без id_machine): '{group_text}'",
                )
                continue

            # По id_machine находим агрегат
            machine = Machine.query.get(machine_id)
            if not machine or not machine.external_code:
                skipped_invalid += 1
                _audit_inc("machine_not_found", f"row_index={index}; id_machine={machine_id}")
                _set_row_result(index, "step3", f"Пропуск: агрегат id={machine_id} не найден или нет external_code")
                continue

            anchor_station = Station.query.get(station_id_row)
            if not anchor_station:
                skipped_invalid += 1
                _audit_inc("station_not_found", f"row_index={index}; id_station={station_id_row}")
                _set_row_result(index, "step3", f"Пропуск: станция id_station={station_id_row} не найдена")
                continue

            machines_same_code = _get_machine_family_for_import(
                machine, anchor_station_id=station_id_row
            )
            if not machines_same_code:
                skipped_invalid += 1
                _audit_inc(
                    "machine_not_on_excel_station",
                    f"row_index={index}; id_machine={machine_id}; id_station={station_id_row}",
                )
                _set_row_result(
                    index,
                    "step3",
                    f"Пропуск: нет агрегатов с external_code этого id_machine на станции id_station={station_id_row}",
                )
                continue

            step3_updated_count = 0
            step3_not_found = False
            anchor_station_version_id = _resolve_version_id(anchor_station)
            canonical_group_type = _find_import_anchor_equipment_group_type(
                group_text,
                fallback_version_id=anchor_station_version_id,
            )

            if canonical_group_type is None:
                _audit_inc(
                    "equipment_group_not_found",
                    f"row_index={index}; group={group_text}; version={current_version}",
                )
                _set_row_result(
                    index,
                    "step3",
                    f"Пропуск: группа оборудования '{group_text}' не найдена в справочнике",
                )
                continue

            for m in machines_same_code:
                db_version_id = _resolve_version_id(m)
                equipment_group = _resolve_forced_equipment_group_type_for_version(
                    group_text,
                    db_version_id,
                    fallback_version_id=anchor_station_version_id,
                )
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

                # Используем канонический тип для каждой версии и согласованную station_id.
                pair = (m.id_station, equipment_group.id, db_version_id)
                processed_pairs.add(pair)
                is_new_group = _machine_requires_new_equipment_group(m, db_version_id)
                group_variant_key = (m.id_station, equipment_group.id, db_version_id, is_new_group)
                requested_group_variants.add(group_variant_key)
                machine_to_group_variant[m.id] = group_variant_key
                row_eg_id = _safe_int(row.get("equipment_group_id")) if has_equipment_group_id_col else None
                if row_eg_id is not None:
                    pair_variant_to_equipment_group_id[group_variant_key] = row_eg_id

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
    repaired_links = 0
    repaired_link_sets = 0
    # Карта (station_id, equipment_group_type_id, version_id) -> numb для предотвращения дублей.
    # Источник numb: только station-only строки (есть id_station и нет id_machine).
    pair_to_numb: dict[tuple[int, int, int | None], int] = {}
    has_numb_col = "ge_numb" in df.columns
    if has_numb_col:
        for index, row in df.iterrows():
            if row.isnull().all():
                continue
            if index in rows_with_empty_source_ids:
                continue
            machine_id = _safe_int(row.get("id_machine")) if has_machine else None
            station_id_row = _safe_int(row.get("id_station")) if has_station else None
            if machine_id is not None:
                continue
            if station_id_row is None:
                continue
            group_text = _get_equipment_group_from_row(row, df.columns)
            if group_text:
                group_text = _clean_name(group_text)
            if not group_text:
                continue
            raw = _extract_cell_value(row, "ge_numb")
            numb_val = _safe_int(raw)
            if numb_val is None:
                continue
            station = Station.query.get(station_id_row)
            if not station or not station.external_code:
                continue
            anchor_version_id = _resolve_version_id(station)
            anchor_group_type = _find_import_anchor_equipment_group_type(
                group_text,
                fallback_version_id=anchor_version_id,
            )
            if not anchor_group_type:
                continue
            for expanded_station_id, expanded_type_id, expanded_version_id in (
                _expand_station_type_pairs_all_versions(station_id_row, anchor_group_type.id)
            ):
                pair_to_numb[(expanded_station_id, expanded_type_id, expanded_version_id)] = numb_val

    print("[IMPORT_FUEL_DB] Шаг 4.1: Формирование EquipmentGroupSetStation и EquipmentGroupSet...")
    try:
        # Собираем (station_id, equipment_group_type_id, version_id) для всех доступных версий БД,
        # где удалось сопоставить станцию и refdata-тип группы оборудования.
        expanded_pairs: set[tuple[int, int, int | None]] = set()
        expanded_group_variants: set[tuple[int, int, int | None, bool]] = set()

        for station_id, equipment_group_type_id, version_id in processed_pairs:
            for expanded_pair in _expand_station_type_pairs_all_versions(
                station_id, equipment_group_type_id
            ):
                expanded_pairs.add(expanded_pair)

        for station_id, equipment_group_type_id, version_id, is_new_group in requested_group_variants:
            for expanded_station_id, expanded_type_id, expanded_version_id in (
                _expand_station_type_pairs_all_versions(station_id, equipment_group_type_id)
            ):
                expanded_group_variants.add(
                    (expanded_station_id, expanded_type_id, expanded_version_id, is_new_group)
                )
                expanded_pairs.add((expanded_station_id, expanded_type_id, expanded_version_id))

        for station_id, equipment_group_type_id, version_id in sorted(expanded_pairs):
            link, was_repaired, merged_set_count = (
                _ensure_compatible_equipment_group_set_station_link(
                    station_id,
                    equipment_group_type_id,
                    version_id,
                )
            )
            if was_repaired:
                repaired_links += 1
                repaired_link_sets += merged_set_count

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

        for station_id, equipment_group_type_id, version_id, is_new_group in sorted(expanded_group_variants):
            link, was_repaired, merged_set_count = (
                _ensure_compatible_equipment_group_set_station_link(
                    station_id,
                    equipment_group_type_id,
                    version_id,
                )
            )
            if was_repaired:
                repaired_links += 1
                repaired_link_sets += merged_set_count
            if not link:
                continue

            equipment_group = None
            row_equipment_group_id = pair_variant_to_equipment_group_id.get(
                (station_id, equipment_group_type_id, version_id, is_new_group)
            )

            if row_equipment_group_id is not None:
                # Использование существующей группы по id из Excel, если она относится к этой же связи.
                eg_by_id = EquipmentGroup.query.get(row_equipment_group_id)
                if eg_by_id:
                    if getattr(eg_by_id, "database_version_id", None) != version_id:
                        warning_key = (
                            row_equipment_group_id,
                            getattr(eg_by_id, "database_version_id", None),
                            version_id,
                        )
                        if warning_key not in ignored_excel_equipment_group_ids_by_reason["wrong_version"]:
                            ignored_excel_equipment_group_ids_by_reason["wrong_version"].add(warning_key)
                            logger.warning(
                                "[IMPORT_FUEL_DB] equipment_group_id=%s из Excel относится к version_id=%s, "
                                "а для текущей строки ожидается version_id=%s. "
                                "Игнорируем id и используем стандартную логику "
                                "для (station_id=%s, type_id=%s, version=%s, is_new=%s).",
                                row_equipment_group_id,
                                getattr(eg_by_id, "database_version_id", None),
                                version_id,
                                station_id,
                                equipment_group_type_id,
                                version_id,
                                is_new_group,
                            )
                    elif not _equipment_group_matches_station_link(
                        row_equipment_group_id,
                        station_id,
                        equipment_group_type_id,
                        version_id,
                        allow_cross_station_merge=True,
                        is_new_group=is_new_group,
                    ):
                        warning_key = (
                            row_equipment_group_id,
                            station_id,
                            equipment_group_type_id,
                            version_id,
                        )
                        if warning_key not in ignored_excel_equipment_group_ids_by_reason["wrong_link"]:
                            ignored_excel_equipment_group_ids_by_reason["wrong_link"].add(warning_key)
                            logger.warning(
                                "[IMPORT_FUEL_DB] equipment_group_id=%s из Excel уже связан с другой "
                                "станцией/типом. Игнорируем id и используем стандартную логику "
                                "для (station_id=%s, type_id=%s, version=%s, is_new=%s).",
                                row_equipment_group_id,
                                station_id,
                                equipment_group_type_id,
                                version_id,
                                is_new_group,
                            )
                    else:
                        equipment_group = eg_by_id
                else:
                    warning_key = (row_equipment_group_id,)
                    if warning_key not in ignored_excel_equipment_group_ids_by_reason["not_found"]:
                        ignored_excel_equipment_group_ids_by_reason["not_found"].add(warning_key)
                        logger.warning(
                            "[IMPORT_FUEL_DB] equipment_group_id=%s из Excel не найден в БД. "
                            "Создаётся/подбирается группа по стандартной логике (station_id=%s, type_id=%s, version=%s, is_new=%s).",
                            row_equipment_group_id,
                            station_id,
                            equipment_group_type_id,
                            version_id,
                            is_new_group,
                        )

            if equipment_group is None:
                station = Station.query.get(station_id)
                group_type = EquipmentGroupType.query.get(equipment_group_type_id)
                ref_uuid = getattr(group_type, "ref_uuid", None) if group_type else None
                group_name = _compose_equipment_group_name(
                    station,
                    group_type,
                    is_new_group=is_new_group,
                )
                key = (station_id, equipment_group_type_id, version_id)
                numb_from_map = pair_to_numb.get(key)

                # По numb безопасно автоподбираем только базовую группу.
                if not is_new_group and numb_from_map is not None:
                    equipment_group = _find_equipment_group_by_numb_for_station_external_code(
                        numb_from_map,
                        station_id,
                        equipment_group_type_id,
                        version_id,
                    )

                station_ext_code = (station.external_code or "").strip() if station else ""
                type_key = ref_uuid if ref_uuid else (
                    group_type.ref_uuid
                    if group_type and getattr(group_type, "ref_uuid", None)
                    else (group_type.name if group_type else str(equipment_group_type_id))
                )
                target_external_code = _generate_stable_external_code_equipment_group(
                    station_ext_code,
                    type_key,
                    numb_from_map,
                    group_variant="new" if is_new_group else None,
                )
                if equipment_group is None:
                    equipment_group = _find_equipment_group_by_external_code(
                        target_external_code,
                        version_id,
                    )
                if equipment_group is None:
                    equipment_group = EquipmentGroup(name=group_name)
                    if numb_from_map is not None:
                        equipment_group.numb = str(numb_from_map)
                    equipment_group.external_code = target_external_code
                    if version_id is not None:
                        equipment_group.database_version_id = version_id
                    elif current_version is not None:
                        set_db_version_on_create(equipment_group)
                    db.session.add(equipment_group)
                    db.session.flush()
                    created_groups += 1

            pair_variant_to_created_equipment_group_id[
                (station_id, equipment_group_type_id, version_id, is_new_group)
            ] = equipment_group.id

            set_v2 = EquipmentGroupSet.query.filter_by(
                equipment_group_id=equipment_group.id,
                equipment_group_set_station_id=link.id,
            ).first()
            if not set_v2:
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
        elif repaired_links or repaired_link_sets:
            db.session.commit()
            print(
                f"[IMPORT_FUEL_DB]   Исправлено связей: links={repaired_links}, moved_sets={repaired_link_sets}"
            )
        else:
            print("[IMPORT_FUEL_DB]   Изменений нет (все связи уже существуют)")
        ignored_excel_equipment_group_ids_total = sum(
            len(items) for items in ignored_excel_equipment_group_ids_by_reason.values()
        )
        if ignored_excel_equipment_group_ids_total:
            print(
                "[IMPORT_FUEL_DB]   Игнорировано equipment_group_id из Excel: "
                f"not_found={len(ignored_excel_equipment_group_ids_by_reason['not_found'])}, "
                f"wrong_version={len(ignored_excel_equipment_group_ids_by_reason['wrong_version'])}, "
                f"wrong_link={len(ignored_excel_equipment_group_ids_by_reason['wrong_link'])}"
            )
    except Exception as e:
        print(f"[IMPORT_FUEL_DB]   ОШИБКА при формировании EquipmentGroupSet: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass
        logger.exception("[IMPORT_FUEL_DB_EQUIPMENT_GROUPS] EquipmentGroupSet step failed: %s", e)
        raise

    updated_groups_fields = 0
    print("[IMPORT_FUEL_DB] Шаг 4.2: Обновление EquipmentGroup из строк Excel...")
    try:
        for index, row in df.iterrows():
            if row.isnull().all():
                continue
            if index in rows_with_empty_source_ids:
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

            # Обновление полей EquipmentGroup (шаг 4.2) — только строки «только станция»
            # с обязательными id_station + ge_numb + ge_name_ext/topl_name.
            if machine_id is not None:
                _set_row_result(
                    index,
                    "step4_2",
                    "Пропуск: обновление EquipmentGroup — только для строк без id_machine",
                )
                continue

            excel_numb = _extract_equipment_group_numb_from_import_row(row, df.columns)
            if excel_numb is None:
                _set_row_result(
                    index,
                    "step4_2",
                    "Пропуск: нет значения topl_NUMB (ge_numb) в строке — нужен для сопоставления с EquipmentGroup",
                )
                continue

            topl_name_value = _safe_str(_extract_cell_value(row, "ge_name_ext")) if "ge_name_ext" in df.columns else None
            if topl_name_value is None:
                _set_row_result(
                    index,
                    "step4_2",
                    "Пропуск: нет значения topl_name (ge_name_ext/name_ext) в строке — строка не подходит для обновления EquipmentGroup",
                )
                continue

            group_text = _get_equipment_group_from_row(row, df.columns)
            if group_text:
                group_text = _clean_name(group_text)
            if group_text and _is_kotelnye_group(group_text):
                _set_row_result(index, "step4_2", "Пропуск: «Котельные» обрабатываются в шаге 4.2.5")
                continue

            station = Station.query.get(station_id_row)
            if not station or not station.external_code:
                _set_row_result(index, "step4_2", "Пропуск: станция не найдена или нет external_code")
                continue

            station_variants = _get_station_variants_for_all_versions(station)
            if not station_variants:
                _set_row_result(index, "step4_2", "Пропуск: нет станций с таким external_code")
                continue

            base_row_values: dict[str, str | None] = {}
            for field in EQUIPMENT_GROUP_UPDATE_FIELDS:
                raw = None
                col_names = EQUIPMENT_GROUP_FIELD_TO_COLUMNS.get(field, [field])
                for col in col_names:
                    if col in df.columns:
                        raw = _extract_cell_value(row, col)
                        if raw is not None:
                            break
                if raw is None:
                    continue
                if field in EQUIPMENT_GROUP_STRICT_INTEGER_FIELDS:
                    val = _safe_str_int_strict(raw)
                elif field in EQUIPMENT_GROUP_SET_INTEGER_FIELDS:
                    val = _safe_str_int(raw)
                else:
                    val = _safe_str(raw)
                if val is not None:
                    if field == "note" and len(val) > 1000:
                        val = val[:1000]
                    base_row_values[field] = val

            row_updated = 0
            row_missing_links = 0
            had_candidate_groups = False
            numb_matched_any = False
            touched_equipment_group_ids: set[int] = set()
            for st in station_variants:
                db_version_id = _resolve_version_id(st)

                # Для station-only строк данные EquipmentGroup должны ложиться на все группы
                # этой станции/семейства с тем же numb. Не сужаем выборку по type/equipment_group.
                candidate_groups = _find_equipment_groups_by_numb_for_station_external_code(
                    excel_numb,
                    st.id,
                    db_version_id,
                )
                if not candidate_groups:
                    row_missing_links += 1
                    continue
                had_candidate_groups = True

                row_values = dict(base_row_values)
                # name обновляем только в сценариях, где есть однозначное сопоставление с типом группы.
                # Для station+numb строки сохраняем существующие typed-name и обновляем только name_ext/topl_name и общие поля.
                row_values.pop("name", None)

                if not row_values:
                    continue

                for equipment_group in candidate_groups:
                    if not equipment_group or equipment_group.id in touched_equipment_group_ids:
                        continue
                    touched_equipment_group_ids.add(equipment_group.id)
                    numb_matched_any = True
                    # Объединенная группа (>1 EquipmentGroupSet): не перезаписывать name
                    eg_set_count = (
                        db.session.query(func.count(EquipmentGroupSet.id))
                        .filter(EquipmentGroupSet.equipment_group_id == equipment_group.id)
                        .scalar()
                    ) or 0
                    skip_name_update = eg_set_count > 1
                    changed = False
                    for field, val in row_values.items():
                        if skip_name_update and field == "name":
                            continue
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
            elif row_missing_links and row_updated == 0:
                _set_row_result(index, "step4_2", "Пропуск: нет EquipmentGroup по связи station+numb")
            elif had_candidate_groups and not numb_matched_any:
                _set_row_result(
                    index,
                    "step4_2",
                    f"Пропуск: numb в файле ({excel_numb}) не совпадает с EquipmentGroup.numb по связи станция–тип",
                )
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
    created_kotelnye_links = 0
    created_kotelnye_sets = 0
    # Котельные сохраняются во всех версиях БД (все записи DatabaseVersion без фильтра id>0)
    kotelnye_all_versions = DatabaseVersion.query.filter(
        DatabaseVersion.id.isnot(None),
    ).order_by(DatabaseVersion.id).all()
    kotelnye_version_ids: list[int] = [v.id for v in kotelnye_all_versions if v.id]
    if not kotelnye_version_ids and current_version:
        kotelnye_version_ids = [current_version]
    valid_version_ids_kotelnye = valid_version_ids | set(kotelnye_version_ids)
    print(
        "[IMPORT_FUEL_DB] Шаг 4.2.5: Обработка «Котельные» — "
        "EquipmentGroup + EquipmentGroupSetStation(station_id=NULL) + EquipmentGroupSet..."
    )
    try:
        for index, row in df.iterrows():
            if row.isnull().all():
                continue
            if index in rows_with_empty_source_ids:
                continue

            # Котельные: только столбец «Группа оборудования» (ge_gruppa_oborudovaniya)
            group_text = _get_equipment_group_for_kotelnye(row, df.columns)
            if group_text:
                group_text = _clean_name(group_text)
            # Проверка: в «Группа оборудования» указано «Котельные» или строка с «котельн»
            if not group_text or not _is_kotelnye_group(group_text):
                continue

            base_row_values: dict[str, str | None] = {}
            for field in EQUIPMENT_GROUP_UPDATE_FIELDS:
                raw = None
                col_names = EQUIPMENT_GROUP_FIELD_TO_COLUMNS.get(field, [field])
                for col in col_names:
                    if col in df.columns:
                        raw = _extract_cell_value(row, col)
                        if raw is not None:
                            break
                if raw is None:
                    continue
                if field in EQUIPMENT_GROUP_STRICT_INTEGER_FIELDS:
                    val = _safe_str_int_strict(raw)
                elif field in EQUIPMENT_GROUP_SET_INTEGER_FIELDS:
                    val = _safe_str_int(raw)
                else:
                    val = _safe_str(raw)
                if val is not None:
                    if field == "note" and len(val) > 1000:
                        val = val[:1000]
                    base_row_values[field] = val

            # Название группы (EquipmentGroup.name) — из name_ext (ge_name_ext / topl_name), не из столбца «Группа оборудования»
            name_ext_val = base_row_values.get("name_ext")
            if name_ext_val:
                base_row_values["name"] = name_ext_val
            elif "name" not in base_row_values:
                base_row_values["name"] = KOTELNYE_GROUP_NAME

            row_created = 0
            row_updated = 0
            row_created_sets = 0
            numb_for_kotelnye = _safe_int(base_row_values.get("numb")) if base_row_values else None
            standalone_name = base_row_values["name"]
            missing_type_versions: list[int] = []
            for db_version_id in kotelnye_version_ids:
                link, link_was_created = _find_or_create_kotelnaya_type_station_link(
                    db_version_id,
                    valid_version_ids_kotelnye,
                )
                if link is None:
                    missing_type_versions.append(db_version_id)
                    continue
                if link_was_created:
                    created_kotelnye_links += 1

                eg, was_created = _find_or_create_standalone_equipment_group(
                    standalone_name, db_version_id, valid_version_ids_kotelnye, numb=numb_for_kotelnye
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

                set_v2 = EquipmentGroupSet.query.filter_by(
                    equipment_group_id=eg.id,
                    equipment_group_set_station_id=link.id,
                ).first()
                if not set_v2:
                    set_v2 = EquipmentGroupSet(
                        equipment_group_id=eg.id,
                        equipment_group_set_station_id=link.id,
                    )
                    db.session.add(set_v2)
                    created_kotelnye_sets += 1
                    row_created_sets += 1

                # Flush после каждой версии — чтобы INSERT выполнился до поиска в следующей
                db.session.flush()

            if missing_type_versions:
                result_msg = (
                    "Пропуск: не найден тип группы оборудования "
                    f"'котельная' для версий {', '.join(str(v) for v in missing_type_versions)}"
                )
            elif row_updated:
                result_msg = (
                    "ОБНОВЛЕНО: standalone «Котельные» синхронизированы через "
                    f"EquipmentGroupSet/TypeStation во {len(kotelnye_version_ids)} версиях"
                )
            elif row_created or row_created_sets:
                result_msg = (
                    f"Создано: EquipmentGroup в {row_created} версиях, "
                    f"EquipmentGroupSet в {row_created_sets} версиях"
                )
            else:
                result_msg = "Без изменений: «Котельные»"
            _set_row_result(index, "step4_2", result_msg)

        if (
            updated_kotelnye
            or created_kotelnye
            or created_kotelnye_links
            or created_kotelnye_sets
        ):
            db.session.commit()
            print(
                "[IMPORT_FUEL_DB]   Обработано «Котельные»: "
                f"updated_groups={updated_kotelnye}, created_groups={created_kotelnye}, "
                f"created_type_station_links={created_kotelnye_links}, "
                f"created_group_sets={created_kotelnye_sets}"
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
            if index in rows_with_empty_source_ids:
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

            with db.session.no_autoflush:
                machine = Machine.query.get(machine_id)
                machines_same_code = _get_machine_family_for_import(
                    machine, anchor_station_id=station_id_row
                )
            if not machine or not machine.external_code:
                _set_row_result(index, "step4_3", "Пропуск: агрегат не найден или нет external_code")
                continue
            if not machines_same_code:
                _set_row_result(
                    index,
                    "step4_3",
                    f"Пропуск: нет агрегатов с таким external_code на станции id_station={station_id_row}",
                )
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
            for col in ("machine_grcode",):
                if col in df.columns:
                    raw_grcode = _extract_cell_value(row, col)
                    break
            if raw_grcode is not None and not (isinstance(raw_grcode, float) and pd.isna(raw_grcode)):
                val = _safe_int(raw_grcode)
                if val is not None:
                    row_values["grcode"] = val

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

                group_variant_key = machine_to_group_variant.get(m.id)
                target_equipment_group_id = (
                    pair_variant_to_created_equipment_group_id.get(group_variant_key)
                    if group_variant_key is not None
                    else None
                )
                if (
                    target_equipment_group_id is not None
                    and getattr(mtp, "equipment_group_id", None) != target_equipment_group_id
                ):
                    mtp.equipment_group_id = target_equipment_group_id
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
            elif not row_values:
                _set_row_result(index, "step4_3", "Пропуск: нет данных для заполнения MachineFuelParam")
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

    # Шаг 4.4: Пересчет y_calc, btp_calc, sntp_calc, bk_calc, snk_calc
    # в EquipmentGroupSpecificFuelConsumption по данным EquipmentGroupFuelParam
    updated_specific_consumption_calc = 0
    try:
        print("[IMPORT_FUEL_DB] Шаг 4.4: Расчет удельных показателей (y_calc, btp_calc, sntp_calc, bk_calc)...")
        updated_specific_consumption_calc = recalculate_all_specific_fuel_consumption_calc()
        print(
            f"[IMPORT_FUEL_DB]   Обновлено EquipmentGroupSpecificFuelConsumption (_calc): "
            f"{updated_specific_consumption_calc}"
        )
    except Exception as e:
        print(f"[IMPORT_FUEL_DB]   ОШИБКА при расчете удельных показателей: {e}")
        logger.exception(
            "[IMPORT_FUEL_DB_EQUIPMENT_GROUPS] Step 4.4 recalculate_specific_consumption_calc failed: %s",
            e,
        )
        try:
            db.session.rollback()
        except Exception:
            pass
        raise

    elapsed = time.perf_counter() - t0
    print(
        f"[IMPORT_FUEL_DB] Шаг 5: ИТОГ. processed_rows={processed_rows} skipped_empty={skipped_empty} "
        f"skipped_invalid={skipped_invalid} updated_machines={updated_machines} "
        f"created_links={created_links} created_groups={created_groups} created_sets={created_sets} "
        f"updated_groups_fields={updated_groups_fields} updated_kotelnye={updated_kotelnye} "
        f"created_kotelnye={created_kotelnye} updated_fuel_params={updated_fuel_params} "
        f"updated_specific_consumption_calc={updated_specific_consumption_calc} "
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
                f"updated_specific_consumption_calc={updated_specific_consumption_calc}; "
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
        f"Рассчитано удельных показателей (y_calc, btp_calc, sntp_calc, bk_calc): {updated_specific_consumption_calc}. "
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
        "updated_specific_consumption_calc": updated_specific_consumption_calc,
        "errors_count": len(errors),
        "report_bytes": report_bytes,
    }

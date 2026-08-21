#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сервис загрузки EquipmentGroupFuelParam из Excel (v2)."""

from __future__ import annotations

import logging
import re
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import pandas as pd
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.logs.services.logging_service import log_to_db
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.external_mapping.fue_em_equipment_group_model import (
    EquipmentGroupExternalMapping,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
    FUEL_PARAM_LABELS,
    MAIN_PARAM_LABELS,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_write_services import (
    sanitize_equipment_group_fuel_param_foreign_keys,
)
from app.refdata.models.years.year_model import Year


def _get_logger():
    try:
        from flask import has_app_context, current_app
        if has_app_context():
            return current_app.logger
    except Exception:
        pass
    return logging.getLogger(__name__)


def _normalize_column_name(col) -> str:
    s = "" if col is None else str(col)
    s = s.replace("\r", " ").replace("\n", " ").strip().lower()
    s = s.replace("е", "е")
    s = " ".join(s.split())
    s = s.replace(" ", "_")
    s = "".join(ch for ch in s if ch.isalnum() or ch == "_")
    s = "_".join(filter(None, s.split("_")))
    return s


EQUIPMENT_GROUP_FUEL_PARAM_FIELDS = [
    "name", "obor", "ved", "ved_cyrillic", "obl", "dep", "oes", "ees", "er", "gk", "be",
    "numb1120", "numb1",
    "nust", "nr", "h", "hfix", "e", "eotp", "eurt", "eust", "q", "turt", "tust", "b",
    "gaz", "isk_gaz", "mazut", "torf", "slan", "proch", "ugol", "don", "podm", "pech",
    "arkt", "kuzn", "ural", "bashk", "kazah", "kan", "tung", "irkut", "hak", "tuv",
    "bur", "chit", "yakut", "amur", "urg", "ushum", "prim", "mag", "chukot", "kamch", "sah",
    "qotr", "sn_ee", "snk", "sn_te", "sn_t", "ewtp", "nt", "nt_sum",
]

INTEGER_FIELDS = frozenset([
    "obor", "ved", "ved_cyrillic", "ees",
    "numb1120", "numb1", "hfix",
])

STRING_FIELDS = frozenset([
    "obl", "dep", "oes", "er", "gk", "be",
])

NUMERIC_FIELDS = frozenset([
    "nust", "nr", "h", "e", "eotp", "eurt", "eust", "q", "turt", "tust", "b",
    "gaz", "isk_gaz", "mazut", "torf", "slan", "proch", "ugol", "don", "podm", "pech",
    "arkt", "kuzn", "ural", "bashk", "kazah", "kan", "tung", "irkut", "hak", "tuv",
    "bur", "chit", "yakut", "amur", "urg", "ushum", "prim", "mag", "chukot", "kamch", "sah",
    "qotr", "sn_ee", "snk", "sn_te", "sn_t", "ewtp", "nt", "nt_sum",
])

COLUMN_ALIASES = {
    "numb1120": ["numb1120", "num1120", "номер1120", "numb", "ном1120", "agr_numb1120", "topl_agr_numb1120"],
    "ved_cyrillic": ["вед", "ved_cyrillic"],
    "h": ["h", "часы", "hours", "ччиум", "ччиум_ч"],
    "hfix": [
        "hfix",
        "h_fix",
        "фиксированные_часы",
        "фиксация_часов",
        "признак_фиксации_ччиум",
        "признак фиксации ччиум",
    ],
    "sn_ee": [
        "sn_ee",
        "snee",
        "sn ee",
        "с н.ээ",
        "с.н.ээ",
        "с_нээ",
        "снээ",
        "с н ээ",
        "с.н ээ",
        "сн на производство электроэнергии",
        "сн на производство электроэнергии, тыс. квтч",
        "сн на производство электроэнергии, тыс. квт·ч",
    ],
    "sn_te": [
        "sn_te",
        "snte",
        "sn te",
        "с.н. тыс.квтч",
        "с.н. тыс.кВтч",
        "сн_тысквтч",
        "с.н. тепла",
        "сн на отпуск тепловой энергии",
        "сн на отпуск тепловой энергии, тыс. квтч",
        "сн на отпуск тепловой энергии, тыс. квт·ч",
    ],
    "sn_t": ["sn_t", "snt", "sn t"],
    # В выгрузках БД Топливо столбец часто без подчёркивания: NTsum → ntsum
    "nt_sum": ["nt_sum", "ntsum", "nt sum", "n_t_sum"],
    "snk": ["snk"],
    # Старые подписи экспорта / Access («Отпуск ээ», «Отпуск эл.эн.»).
    "eotp": ["eotp", "отпуск ээ", "отпуск эл.эн", "отпуск эл.эн.", "отпуск ээ, тыс.квтч"],
    # Старые подписи экспорта («Отпуск, Гкал», «Отпуск тепл.эн.»).
    "q": ["q", "отпуск тэ", "отпуск тэ, тыс.гкал", "отпуск, гкал", "отпуск тепл.эн", "отпуск тепл.эн.", "отпуск тепла"],
    "equipment_group_id": ["equipment_group_id", "eq_group_id", "id_equipment_group"],
    "equipment_group_set_station_id": [
        "equipment_group_set_station_id", "eq_group_station_id", "link_id", "linkid",
    ],
    "station_id": ["station_id", "id_station", "id_станции"],
    "equipment_group_type_id": ["equipment_group_type_id", "equipment_group_id", "group_type_id", "id_group_type"],
    "equipment_group_type": ["equipment_group_type", "group_type", "type_name", "название_типа", "тип_группы"],
    "station_external_code": ["station_external_code", "station_code", "код_станции", "external_code"],
    "station_name": ["station_name", "stname", "название_станции", "наименование_станции"],
    "year_number": ["year_number", "year", "год"],
    "qotr": [
        "qotr",
        "тепловое потребление",
        "тепловое потребление (отборов турбин)",
        "тепловое потребление (отборов турбин), тыс.гкал",
    ],
    "turt": [
        "turt",
        "урут",
        "урут на отпуск тэ",
        "урут на отпуск тэ, кг ут/гкал",
        "урут на отпуск тэ, кг у.т./гкал",
    ],
}

# Маркерные столбцы «Доп_угли» (EquipmentGroupExtraFuelParam) vs «Станции» (основные параметры).
_EXTRA_FUEL_MARKER_COLS = frozenset({"gaz_prir", "nazar", "kuzngd", "maztop", "tvproch"})
_STATIONS_FUEL_MARKER_COLS = frozenset({"nust", "nr", "eotp", "nt", "ntsum", "nt_sum", "qotr"})
# «Сводная таблица для ОТЭТ»: абсолютные СН (sn_ee / sn_te).
_OTET_SVODNAYA_SN_EE_NORMS = frozenset({"с_нээ", "снээ", "sn_ee", "snee"})
_OTET_SVODNAYA_SN_TE_NORMS = frozenset({"сн_тысквтч", "sn_te", "snte"})
_OTET_SVODNAYA_FIELDS = ("sn_ee", "sn_te")
# Access / исходные файлы: SN_EE и SN_TE в кВт·ч; в АРМ — тыс. кВт·ч.
_SN_FILE_TO_THOUSAND_KWH = Decimal("1000")
_SN_FILE_SCALE_FIELDS = frozenset({"sn_ee", "sn_te"})


def _basename_lower(filename: str | None) -> str:
    name = (filename or "").strip().replace("\\", "/")
    name = name.rsplit("/", 1)[-1]
    return name.lower().replace("ё", "е")


def _filename_looks_like_otet_svodnaya(filename: str | None) -> bool:
    """«Сводная таблица для ОТЭТ*.xls(x)» — абсолютные СН."""
    base = _basename_lower(filename)
    if not base:
        return False
    has_svod = "сводн" in base or "svodn" in base
    has_otet = "отэт" in base or "otet" in base
    return has_svod and (has_otet or "табл" in base or "table" in base)


_UNKNOWN_FUEL_PARAMS_FILE_MSG = (
    "Загружать можно только файлы Access «Станции*.xlsx» (основные параметры), "
    "«Доп_угли*.xlsx» (детализация топлива) "
    "или «Сводная таблица для ОТЭТ*.xls(x)» (СН sn_ee / sn_te). "
    "Имя файла или столбцы листа не соответствуют этим выгрузкам."
)


def _sheet_norms_look_like_otet_svodnaya(norms: set[str]) -> bool:
    has_numb = "numb1120" in norms
    has_sn_ee = bool(norms & _OTET_SVODNAYA_SN_EE_NORMS) or any(
        "нээ" in n for n in norms
    )
    has_sn_te = bool(norms & _OTET_SVODNAYA_SN_TE_NORMS) or any(
        "тысквт" in n for n in norms
    )
    if not (has_numb and has_sn_ee and has_sn_te):
        return False
    # Не путать с полной выгрузкой «Станции».
    if norms & _STATIONS_FUEL_MARKER_COLS:
        return False
    return True


def _otet_svodnaya_header_norms_from_sheet(xls: pd.ExcelFile, sheet_name: str) -> set[str]:
    """Ищет строку шапки (NUMB1120 + СН) в первых строках листа сводной ОТЭТ."""
    raw = xls.parse(sheet_name, header=None, nrows=12)
    for i in range(len(raw)):
        vals = [
            "" if pd.isna(x) else str(x).strip()
            for x in raw.iloc[i].tolist()
        ]
        norms = {_normalize_column_name(v) for v in vals if v}
        if "numb1120" in norms and _sheet_norms_look_like_otet_svodnaya(norms):
            return norms
    return set()


def detect_fuel_params_excel_import_kind(filename: str | None, file=None) -> str | None:
    """
    Определяет тип файла для одной кнопки импорта на stations_equipment_group_fuel_params:
    - «stations» → EquipmentGroupFuelParam (Станции*.xlsx)
    - «extra» → EquipmentGroupExtraFuelParam (Доп_угли*.xlsx)
    - «otet_svodnaya» → только sn_ee / sn_te из «Сводная таблица для ОТЭТ»
    - None → файл не похож ни на один из разрешённых типов

    Сначала по имени файла, при неоднозначности — по заголовкам листа (если передан file).
    """
    base = _basename_lower(filename)
    # «Имена_станций» содержит «станци», но это soft-import COMP/MAIN/NIV — не сюда.
    is_imena = ("имен" in base and "станц" in base) or ("imena" in base and "stanci" in base)
    if _filename_looks_like_otet_svodnaya(filename):
        return "otet_svodnaya"
    if "доп" in base and "угл" in base:
        return "extra"
    if base.startswith("доп_угл") or base.startswith("допугл"):
        return "extra"
    # латиница / транслит: Dop_ugli2024.xlsx
    if "dop" in base and "ugl" in base:
        return "extra"
    if not is_imena and ("станци" in base or base.startswith("stanci")):
        return "stations"

    if file is not None:
        try:
            pos = None
            if hasattr(file, "tell"):
                try:
                    pos = file.tell()
                except Exception:
                    pos = None
            xls = pd.ExcelFile(file)
            # Сводная ОТЭТ: шапка не в первой строке, листы по годам.
            for sheet_name in xls.sheet_names[:3]:
                norms_otet = _otet_svodnaya_header_norms_from_sheet(xls, sheet_name)
                if norms_otet:
                    kind = "otet_svodnaya"
                    break
            else:
                df_head = xls.parse(xls.sheet_names[0], header=0, nrows=0)
                norms = {_normalize_column_name(c) for c in df_head.columns}
                if norms & _EXTRA_FUEL_MARKER_COLS and not (norms & _STATIONS_FUEL_MARKER_COLS):
                    kind = "extra"
                elif norms & _STATIONS_FUEL_MARKER_COLS:
                    kind = "stations"
                elif norms & _EXTRA_FUEL_MARKER_COLS:
                    kind = "extra"
                else:
                    kind = None
            if hasattr(file, "seek"):
                try:
                    file.seek(0 if pos is None else pos)
                except Exception:
                    pass
            return kind
        except Exception:
            if hasattr(file, "seek"):
                try:
                    file.seek(0)
                except Exception:
                    pass

    return None


def require_fuel_params_excel_import_kind(filename: str | None, file=None) -> str:
    """
    Как detect_fuel_params_excel_import_kind, но для неизвестного файла бросает ValueError.
    """
    kind = detect_fuel_params_excel_import_kind(filename, file=file)
    if kind not in ("stations", "extra", "otet_svodnaya"):
        raise ValueError(_UNKNOWN_FUEL_PARAMS_FILE_MSG)
    return kind


# Год в имени Access-выгрузки: Станции2023.xlsx, Доп_угли2024.xlsx.
_FILENAME_YEAR_RE = re.compile(r"(?:19|20)\d{2}")
_IMPORT_KIND_LABELS = {
    "stations": "«Станции»",
    "extra": "«Доп_угли»",
    "otet_svodnaya": "«Сводная таблица для ОТЭТ»",
}


def extract_year_from_fuel_params_import_filename(filename: str | None) -> int | None:
    """Год из имени файла (Станции2023.xlsx → 2023). Нет года в имени — None."""
    base = _basename_lower(filename)
    if not base:
        return None
    stem = base.rsplit(".", 1)[0]
    found = _FILENAME_YEAR_RE.findall(stem)
    if not found:
        return None
    return int(found[-1])


def resolve_fuel_params_import_year(filename: str | None, fallback_year: int) -> int:
    """
    Год загрузки: из имени файла (Станции2023.xlsx → 2023), иначе год фильтра.
    Несколько файлов (Станции2018.xlsx … Станции2024.xlsx) кладутся каждый в свой год.
    """
    file_year = extract_year_from_fuel_params_import_filename(filename)
    if file_year is not None:
        return int(file_year)
    return int(fallback_year)


def fuel_params_import_year_mismatch_message(
    filename: str | None,
    selected_year: int,
    import_kind: str | None = None,
) -> str | None:
    """
    Текст предупреждения, если год в имени файла не совпадает с годом фильтра.
    Импорт по кнопке больше не блокирует такое расхождение: год берётся из имени.
    Нет года в имени или годы совпадают — None.
    """
    file_year = extract_year_from_fuel_params_import_filename(filename)
    if file_year is None or int(file_year) == int(selected_year):
        return None
    kind_label = _IMPORT_KIND_LABELS.get(import_kind or "", "файла")
    return (
        f"Год в имени файла ({file_year}) не совпадает с выбранным годом на странице "
        f"({selected_year}). Чтобы загрузить данные за {file_year}, выберите этот год "
        f"в фильтре. Загрузка {kind_label} отменена."
    )


def _apply_column_aliases(df: pd.DataFrame) -> pd.DataFrame:
    alias_to_canonical = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            alias_to_canonical[_normalize_column_name(a)] = canonical
    for field in EQUIPMENT_GROUP_FUEL_PARAM_FIELDS:
        alias_to_canonical[_normalize_column_name(field)] = field
    # Заголовки экспорта (русские подписи) — как в export_stations_equipment_group_fuel_params
    for field, label in {**MAIN_PARAM_LABELS, **FUEL_PARAM_LABELS}.items():
        if field in EQUIPMENT_GROUP_FUEL_PARAM_FIELDS:
            alias_to_canonical[_normalize_column_name(label)] = field

    rename_map = {}
    for col in df.columns:
        norm = _normalize_column_name(col)
        canonical = alias_to_canonical.get(norm) or (
            norm if norm in EQUIPMENT_GROUP_FUEL_PARAM_FIELDS else None
        )
        if canonical and canonical not in rename_map.values():
            rename_map[col] = canonical
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def _extract_cell_value(row, field: str):
    val = row.get(field)
    if isinstance(val, pd.Series):
        for v in val:
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                if isinstance(v, str) and not v.strip():
                    continue
                return v
        return None
    return val


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
    except (ValueError, InvalidOperation):
        pass
    return None


def _safe_decimal(value, max_digits: int = 6) -> Decimal | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, str):
        s = value.strip().replace("\u00a0", " ").replace("\xa0", " ")
        s = "".join(ch for ch in s if ch != " ")
        if not s or s.lower() in ("nan", "—", "-", "–"):
            return None
    try:
        if isinstance(value, Decimal):
            dec_val = value
        elif isinstance(value, (int, float)):
            dec_val = Decimal(str(value))
        elif isinstance(value, str):
            dec_val = Decimal(value.strip().replace(",", "."))
        else:
            dec_val = Decimal(str(value))

        if isinstance(value, str):
            s = value.strip().replace(",", ".")
            if "." in s:
                frac = s.split(".", 1)[1].rstrip("0")
                scale = len(frac)
            else:
                scale = 0
            scale = min(scale, max_digits)
        else:
            raw_scale = -dec_val.as_tuple().exponent if dec_val.as_tuple().exponent < 0 else 0
            scale = min(raw_scale, max_digits)

        if scale <= 0:
            return dec_val.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        quant = Decimal("1." + "0" * scale)
        return dec_val.quantize(quant, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _scale_sn_from_file(value) -> Decimal | None:
    """СН из файла: исходные кВт·ч → тыс. кВт·ч (делить на 1000)."""
    val = _safe_decimal(value)
    if val is None:
        return None
    return val / _SN_FILE_TO_THOUSAND_KWH


def _safe_str(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    return s if s else None


def _numb1120_for_match(value) -> str | None:
    """Нормализует numb1120 для сопоставления с EquipmentGroup.numb (строка)."""
    n = _safe_int(value)
    if n is not None:
        return str(n)
    return _safe_str(value)


def _year_number_from_stations_row(row, fallback_year: int) -> int | None:
    """Год строки Access «Станции(Схема).Year»; иначе год из имени файла / фильтра."""
    raw = _extract_cell_value(row, "year_number")
    if raw is None:
        raw = _extract_cell_value(row, "year")
    parsed = _safe_int(raw)
    if parsed is not None:
        return parsed
    try:
        return int(fallback_year)
    except (TypeError, ValueError):
        return None


def _qotr_from_stations_row(row):
    """QOTR из строки; пустая ячейка — None."""
    return _safe_decimal(_extract_cell_value(row, "qotr"))


def _cell_is_empty(raw) -> bool:
    if raw is None:
        return True
    if isinstance(raw, float) and pd.isna(raw):
        return True
    if isinstance(raw, str) and not str(raw).strip():
        return True
    return False


def _access_code_as_str(raw) -> str | None:
    """OES/OBL из Access: 1 → «1», без FK-справочника (DEP туда не пишем)."""
    if _cell_is_empty(raw):
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return str(raw)
    if isinstance(raw, float):
        if raw.is_integer():
            return str(int(raw))
        return str(raw).strip() or None
    s = str(raw).strip()
    if not s or s.lower() in ("nan", "—", "-", "–"):
        return None
    try:
        f = float(s.replace(",", "."))
        if f.is_integer():
            return str(int(f))
    except (TypeError, ValueError):
        pass
    return s


# Входы Коэфф / Распред / Топливо из «Станции(Схема)». Не берём DEP (ломает FK),
# не берём рассчитанные B/GAZ/EURT/EUST/TUST — их пишет этап «Топливо».
# TURT — вход TUST = Q·TURT/1000, не результат Топливо.
_STATIONS_SCHEMA_CALC_FIELDS: tuple[str, ...] = (
    "name",
    "ved",
    "ved_cyrillic",
    "obor",
    "oes",
    "obl",
    "nust",
    "nr",
    "h",
    "hfix",
    "q",
    "qotr",
    "turt",
    "nt",
    "nt_sum",
    "e",
    "ewtp",
    "snk",
)
_STATIONS_SCHEMA_INT_FIELDS = frozenset({"ved", "ved_cyrillic", "obor", "hfix"})
_STATIONS_SCHEMA_STR_FIELDS = frozenset({"name", "oes", "obl"})


def _stations_schema_field_value(field: str, raw):
    if field in _STATIONS_SCHEMA_INT_FIELDS:
        return _safe_int(raw)
    if field in _STATIONS_SCHEMA_STR_FIELDS:
        if field == "name":
            return _safe_str(raw)
        return _access_code_as_str(raw)
    return _safe_decimal(raw)


def _stations_schema_row_values(row, columns) -> dict:
    """Поля расчёта из строки файла. Пустая ячейка → None (как в Access). DEP игнорируется."""
    col_set = set(columns)
    out = {}
    for field in _STATIONS_SCHEMA_CALC_FIELDS:
        if field not in col_set:
            continue
        out[field] = _stations_schema_field_value(field, _extract_cell_value(row, field))
    return out


def _obor_if_mapped(obor: int | None) -> int | None:
    """OBOR пишем только если код есть в справочнике типов ГО — иначе FK валит весь файл."""
    if obor is None:
        return None
    cache = getattr(_obor_if_mapped, "_codes", None)
    if cache is None:
        rows = EquipmentGroupExternalMapping.query.with_entities(
            EquipmentGroupExternalMapping.code
        ).all()
        cache = {int(c) for (c,) in rows if c is not None}
        _obor_if_mapped._codes = cache
    try:
        code = int(obor)
    except (TypeError, ValueError):
        return None
    return code if code in cache else None


def _get_existing_equipment_group_fuel_param(
    equipment_group_id: int,
    year_number: int,
) -> EquipmentGroupFuelParam | None:
    return (
        EquipmentGroupFuelParam.query.filter_by(
            equipment_group_id=int(equipment_group_id),
            year_number=int(year_number),
        ).first()
    )


def _resolve_equipment_groups_from_row(row):
    """
    Возвращает список (equipment_group_id, database_version_id) для строки.
    Сопоставление по numb1120 и копиям с тем же external_code во всех версиях БД.
    equipment_group_id обязателен — строки без ГО не создаём.
    """
    from app.fuel.services.fuel_imports.fuel_import_all_versions import (
        resolve_equipment_group_import_targets,
    )

    return resolve_equipment_group_import_targets(
        _extract_cell_value(row, "numb1120"),
        fill_missing_versions=False,
        require_group_match=True,
    )


def _get_or_create_equipment_group_fuel_param(
    equipment_group_id: int,
    year: int,
    eg_database_version_id: int | None,
) -> tuple[EquipmentGroupFuelParam, bool]:
    """
    Одна строка на (группу, год) — так задан uq_equipment_group_fuel_param_group_year.

    Не фильтруем по database_version_id: иначе существующая строка с другой версией
    не находится, и INSERT падает с UniqueViolation.
    """
    eg_id = int(equipment_group_id)
    year_number = int(year)
    param = (
        EquipmentGroupFuelParam.query.filter_by(
            equipment_group_id=eg_id,
            year_number=year_number,
        ).first()
    )
    if param is not None:
        if param.database_version_id is None and eg_database_version_id is not None:
            param.database_version_id = eg_database_version_id
        return param, False

    param = EquipmentGroupFuelParam(
        equipment_group_id=eg_id,
        year_number=year_number,
        database_version_id=eg_database_version_id,
    )
    try:
        with db.session.begin_nested():
            db.session.add(param)
            db.session.flush()
        return param, True
    except IntegrityError:
        param = (
            EquipmentGroupFuelParam.query.filter_by(
                equipment_group_id=eg_id,
                year_number=year_number,
            ).first()
        )
        if param is None:
            raise
        if param.database_version_id is None and eg_database_version_id is not None:
            param.database_version_id = eg_database_version_id
        return param, False


def import_equipment_group_fuel_params_from_excel(file, user: str, year: int) -> dict:
    """
    Access «Станции(Схема)»: входы расчёта по NUMB1120 и году.

    Пишет: ved, obor, oes, obl, nust, nr, h, hfix, q, qotr, turt, nt, nt_sum, e, ewtp, snk, name.
    Пустая ячейка в файле очищает поле в ТЭП (чтобы QOTR с базового года не оставался).
    Не пишет DEP и виды топлива (B/GAZ/TUST/…) — DEP ломает справочник, топливо считает этап.

    Год — из столбца Year, иначе из имени файла / фильтра страницы.
    Нет строки ТЭП — создаётся.
    """
    logger = _get_logger()
    t0 = time.perf_counter()
    filename = getattr(file, "filename", None)

    logger.info(
        "[IMPORT_EQUIPMENT_GROUP_FUEL_PARAMS_V2] start stations-schema-calc "
        "user=%s filename=%s year=%s",
        user, filename, year,
    )

    xls = pd.ExcelFile(file)
    sheet_name = xls.sheet_names[0]
    df = xls.parse(sheet_name, header=0)
    df = df.dropna(how="all")
    df = _apply_column_aliases(df)

    created = 0
    updated = 0
    skipped_no_match = 0
    skipped_no_year = 0

    for _index, row in df.iterrows():
        if row.isnull().all():
            continue

        year_number = _year_number_from_stations_row(row, year)
        if year_number is None:
            skipped_no_year += 1
            continue

        equipment_groups = _resolve_equipment_groups_from_row(row)
        if not equipment_groups:
            skipped_no_match += 1
            continue

        values = _stations_schema_row_values(row, df.columns)
        if not values:
            continue
        if "obor" in values:
            values["obor"] = _obor_if_mapped(values["obor"])

        for equipment_group_id, eg_database_version_id in equipment_groups:
            param, was_created = _get_or_create_equipment_group_fuel_param(
                equipment_group_id, year_number, eg_database_version_id
            )
            changed = False
            for field, val in values.items():
                if not hasattr(param, field):
                    continue
                if getattr(param, field) != val:
                    setattr(param, field, val)
                    changed = True
            if sanitize_equipment_group_fuel_param_foreign_keys(param):
                changed = True
            if was_created:
                created += 1
            elif changed:
                updated += 1

    try:
        if created or updated:
            db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        logger.exception("[IMPORT_EQUIPMENT_GROUP_FUEL_PARAMS_V2] db error: %s", exc)
        raise ValueError("Ошибка сохранения данных: проверьте корректность файла.") from exc

    elapsed = time.perf_counter() - t0
    fields_label = ", ".join(_STATIONS_SCHEMA_CALC_FIELDS)
    message = (
        "Из «Станции(Схема)» загружены входы расчёта ({fields}) по NUMB1120 и году. "
        "Создано: {created}, обновлено: {updated}, "
        "пропущено (нет numb): {skipped_no_match}."
    ).format(
        fields=fields_label,
        created=created,
        updated=updated,
        skipped_no_match=skipped_no_match,
    )
    logger.info(
        "[IMPORT_EQUIPMENT_GROUP_FUEL_PARAMS_V2] done stations-schema-calc "
        "created=%s updated=%s skipped=%s skipped_no_year=%s elapsed=%.2fs",
        created, updated, skipped_no_match, skipped_no_year, elapsed,
    )
    log_to_db(user, "Загрузка входов расчёта из Станции(Схема)", message)
    return {
        "message": message,
        "created": created,
        "updated": updated,
        "skipped": skipped_no_match,
        "skipped_no_year": skipped_no_year,
    }


def _find_otet_svodnaya_year_sheet(xls: pd.ExcelFile, year: int) -> str:
    """Лист сводной ОТЭТ с именем года («2024», «2015 » и т.п.)."""
    year_s = str(int(year))
    for name in xls.sheet_names:
        if str(name).strip() == year_s:
            return name
    available = ", ".join(repr(str(n).strip()) for n in xls.sheet_names)
    raise ValueError(
        f"В файле «Сводная таблица для ОТЭТ» нет листа за {year_s}. "
        f"Доступные листы: {available}."
    )


def _load_otet_svodnaya_sn_dataframe(xls: pd.ExcelFile, sheet_name: str) -> pd.DataFrame:
    """
    Читает лист сводной: Наименование | С н.ээ | С.н. тыс.кВтч | NUMB1120.
    Возвращает DataFrame с колонками numb1120, sn_ee, sn_te.
    """
    raw = xls.parse(sheet_name, header=None)
    header_idx = None
    header_vals: list[str] = []
    for i in range(min(20, len(raw))):
        vals = [
            "" if pd.isna(x) else str(x).strip()
            for x in raw.iloc[i].tolist()
        ]
        norms = [_normalize_column_name(v) for v in vals]
        if "numb1120" not in norms:
            continue
        if _sheet_norms_look_like_otet_svodnaya(set(n for n in norms if n)):
            header_idx = i
            header_vals = vals
            break
    if header_idx is None:
        raise ValueError(
            f"На листе «{sheet_name}» не найдена шапка "
            "«С н.ээ / С.н. тыс.кВтч / NUMB1120»."
        )

    alias_to_canonical = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            alias_to_canonical[_normalize_column_name(a)] = canonical
    for field in ("numb1120", "sn_ee", "sn_te", "name"):
        alias_to_canonical[_normalize_column_name(field)] = field
    for field, label in FUEL_PARAM_LABELS.items():
        if field in ("sn_ee", "sn_te", "numb1120"):
            alias_to_canonical[_normalize_column_name(label)] = field

    col_map: dict[int, str] = {}
    used: set[str] = set()
    for idx, val in enumerate(header_vals):
        if not val:
            continue
        canonical = alias_to_canonical.get(_normalize_column_name(val))
        if canonical and canonical not in used:
            col_map[idx] = canonical
            used.add(canonical)

    if "numb1120" not in used:
        raise ValueError(f"На листе «{sheet_name}» нет столбца NUMB1120.")
    if "sn_ee" not in used and "sn_te" not in used:
        raise ValueError(
            f"На листе «{sheet_name}» нет столбцов СН (С н.ээ / С.н. тыс.кВтч)."
        )

    rows = []
    for i in range(header_idx + 1, len(raw)):
        cells = raw.iloc[i].tolist()
        item = {}
        for idx, field in col_map.items():
            if idx >= len(cells):
                continue
            item[field] = cells[idx]
        numb = _numb1120_for_match(item.get("numb1120"))
        if not numb or numb.upper() == "NUMB1120":
            continue
        name_val = _safe_str(item.get("name"))
        if name_val and name_val.upper() == "NAME":
            continue
        row_out = {"numb1120": numb}
        if "sn_ee" in item:
            row_out["sn_ee"] = item.get("sn_ee")
        if "sn_te" in item:
            row_out["sn_te"] = item.get("sn_te")
        # Строка-заголовок региона без чисел СН — пропускаем, если оба СН пустые.
        sn_ee_val = _safe_decimal(row_out.get("sn_ee"))
        sn_te_val = _safe_decimal(row_out.get("sn_te"))
        if sn_ee_val is None and sn_te_val is None:
            continue
        rows.append(row_out)

    if not rows:
        raise ValueError(
            f"На листе «{sheet_name}» нет строк с NUMB1120 и значениями СН."
        )
    return pd.DataFrame(rows)


def import_otet_svodnaya_sn_from_excel(file, user: str, year: int) -> dict:
    """
    Импорт абсолютных СН из «Сводная таблица для ОТЭТ».

    Лист = выбранный год фильтра. Пишет только sn_ee / sn_te в EquipmentGroupFuelParam
    (сопоставление по numb1120 → EquipmentGroup.numb).
    """
    logger = _get_logger()
    t0 = time.perf_counter()
    filename = getattr(file, "filename", None)
    logger.info(
        "[IMPORT_OTET_SVODNAYA_SN] start user=%s filename=%s year=%s",
        user, filename, year,
    )

    if Year.query.filter_by(number=year).first() is None:
        raise ValueError(
            f"Год {year} не найден в справочнике gs_sys_years. "
            "Добавьте год в справочник или выберите другой год."
        )

    xls = pd.ExcelFile(file)
    sheet_name = _find_otet_svodnaya_year_sheet(xls, year)
    df = _load_otet_svodnaya_sn_dataframe(xls, sheet_name)

    created = 0
    updated = 0
    skipped_no_match = 0
    skipped_no_year = 0
    skipped_empty = 0

    for _, row in df.iterrows():
        equipment_groups = _resolve_equipment_groups_from_row(row)
        if not equipment_groups:
            skipped_no_match += 1
            continue

        row_values = {}
        for field in _OTET_SVODNAYA_FIELDS:
            if field not in df.columns:
                continue
            val = _scale_sn_from_file(_extract_cell_value(row, field))
            if val is not None:
                row_values[field] = val
        if not row_values:
            skipped_empty += 1
            continue

        for equipment_group_id, eg_database_version_id in equipment_groups:
            year_query = Year.query.filter_by(number=year)
            if eg_database_version_id is not None:
                year_query = year_query.filter_by(database_version_id=eg_database_version_id)
            else:
                year_query = year_query.filter(Year.database_version_id.is_(None))
            if year_query.first() is None:
                skipped_no_year += 1
                continue

            param, was_created = _get_or_create_equipment_group_fuel_param(
                equipment_group_id, year, eg_database_version_id
            )
            if was_created:
                created += 1

            changed = False
            for field, val in row_values.items():
                cur = getattr(param, field, None)
                if cur != val:
                    setattr(param, field, val)
                    changed = True
            if changed:
                updated += 1

    try:
        if created or updated:
            db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        logger.exception("[IMPORT_OTET_SVODNAYA_SN] db error: %s", exc)
        raise ValueError("Ошибка сохранения данных: проверьте корректность файла.") from exc

    elapsed = time.perf_counter() - t0
    message = (
        f"Лист «{sheet_name}»: создано записей: {created}, обновлено: {updated}, "
        f"пропущено (нет numb): {skipped_no_match}, "
        f"пропущено (нет года в версии): {skipped_no_year}, "
        f"пропущено (пустые СН): {skipped_empty}."
    )
    logger.info(
        "[IMPORT_OTET_SVODNAYA_SN] done sheet=%s created=%s updated=%s skipped=%s "
        "skipped_no_year=%s skipped_empty=%s elapsed=%.2fs",
        sheet_name, created, updated, skipped_no_match, skipped_no_year, skipped_empty, elapsed,
    )
    log_to_db(user, "Загрузка СН из сводной ОТЭТ", message)
    return {
        "message": message,
        "created": created,
        "updated": updated,
        "skipped": skipped_no_match,
        "skipped_no_year": skipped_no_year,
        "skipped_empty": skipped_empty,
        "sheet_name": sheet_name,
    }

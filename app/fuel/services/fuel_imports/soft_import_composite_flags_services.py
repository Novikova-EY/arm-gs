# -*- coding: utf-8 -*-
"""
Мягкая дозагрузка Access «Имена_станций» → существующие EquipmentGroup по numb.

Режим C + опциональный phase B:
1) обновить у уже существующих EG по numb:
   флаги comp/main/niv и словарные поля (d, r, name_ext, vedomstvo, be, gk,
   gkf, er, n1/n2, p1/p2, addr, codegor, note, …);
   поле name (название в АРМ после объединения) не перезаписывается —
   Excel NAME / name_ext → name_ext;
2) Phase A — родители для семей, где дети уже есть в АРМ (по database_version_id);
3) Phase B — COMP=1 без детей (архив/отменённые планы): только если явно
   create_phase_b_parents=True / галка «Включая phase B»; по умолчанию выкл,
   в отчёте показывается как отложенное.
4) Отсутствующие NUMB — создать непривязанные EG в текущей версии БД:
   create_missing_numbs=True / галка «Создать отсутствующие NUMB».

Гарантии безопасности:
- по умолчанию dry_run=True (только отчёт, без commit);
- не трогает агрегаты / MachineFuelParam;
- не создаёт группы из id_station / id_machine (это синяя «Импорт из Excel»);
- пустые ячейки словарных полей не затирают значения в БД;
- после записи синхронизирует FuelParam.ved=0 у родителей.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.logs.services.logging_service import log_to_db

logger = logging.getLogger(__name__)

_SOFT_FIELDS = ("comp", "main", "niv")

# Доп. поля Excel → meta родителя и дозагрузка существующих EG (нормализованные имена).
_PARENT_META_FIELDS = (
    "name",
    "name_ext",
    "niv",
    "comp",
    "d",
    "r",
    "forem",
    "vedomstvo",
    "obl",
    "dep",
    "oes",
    "er",
    "fo",
    "tm",
    "addr",
    "note",
    "codegor",
    "be",
    "gk",
    "gkf",
    "ordnumb",
    "n1",
    "n2",
    "p1",
    "p2",
)

# Словарные поля, которые дозагружаем в уже существующие EG по numb.
_DICT_INT_FIELDS = (
    "d",
    "r",
    "forem",
    "vedomstvo",
    "obl",
    "dep",
    "oes",
    "er",
    "fo",
    "codegor",
    "be",
    "gk",
    "gkf",
)
_DICT_TEXT_FIELDS = ("tm", "addr", "note", "ordnumb", "n1", "n2", "p1", "p2")
_DICT_TEXT_MAXLEN = {"note": 1000}
_META_TEXT_FIELDS = frozenset(
    {"name", "name_ext", "tm", "addr", "note", "ordnumb", "n1", "n2", "p1", "p2"}
)


def _normalize_column_name(name: object) -> str:
    if name is None:
        return ""
    text = str(name).strip().lower().replace("ё", "е")
    out = []
    for ch in text:
        if ch.isalnum() or ch in ("_",):
            out.append(ch)
        elif ch.isspace() or ch in ("-", ".", "/", "\\"):
            out.append("_")
    return "_".join(p for p in "".join(out).split("_") if p)


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text or text in {"—", "-", "None", "null", "NULL"}:
            return None
        value = text
    try:
        as_float = float(value)
        if as_float != as_float:  # NaN
            return None
        return int(as_float)
    except (TypeError, ValueError):
        return None


def _numb_key(value: Any) -> str | None:
    n = _safe_int(value)
    if n is None:
        return None
    return str(n)


def _meta_text_value(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return str(int(raw))
    if isinstance(raw, float):
        if pd.isna(raw):
            return None
        if raw == int(raw):
            return str(int(raw))
        text = str(raw).strip()
        return text or None
    if isinstance(raw, int):
        return str(raw)
    if not isinstance(raw, str) and pd.isna(raw):
        return None
    text = str(raw).strip()
    return text or None


def _dict_updates_from_meta(eg: Any, meta: dict[str, Any] | None) -> dict[str, Any]:
    """Excel → существующая EG. Пустые ячейки не затирают БД. NAME → name_ext."""
    changes: dict[str, Any] = {}
    if not meta:
        return changes

    excel_title = meta.get("name_ext") or meta.get("name")
    if excel_title:
        new_ext = str(excel_title).strip()[:255]
        if new_ext and (getattr(eg, "name_ext", None) or "") != new_ext:
            changes["name_ext"] = new_ext

    for f in _DICT_INT_FIELDS:
        if f not in meta:
            continue
        v = meta[f]
        if v is None:
            continue
        if getattr(eg, f, None) != v:
            changes[f] = v

    for f in _DICT_TEXT_FIELDS:
        if f not in meta:
            continue
        v = meta[f]
        if v is None or v == "":
            continue
        maxlen = _DICT_TEXT_MAXLEN.get(f, 255)
        text = str(v).strip()[:maxlen]
        if not text:
            continue
        if (getattr(eg, f, None) or "") != text:
            changes[f] = text
    return changes


def _norm_title(value: Any) -> str:
    """Сжатое имя для сопоставления Access NAME ↔ группа/станция АРМ."""
    if value is None:
        return ""
    text = str(value).strip().lower().replace("ё", "е")
    out = []
    for ch in text:
        if ch.isalnum() or ch.isspace():
            out.append(ch)
        else:
            out.append(" ")
    return " ".join("".join(out).split())


def _names_related(a: Any, b: Any) -> bool:
    na, nb = _norm_title(a), _norm_title(b)
    if not na or not nb:
        return True
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return True
    return len(ta & tb) >= min(2, len(ta), len(tb))


def _imena_header_row_index(xls: pd.ExcelFile, sheet_name: str) -> int:
    preview = xls.parse(sheet_name, header=None, nrows=12)
    markers = {"numb", "numb1120", "код", "код_станции", "num"}
    extra = {
        "comp",
        "main",
        "niv",
        "d",
        "r",
        "name",
        "наименование",
        "название",
        "vedomstvo",
        "ведомство",
    }
    for try_row in range(min(10, len(preview))):
        norms: set[str] = set()
        for c in preview.iloc[try_row]:
            if pd.notna(c) and str(c).strip():
                norms.add(_normalize_column_name(c))
        if norms & markers:
            return try_row
        if len(norms & extra) >= 2:
            return try_row
    return 0


def _read_imena_dataframe(file) -> pd.DataFrame:
    xls = pd.ExcelFile(file)
    sheet_name = xls.sheet_names[0]
    header_row = _imena_header_row_index(xls, sheet_name)
    df = xls.parse(sheet_name, header=header_row)
    df = df.dropna(how="all")
    rename = {}
    for col in list(df.columns):
        norm = _normalize_column_name(col)
        if (
            norm in {"numb", "num", "код", "код_станции", "numb1120"}
            or ("numb" in norm and ("код" in norm or "групп" in norm))
        ):
            rename[col] = "numb"
        elif norm in {"comp", "topl_comp"}:
            rename[col] = "comp"
        elif norm in {"main", "topl_main"}:
            rename[col] = "main"
        elif norm in {"niv", "topl_niv"}:
            rename[col] = "niv"
        elif norm in {"name", "наименование", "имя", "название"}:
            rename[col] = "name"
        elif norm in {"name_ext", "topl_name", "название_бд_топливо"}:
            rename[col] = "name_ext"
        elif norm in {
            "vedomstvo",
            "ведомство",
        } or norm.startswith("ведомство"):
            rename[col] = "vedomstvo"
        elif norm in {"forem", "форэм", "форем"}:
            rename[col] = "forem"
        elif norm in {"примечание", "note", "prim"}:
            rename[col] = "note"
        elif norm in {"ordnumb", "ord_numb"}:
            rename[col] = "ordnumb"
        elif norm in {"n1", "n2", "p1", "p2"}:
            rename[col] = norm
        elif "мощность_блока" in norm and ("1" in norm or "вар_1" in norm):
            rename[col] = "n1"
        elif "мощность_блока" in norm and ("2" in norm or "вар_2" in norm):
            rename[col] = "n2"
        elif "давление_пара" in norm and ("1" in norm or "вар_1" in norm):
            rename[col] = "p1"
        elif "давление_пара" in norm and ("2" in norm or "вар_2" in norm):
            rename[col] = "p2"
        elif norm in {
            "d",
            "признак_действующей",
            "признак_действующей_электростанции",
        } or (norm.startswith("признак_действующей") and "d" in norm):
            rename[col] = "d"
        elif norm in {
            "r",
            "признак_расширяемой",
            "признак_расширяемой_электростанции",
        } or (norm.startswith("признак_расширяемой") and "r" in norm):
            rename[col] = "r"
        elif norm in {"addr", "адрес"}:
            rename[col] = "addr"
        elif norm in {"codegor", "код_города"}:
            rename[col] = "codegor"
        elif norm in {"be", "тип_генерирующей_компании"} or (
            "тип_генерирующей" in norm and "be" in norm
        ):
            rename[col] = "be"
        elif norm in {"gkf", "филиал_генерирующей_компании"} or (
            "филиал" in norm and "gkf" in norm
        ):
            rename[col] = "gkf"
        elif norm in {"gk", "генерирующая_компания"} or (
            "генерирующая_компания" in norm and "gk" in norm and "филиал" not in norm
        ):
            rename[col] = "gk"
        elif norm in {"er", "экономический_район"} or (
            "экономический_район" in norm
        ):
            rename[col] = "er"
        elif norm in {
            "obl",
            "dep",
            "oes",
            "fo",
            "tm",
        }:
            rename[col] = norm
    if rename:
        df = df.rename(columns=rename)
    for key in ("numb", "comp", "main", "niv", "name", *_PARENT_META_FIELDS):
        cols = [c for c in df.columns if c == key]
        if len(cols) > 1:
            df = df.drop(columns=cols[1:])
    return df


def _excel_row_meta(row: pd.Series, present_meta: list[str]) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    for f in present_meta:
        if f not in row.index:
            continue
        raw = row.get(f)
        if f in _META_TEXT_FIELDS:
            text = _meta_text_value(raw)
            if text:
                meta[f] = text
        else:
            meta[f] = _safe_int(raw)
    return meta


@dataclass
class SoftCompositeFlagsResult:
    dry_run: bool
    excel_rows: int = 0
    excel_unique_numb: int = 0
    matched_numb: int = 0
    skipped_no_numb: int = 0
    skipped_not_in_db: int = 0
    matched_by_name: int = 0
    eg_without_numb: int = 0
    name_mismatch_warnings: int = 0
    eg_rows_would_update: int = 0
    eg_rows_updated: int = 0
    eg_rows_unchanged: int = 0
    parent_shells_would_create: int = 0
    parent_shells_created: int = 0
    parent_shells_unique_numbs: int = 0
    parent_shells_skipped_no_station: int = 0
    parent_shells_without_station: int = 0
    phase_b_would_create: int = 0
    phase_b_created: int = 0
    phase_b_unique_numbs: int = 0
    phase_b_without_station: int = 0
    phase_b_enabled: bool = False
    missing_numbs_enabled: bool = False
    missing_numbs_would_create: int = 0
    missing_numbs_created: int = 0
    missing_numbs_unique: int = 0
    deferred_comp1_no_children: int = 0
    ved_zero_synced: int = 0
    warnings: list[str] = field(default_factory=list)
    sample_updates: list[dict] = field(default_factory=list)
    sample_missing_numb: list[str] = field(default_factory=list)
    sample_parent_shells: list[dict] = field(default_factory=list)
    sample_phase_b: list[dict] = field(default_factory=list)
    sample_missing_numbs: list[dict] = field(default_factory=list)
    sample_deferred_comp1: list[dict] = field(default_factory=list)
    reconciliation_lines: list[str] = field(default_factory=list)
    message: str = ""

    def to_flash_lines(self) -> list[str]:
        mode = "ПРОВЕРКА (без записи)" if self.dry_run else "ПРИМЕНЕНО"
        lines = [
            f"[{mode}] Мягкая дозагрузка из «Имена_станций»: флаги comp/main/niv "
            f"и словарные поля (d, r, name_ext, vedomstvo, be, gk, n1, p1, addr, …) "
            f"(режим C"
            + (" + phase B" if self.phase_b_enabled else ", phase B выкл")
            + (
                " + отсутствующие NUMB"
                if self.missing_numbs_enabled
                else ", отсутствующие NUMB выкл"
            )
            + ").",
        ]
        if self.dry_run:
            lines.append(
                "Таблица на странице не изменится, пока не отметите «Применить изменения» "
                "и не загрузите файл ещё раз."
            )
        lines.extend(
            [
            (
                f"Строк Excel: {self.excel_rows}, уникальных NUMB: {self.excel_unique_numb}, "
                f"найдено в БД по numb: {self.matched_numb}, нет в БД: {self.skipped_not_in_db}, "
                f"без NUMB в файле: {self.skipped_no_numb}"
                + (
                    f", сопоставлено по названию: {self.matched_by_name}"
                    if self.matched_by_name
                    else ""
                )
                + (
                    f", групп в АРМ без numb: {self.eg_without_numb}."
                    if self.eg_without_numb
                    else "."
                )
            ),
            (
                f"Записей EG к изменению: {self.eg_rows_would_update}, "
                f"без изменений: {self.eg_rows_unchanged}"
                + (f", записано: {self.eg_rows_updated}." if not self.dry_run else ".")
            ),
            (
                f"Phase A (семьи с детьми, по версиям): "
                f"{self.parent_shells_would_create} строк / "
                f"{self.parent_shells_unique_numbs} уникальных numb"
                + (
                    f", создано: {self.parent_shells_created}."
                    if not self.dry_run
                    else "."
                )
            ),
        ]
        )
        if self.phase_b_enabled:
            lines.append(
                f"Phase B (COMP=1 без детей, по версиям словаря): "
                f"{self.phase_b_would_create} строк / "
                f"{self.phase_b_unique_numbs} уникальных numb"
                + (
                    f", создано: {self.phase_b_created}."
                    if not self.dry_run
                    else "."
                )
            )
        else:
            lines.append(
                f"Phase B отложена (галка «включая phase B» выкл): "
                f"{self.phase_b_unique_numbs} уникальных numb / "
                f"{self.phase_b_would_create} строк — не создаём "
                f"(архив/отменённые планы)."
            )
        if self.missing_numbs_enabled:
            lines.append(
                f"Отсутствующие NUMB (текущая версия, без станции): "
                f"{self.missing_numbs_would_create} строк / "
                f"{self.missing_numbs_unique} уникальных numb"
                + (
                    f", создано: {self.missing_numbs_created}."
                    if not self.dry_run
                    else "."
                )
            )
        else:
            lines.append(
                f"Отсутствующие NUMB отложены (галка выкл): "
                f"{self.missing_numbs_unique} уникальных numb / "
                f"{self.missing_numbs_would_create} строк — не создаём."
            )
        if self.parent_shells_skipped_no_station:
            lines.append(
                f"Phase A пропущено (require_station): "
                f"{self.parent_shells_skipped_no_station}."
            )
        without = self.parent_shells_without_station
        if self.phase_b_enabled:
            without += self.phase_b_without_station
        if without:
            lines.append(
                f"Родителей без Station (будут «висеть»): {without} "
                f"(A={self.parent_shells_without_station}"
                + (
                    f", B={self.phase_b_without_station}"
                    if self.phase_b_enabled
                    else ""
                )
                + ")."
            )
        if self.ved_zero_synced:
            lines.append(
                f"FuelParam.ved=0 у родителей синхронизировано строк: "
                f"{self.ved_zero_synced}."
            )
        if self.sample_missing_numb:
            lines.append(
                "Примеры NUMB из Excel, которых нет в EquipmentGroup: "
                + ", ".join(self.sample_missing_numb[:20])
                + ("…" if len(self.sample_missing_numb) > 20 else "")
            )
        if self.sample_parent_shells:
            bits = [
                f"numb={s['numb']} «{s.get('name','')}» ver={s.get('database_version_id')} "
                f"kids={s.get('child_count')} st={s.get('station_id')}"
                for s in self.sample_parent_shells[:8]
            ]
            lines.append("Примеры родителей (phase A): " + "; ".join(bits))
        if self.sample_phase_b:
            bits = [
                f"numb={s['numb']} «{s.get('name','')}» ver={s.get('database_version_id')} "
                f"st={s.get('station_id')}"
                for s in self.sample_phase_b[:8]
            ]
            label = (
                "Примеры родителей (phase B): "
                if self.phase_b_enabled
                else "Примеры отложенных COMP=1 (phase B): "
            )
            lines.append(label + "; ".join(bits))
        if self.sample_missing_numbs:
            bits = [
                f"numb={s['numb']} «{s.get('name','')}» main={s.get('main')} "
                f"ver={s.get('database_version_id')}"
                for s in self.sample_missing_numbs[:8]
            ]
            label = (
                "Примеры создаваемых NUMB: "
                if self.missing_numbs_enabled
                else "Примеры отложенных NUMB: "
            )
            lines.append(label + "; ".join(bits))
        if self.sample_updates:
            bits = []
            for u in self.sample_updates[:8]:
                parts = [f"numb={u['numb']} id={u['eg_id']}"]
                if (
                    u.get("old_comp") != u.get("new_comp")
                    or u.get("old_main") != u.get("new_main")
                    or u.get("old_niv") != u.get("new_niv")
                ):
                    parts.append(
                        f"comp {u['old_comp']}->{u['new_comp']}, "
                        f"main {u['old_main']}->{u['new_main']}, "
                        f"niv {u['old_niv']}->{u['new_niv']}"
                    )
                dict_changes = u.get("dict_changes") or {}
                if dict_changes:
                    dict_bits = [
                        f"{k} {ch.get('old')}->{ch.get('new')}"
                        for k, ch in dict_changes.items()
                    ]
                    parts.append(", ".join(dict_bits))
                bits.append(": ".join(parts) if len(parts) > 1 else parts[0])
            lines.append("Примеры изменений: " + "; ".join(bits))
        for w in self.warnings[:12]:
            lines.append("⚠ " + w)
        if len(self.warnings) > 12:
            lines.append(f"… и ещё предупреждений: {len(self.warnings) - 12}")
        lines.extend(self.reconciliation_lines[:16])
        return lines


def soft_import_composite_flags_from_imena_excel(
    file,
    user: str,
    *,
    dry_run: bool = True,
    create_missing_parents: bool = True,
    create_phase_b_parents: bool = False,
    create_missing_numbs: bool = False,
    require_station_for_parents: bool = False,
    database_version_id: int | None = None,
    session: Session | None = None,
) -> SoftCompositeFlagsResult:
    """
    Читает Access-выгрузку «Имена_станций.xlsx» и мягко дозагружает
    существующие группы по numb: флаги comp/main/niv и словарные поля.
    Не создаёт группы из id_station / id_machine и не перезаписывает name.

    dry_run=True — только отчёт, commit не делается.
    Phase A: родители для семей с детьми в АРМ (по умолчанию вкл).
    Phase B: COMP=1 без детей — только если create_phase_b_parents=True
    (по умолчанию выкл: архив/отменённые планы).
    Отсутствующие NUMB: create_missing_numbs=True — EG в текущей версии БД
    без Station (связь вручную).
    """
    t0 = time.perf_counter()
    sess = session or db.session
    result = SoftCompositeFlagsResult(
        dry_run=dry_run,
        phase_b_enabled=bool(create_phase_b_parents),
        missing_numbs_enabled=bool(create_missing_numbs),
    )

    from app.fuel.services.fuel_imports.fuel_excel_file_guard_services import (
        reject_access_stations_or_extra_fuel_excel,
    )

    reject_access_stations_or_extra_fuel_excel(
        getattr(file, "filename", None),
        file=file,
        context="soft_import",
    )

    df = _read_imena_dataframe(file)
    present_fields = [f for f in _SOFT_FIELDS if f in df.columns]
    present_meta = [f for f in _PARENT_META_FIELDS if f in df.columns]
    if "numb" not in df.columns:
        raise ValueError(
            "В файле нет колонки NUMB. Нужна выгрузка Access «Имена_станций» "
            "с полями NUMB и словарными колонками (COMP/MAIN/NIV, d, r, "
            "vedomstvo, be, gk, n1, p1, addr, …)."
        )
    if not present_fields and not present_meta:
        raise ValueError(
            "В файле нет колонок COMP / MAIN / NIV и нет словарных полей "
            "(d, r, name, vedomstvo, be, gk, n1, p1, addr, …) — нечего обновлять."
        )

    excel_by_numb: dict[str, dict[str, int | None]] = {}
    excel_meta_by_numb: dict[str, dict[str, Any]] = {}

    for _, row in df.iterrows():
        result.excel_rows += 1
        key = _numb_key(row.get("numb"))
        if key is None:
            result.skipped_no_numb += 1
            continue
        vals: dict[str, int | None] = {}
        for f in present_fields:
            vals[f] = _safe_int(row.get(f))
        if vals.get("main") == 0:
            vals["main"] = None
        excel_by_numb[key] = vals
        excel_meta_by_numb[key] = _excel_row_meta(row, present_meta)

    result.excel_unique_numb = len(excel_by_numb)

    eg_rows = (
        sess.query(EquipmentGroup)
        .filter(EquipmentGroup.numb.isnot(None))
        .all()
    )
    eg_by_numb: dict[str, list[EquipmentGroup]] = {}
    for eg in eg_rows:
        key = _numb_key(eg.numb)
        if key is None:
            continue
        eg_by_numb.setdefault(key, []).append(eg)

    db_numb_set = set(eg_by_numb.keys())
    excel_numb_set = set(excel_by_numb.keys())
    missing = sorted(
        excel_numb_set - db_numb_set, key=lambda x: int(x) if x.isdigit() else 0
    )
    result.skipped_not_in_db = len(missing)
    result.sample_missing_numb = missing[:50]
    result.matched_numb = len(excel_numb_set & db_numb_set)

    children_by_main: dict[str, list[str]] = {}
    for numb, vals in excel_by_numb.items():
        main = vals.get("main")
        if main is not None and main > 0:
            children_by_main.setdefault(str(main), []).append(numb)

    for numb, vals in excel_by_numb.items():
        main = vals.get("main")
        if main is not None and main > 0:
            main_key = str(main)
            if main_key not in excel_by_numb and main_key not in db_numb_set:
                result.warnings.append(
                    f"numb={numb}: MAIN={main} отсутствует и в Excel, и в БД."
                )

    for main_key, kids in children_by_main.items():
        if main_key in excel_by_numb and excel_by_numb[main_key].get("comp") != 1:
            result.warnings.append(
                f"У NUMB={main_key} есть дети в Excel ({len(kids)}), но COMP≠1."
            )

    updates: list[
        tuple[
            EquipmentGroup,
            dict[str, int | None],
            dict[str, int | None],
            dict[str, Any],
        ]
    ] = []
    pending_flag_updates: dict[int, dict[str, int | None]] = {}
    queued_eg_ids: set[int] = set()

    def _queue_eg_update(
        eg: EquipmentGroup,
        numb_key: str,
        new_vals: dict[str, int | None],
        meta: dict[str, Any],
        *,
        set_numb: bool = False,
    ) -> None:
        if eg.id in queued_eg_ids:
            return
        old_vals = {
            "comp": _safe_int(eg.comp),
            "main": _safe_int(eg.main)
            if _safe_int(eg.main) not in (0, None)
            else None,
            "niv": _safe_int(eg.niv),
        }
        new_norm = dict(old_vals)
        for f in present_fields:
            v = new_vals.get(f)
            if f == "main" and v == 0:
                v = None
            new_norm[f] = v
        flag_changed = old_vals != new_norm
        dict_changes = _dict_updates_from_meta(eg, meta)
        if set_numb:
            numb_int = int(numb_key)
            if _safe_int(eg.numb) != numb_int:
                dict_changes["numb"] = numb_int
        excel_name = meta.get("name_ext") or meta.get("name")
        eg_label = eg.name or eg.name_ext
        if excel_name and eg_label and not _names_related(excel_name, eg_label):
            result.name_mismatch_warnings += 1
            if len(result.warnings) < 40:
                result.warnings.append(
                    f"numb={numb_key} id={eg.id}: в Access «{str(excel_name)[:70]}», "
                    f"в АРМ «{str(eg_label)[:70]}». Код группы, скорее всего, чужой — "
                    "проверьте NUMB."
                )
        if not flag_changed and not dict_changes:
            result.eg_rows_unchanged += 1
            queued_eg_ids.add(eg.id)
            return
        updates.append((eg, old_vals, new_norm, dict_changes))
        queued_eg_ids.add(eg.id)
        if flag_changed:
            pending_flag_updates[eg.id] = new_norm
        result.eg_rows_would_update += 1
        if len(result.sample_updates) < 25:
            sample = {
                "numb": numb_key,
                "eg_id": eg.id,
                "name": (
                    eg.name
                    or eg.name_ext
                    or (meta.get("name_ext") or meta.get("name") or "")
                )[:80],
                "old_comp": old_vals["comp"],
                "new_comp": new_norm["comp"],
                "old_main": old_vals["main"],
                "new_main": new_norm["main"],
                "old_niv": old_vals["niv"],
                "new_niv": new_norm["niv"],
                "database_version_id": eg.database_version_id,
            }
            if dict_changes:
                sample["dict_changes"] = {
                    k: {"old": getattr(eg, k, None), "new": v}
                    for k, v in dict_changes.items()
                }
            result.sample_updates.append(sample)

    for numb_key, new_vals in excel_by_numb.items():
        groups = eg_by_numb.get(numb_key) or []
        if not groups:
            continue
        meta = excel_meta_by_numb.get(numb_key) or {}
        for eg in groups:
            _queue_eg_update(eg, numb_key, new_vals, meta)

    excel_name_to_numbs: dict[str, list[str]] = {}
    for numb_key, meta in excel_meta_by_numb.items():
        title = _norm_title(meta.get("name_ext") or meta.get("name"))
        if title:
            excel_name_to_numbs.setdefault(title, []).append(numb_key)

    eg_no_numb_rows = (
        sess.query(EquipmentGroup).filter(EquipmentGroup.numb.is_(None)).all()
    )
    result.eg_without_numb = len(eg_no_numb_rows)
    station_names_by_eg: dict[int, list[str]] = {}
    if eg_no_numb_rows:
        try:
            from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
            from app.fuel.models.fue_equipment_group_set_station_model import (
                EquipmentGroupSetStation,
            )
            from app.generation.models.station.station_model import Station

            no_numb_ids = [eg.id for eg in eg_no_numb_rows]
            link_rows = (
                sess.query(EquipmentGroupSet.equipment_group_id, Station.name)
                .join(
                    EquipmentGroupSetStation,
                    EquipmentGroupSet.equipment_group_set_station_id
                    == EquipmentGroupSetStation.id,
                )
                .join(Station, Station.id == EquipmentGroupSetStation.station_id)
                .filter(EquipmentGroupSet.equipment_group_id.in_(no_numb_ids))
                .all()
            )
            for eg_id, st_name in link_rows:
                if st_name:
                    station_names_by_eg.setdefault(int(eg_id), []).append(str(st_name))
        except Exception:
            logger.exception(
                "[SOFT_IMPORT_COMPOSITE_FLAGS] station names for name-match failed"
            )

    for eg in eg_no_numb_rows:
        labels = [eg.name, eg.name_ext, *(station_names_by_eg.get(eg.id) or [])]
        found: list[str] = []
        for label in labels:
            key = _norm_title(label)
            if key:
                found.extend(excel_name_to_numbs.get(key) or [])
        unique = list(dict.fromkeys(found))
        if len(unique) != 1:
            if len(unique) > 1 and len(result.warnings) < 40:
                result.warnings.append(
                    f"id={eg.id} «{(eg.name or eg.name_ext or '')[:60]}»: "
                    f"несколько NUMB по названию ({', '.join(unique[:6])}) — пропуск."
                )
            continue
        numb_key = unique[0]
        result.matched_by_name += 1
        _queue_eg_update(
            eg,
            numb_key,
            excel_by_numb.get(numb_key) or {},
            excel_meta_by_numb.get(numb_key) or {},
            set_numb=True,
        )

    if result.matched_numb == 0 and result.matched_by_name == 0:
        result.warnings.insert(
            0,
            "Ни одна группа не сопоставилась с файлом. Жёлтая загрузка ищет "
            "совпадение по NUMB (код группы в АРМ) или по точному названию. "
            "Группы без numb и без того же NAME, что в Access, остаются пустыми.",
        )

    if not dry_run:
        for eg, _old, new_norm, dict_changes in updates:
            if present_fields:
                for f in present_fields:
                    setattr(eg, f, new_norm[f])
            for f, v in dict_changes.items():
                setattr(eg, f, v)
            sess.add(eg)
            result.eg_rows_updated += 1
        sess.flush()

    from app.fuel.services.equipment_groups.composite_main_vs_station_reconciliation_services import (
        create_missing_numbs_from_excel,
        create_missing_parent_shells_from_children,
        create_phase_b_comp1_parents_from_excel,
        report_composite_vs_station_clusters,
    )
    from app.fuel.services.equipment_groups.composite_parent_ved_sync_services import (
        sync_composite_parent_ved_zero,
    )

    # Meta для создания родителей: все строки Excel (не только COMP=1).
    excel_parent_meta: dict[str, dict] = dict(excel_meta_by_numb)

    shells = None
    if create_missing_parents:
        shells = create_missing_parent_shells_from_children(
            sess,
            dry_run=dry_run,
            excel_parents=excel_parent_meta,
            pending_flag_updates=pending_flag_updates if dry_run else None,
            require_station=require_station_for_parents,
        )
        result.parent_shells_would_create = shells.created_or_planned
        result.parent_shells_unique_numbs = shells.unique_parent_numbs
        result.sample_parent_shells = shells.samples
        result.parent_shells_skipped_no_station = len(shells.skipped_no_station)
        result.parent_shells_without_station = shells.created_without_station
        result.warnings.extend(shells.warnings)
        if not dry_run:
            result.parent_shells_created = shells.created_or_planned

    # Phase B всегда считаем для отчёта; пишем только если галка вкл.
    phase_b_write = bool(create_phase_b_parents) and not dry_run
    phase_b = create_phase_b_comp1_parents_from_excel(
        sess,
        dry_run=not phase_b_write,
        excel_parents=excel_parent_meta,
    )
    result.phase_b_would_create = phase_b.created_or_planned
    result.phase_b_unique_numbs = phase_b.unique_parent_numbs
    result.phase_b_without_station = phase_b.created_without_station
    result.sample_phase_b = phase_b.samples
    if create_phase_b_parents:
        result.warnings.extend(phase_b.warnings)
    result.deferred_comp1_no_children = phase_b.unique_parent_numbs
    result.sample_deferred_comp1 = phase_b.samples
    if phase_b_write:
        result.phase_b_created = phase_b.created_or_planned

    target_ver = database_version_id
    if target_ver is None:
        try:
            from app.common.services.database_version_filter import (
                get_current_db_version_id,
            )

            target_ver = get_current_db_version_id()
        except Exception:
            target_ver = None

    excel_missing_meta: dict[str, dict] = {}
    for numb_key, meta in excel_parent_meta.items():
        merged = dict(meta)
        flags = excel_by_numb.get(numb_key) or {}
        for f in _SOFT_FIELDS:
            if f in flags:
                merged[f] = flags[f]
        excel_missing_meta[numb_key] = merged

    exclude_numbs: set[int] = set()
    if shells is not None:
        exclude_numbs |= getattr(shells, "planned_numbs", set()) or set()
    if create_phase_b_parents:
        exclude_numbs |= phase_b.planned_numbs or set()

    missing_write = bool(create_missing_numbs) and not dry_run and target_ver is not None
    if create_missing_numbs and not dry_run and target_ver is None:
        result.warnings.append(
            "Не определена текущая версия БД — отсутствующие NUMB не создаём."
        )
    missing = create_missing_numbs_from_excel(
        sess,
        dry_run=not missing_write,
        excel_rows=excel_missing_meta,
        database_version_id=target_ver,
        exclude_numbs=exclude_numbs,
    )
    result.missing_numbs_would_create = missing.created_or_planned
    result.missing_numbs_unique = missing.unique_parent_numbs
    result.sample_missing_numbs = missing.samples
    if missing_write:
        result.missing_numbs_created = missing.created_or_planned

    recon = report_composite_vs_station_clusters(sess)
    result.reconciliation_lines = recon.to_flash_lines()

    if not dry_run:
        result.ved_zero_synced = sync_composite_parent_ved_zero(sess)
        sess.commit()
        log_to_db(
            user,
            "Мягкая дозагрузка из Имена_станций (флаги + словарные поля, C + phase B)",
            (
                f"updated={result.eg_rows_updated}; matched_numb={result.matched_numb}; "
                f"missing={result.skipped_not_in_db}; "
                f"phase_a={result.parent_shells_created}; "
                f"phase_b={result.phase_b_created}; "
                f"missing_numbs={result.missing_numbs_created}; "
                f"ved0={result.ved_zero_synced}"
            ),
            entity_type="soft_import_composite_flags",
        )

    elapsed = time.perf_counter() - t0
    result.message = " | ".join(result.to_flash_lines())
    logger.info(
        "[SOFT_IMPORT_COMPOSITE_FLAGS] dry_run=%s user=%s matched=%s would_update=%s "
        "updated=%s missing=%s phase_a=%s phase_b=%s missing_numbs=%s ved0=%s elapsed=%.2fs",
        dry_run,
        user,
        result.matched_numb,
        result.eg_rows_would_update,
        result.eg_rows_updated,
        result.skipped_not_in_db,
        result.parent_shells_would_create,
        result.phase_b_would_create,
        result.missing_numbs_would_create,
        result.ved_zero_synced,
        elapsed,
    )
    return result

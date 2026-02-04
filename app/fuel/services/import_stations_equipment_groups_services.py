# -*- coding: utf-8 -*-
"""Сервис импорта групп оборудования для агрегатов (stations_equipment_groups)."""

from __future__ import annotations

import logging
import time
import pandas as pd
from sqlalchemy import func

from app.extensions import db
from app.logs.services.logging_service import log_to_db
from app.common.services.help_services import _clean_name
from app.common.services.database_version_filter import filter_by_db_version, set_db_version_on_create
from app.generation.models.machine.machine_model import Machine
from app.generation.models.station.station_model import Station
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation


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


def _apply_equipment_group_import_column_aliases(df: pd.DataFrame) -> pd.DataFrame:
    alias_to_canonical: dict[str, str] = {}

    def add_aliases(canonical: str, aliases: list[str]) -> None:
        for a in aliases:
            alias_to_canonical[_normalize_column_name(a)] = canonical

    add_aliases("id_station", ["id_station", "station_id", "id_станции", "id_станция", "id_станций"])
    add_aliases("id_machine", ["id_machine", "machine_id", "id_агрегата", "id_агрегат", "id_агрегатов"])
    add_aliases("equipment_group", [
        "equipment_group", "group", "equipment_group_name", "group_name",
        "группа_оборудования", "группа", "наименование_группы",
    ])

    rename_map: dict[str, str] = {}
    for col in df.columns:
        normalized = _normalize_column_name(col)
        canonical = alias_to_canonical.get(normalized)
        if canonical and canonical != col and canonical not in df.columns:
            rename_map[col] = canonical

    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def _detect_header_row_index(df_raw: pd.DataFrame, normalized_header_candidates: set[str], max_rows: int = 30) -> int | None:
    if df_raw is None or df_raw.empty:
        return None

    best_idx = None
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
        if best_score >= 2:
            break

    if best_score < 2:
        return None
    return best_idx


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


def _versioned_query(model):
    return filter_by_db_version(model.query, model)


def _ensure_equipment_group_set_for_station(station_id: int, equipment_group_id: int):
    if not station_id or not equipment_group_id:
        return None, False, False

    link = (
        _versioned_query(EquipmentGroupSetStation)
        .join(
            EquipmentGroupSet,
            EquipmentGroupSetStation.equipment_group_set_id == EquipmentGroupSet.id,
        )
        .filter(
            EquipmentGroupSetStation.station_id == station_id,
            EquipmentGroupSet.id_equipment_group == equipment_group_id,
        )
        .first()
    )
    if link:
        return link.equipment_group_set, False, False

    station = _versioned_query(Station).filter_by(id=station_id).first()
    equipment_group = _versioned_query(EquipmentGroup).filter_by(id=equipment_group_id).first()
    group_name = None
    if station and station.name and equipment_group and equipment_group.name:
        group_name = f"{station.name} ({equipment_group.name})"

    group_set = EquipmentGroupSet(
        id_equipment_group=equipment_group_id,
        name=group_name,
    )
    set_db_version_on_create(group_set)
    db.session.add(group_set)
    db.session.flush()

    link = EquipmentGroupSetStation(
        equipment_group_set_id=group_set.id,
        station_id=station_id,
    )
    set_db_version_on_create(link)
    db.session.add(link)
    db.session.flush()

    return group_set, True, True


def import_station_equipment_groups_from_excel(file, user: str):
    logger = _get_logger()
    t0 = time.perf_counter()
    filename = getattr(file, "filename", None)

    logger.info("[IMPORT_EQUIPMENT_GROUPS] start user=%s filename=%s", user, filename)

    xls = pd.ExcelFile(file)
    sheet_name = xls.sheet_names[0]

    df = xls.parse(sheet_name, header=0)
    df = df.dropna(how="all")
    df = _apply_equipment_group_import_column_aliases(df)

    required_columns = {"id_station", "id_machine", "equipment_group"}
    missing = sorted([c for c in required_columns if c not in df.columns])

    if missing:
        try:
            df_raw = xls.parse(sheet_name, header=None)
            normalized_candidates = {
                _normalize_column_name("id_station"),
                _normalize_column_name("station_id"),
                _normalize_column_name("id_станции"),
                _normalize_column_name("id_machine"),
                _normalize_column_name("machine_id"),
                _normalize_column_name("id_агрегата"),
                _normalize_column_name("equipment_group"),
                _normalize_column_name("группа_оборудования"),
            }
            header_row = _detect_header_row_index(df_raw, normalized_candidates, max_rows=40)
            if header_row is not None:
                df = xls.parse(sheet_name, header=header_row)
                df = df.dropna(how="all")
                df = _apply_equipment_group_import_column_aliases(df)
        except Exception:
            logger.exception("[IMPORT_EQUIPMENT_GROUPS] header autodetect failed filename=%s", filename)

    missing = sorted([c for c in required_columns if c not in df.columns])
    if missing:
        logger.error(
            "[IMPORT_EQUIPMENT_GROUPS] invalid template filename=%s missing=%s columns=%s",
            filename,
            missing,
            list(df.columns),
        )
        raise ValueError(
            "Неверный шаблон файла: отсутствуют обязательные колонки "
            f"{missing}. Ожидаются: id_station, id_machine, equipment_group."
        )

    processed_rows = 0
    skipped_empty_rows = 0
    skipped_invalid_rows = 0
    updated_machines = 0
    unchanged_machines = 0
    created_group_sets = 0
    created_group_set_links = 0
    updated_machine_group_sets = 0
    errors = []
    audit_counts = {}
    audit_samples = {}
    loaded_station_group_pairs = set()
    group_set_cache: dict[tuple[int, int], EquipmentGroupSet] = {}

    def _audit_inc(reason: str, sample: str | None = None) -> None:
        audit_counts[reason] = audit_counts.get(reason, 0) + 1
        if sample:
            lst = audit_samples.setdefault(reason, [])
            if len(lst) < 50:
                lst.append(sample)

    for index, row in df.iterrows():
        if row.isnull().all():
            skipped_empty_rows += 1
            _audit_inc("row_empty", f"row_index={index}")
            continue

        processed_rows += 1
        try:
            station_id = _safe_int(row.get("id_station"))
            machine_id = _safe_int(row.get("id_machine"))
            group_text = row.get("equipment_group")
            group_text = _clean_name(group_text) if group_text is not None and not pd.isna(group_text) else None
            group_text = group_text.strip() if isinstance(group_text, str) else group_text

            if station_id is None or machine_id is None or not group_text:
                skipped_invalid_rows += 1
                _audit_inc(
                    "row_missing_required",
                    f"row_index={index}; station_id={station_id}; machine_id={machine_id}; equipment_group={group_text}",
                )
                continue

            machine = (
                _versioned_query(Machine)
                .filter(Machine.id == machine_id, Machine.id_station == station_id)
                .first()
            )
            if not machine:
                skipped_invalid_rows += 1
                logger.warning(
                    "[IMPORT_EQUIPMENT_GROUPS] machine not found station_id=%s machine_id=%s row=%s",
                    station_id,
                    machine_id,
                    index,
                )
                _audit_inc(
                    "machine_not_found",
                    f"row_index={index}; station_id={station_id}; machine_id={machine_id}; equipment_group={group_text}",
                )
                continue

            group_norm = str(group_text).strip().lower()
            group = (
                _versioned_query(EquipmentGroup)
                .filter(_equipment_group_name_sql_normalized() == group_norm)
                .first()
            )
            if not group and group_norm.isdigit():
                group = _versioned_query(EquipmentGroup).filter_by(id=int(group_norm)).first()

            if not group:
                skipped_invalid_rows += 1
                logger.warning(
                    "[IMPORT_EQUIPMENT_GROUPS] equipment_group not found name=%s row=%s",
                    group_text,
                    index,
                )
                _audit_inc(
                    "equipment_group_not_found",
                    f"row_index={index}; station_id={station_id}; machine_id={machine_id}; equipment_group={group_text}",
                )
                continue

            loaded_station_group_pairs.add((station_id, group.id))

            group_set = group_set_cache.get((station_id, group.id))
            if group_set is None:
                group_set, created_set, created_link = _ensure_equipment_group_set_for_station(
                    station_id, group.id
                )
                if created_set:
                    created_group_sets += 1
                if created_link:
                    created_group_set_links += 1
                if group_set is not None:
                    group_set_cache[(station_id, group.id)] = group_set

            if group_set and machine.equipment_group_set_id != group_set.id:
                machine.equipment_group_set_id = group_set.id
                db.session.add(machine)
                updated_machine_group_sets += 1

            if machine.id_equipment_group != group.id:
                old_group_id = machine.id_equipment_group
                old_group_name = None
                if old_group_id:
                    try:
                        old_group = _versioned_query(EquipmentGroup).filter_by(id=old_group_id).first()
                        old_group_name = old_group.name if old_group else None
                    except Exception:
                        old_group_name = None

                station_name = None
                machine_number = None
                machine_name = None
                try:
                    station = getattr(machine, "machine_station", None)
                    station_name = station.name if station else None
                except Exception:
                    station_name = None
                try:
                    machine_number = machine.machine_number
                except Exception:
                    machine_number = None
                try:
                    machine_name = machine.machine_name
                except Exception:
                    machine_name = None

                machine.id_equipment_group = group.id
                db.session.add(machine)
                updated_machines += 1

                log_to_db(
                    user,
                    "Загрузка групп оборудования: обновление агрегата",
                    details=(
                        f"station_id={station_id}; station_name={station_name}; "
                        f"machine_id={machine_id}; machine_number={machine_number}; machine_name={machine_name}; "
                        f"old_group_id={old_group_id}; old_group_name={old_group_name}; "
                        f"new_group_id={group.id}; new_group_name={group.name}; "
                        f"equipment_group_text={group_text}; row_index={index}"
                    ),
                    entity_type="machine",
                    entity_id=machine.id,
                )
            else:
                unchanged_machines += 1
                _audit_inc(
                    "no_changes",
                    f"row_index={index}; station_id={station_id}; machine_id={machine_id}; equipment_group={group_text}",
                )

        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            err = {
                "row_index": int(index) if isinstance(index, (int, float)) else str(index),
                "filename": filename,
            }
            errors.append(err)
            logger.exception("[IMPORT_EQUIPMENT_GROUPS] row failed: %s", err)
            _audit_inc("row_exception", f"row_index={index}; filename={filename}")
            continue

    try:
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        logger.exception("[IMPORT_EQUIPMENT_GROUPS] final commit failed user=%s filename=%s", user, filename)
        raise

    elapsed = time.perf_counter() - t0
    logger.info(
        "[IMPORT_EQUIPMENT_GROUPS] done user=%s filename=%s processed=%s skipped_empty=%s skipped_invalid=%s updated=%s unchanged=%s errors=%s time=%.2fs",
        user,
        filename,
        processed_rows,
        skipped_empty_rows,
        skipped_invalid_rows,
        updated_machines,
        unchanged_machines,
        len(errors),
        elapsed,
    )

    try:
        log_to_db(
            user,
            "Загрузка групп оборудования: итог импорта",
            details=(
                f"filename={filename}; processed_rows={processed_rows}; "
                f"skipped_empty_rows={skipped_empty_rows}; skipped_invalid_rows={skipped_invalid_rows}; "
                f"updated_machines={updated_machines}; unchanged_machines={unchanged_machines}; "
                f"created_group_sets={created_group_sets}; created_group_set_links={created_group_set_links}; "
                f"updated_machine_group_sets={updated_machine_group_sets}; "
                f"errors_count={len(errors)}; "
                f"counts={audit_counts}"
            ),
            entity_type="import_equipment_groups",
            entity_id=None,
        )

        for reason in sorted(audit_samples.keys()):
            examples = audit_samples.get(reason) or []
            for sample in examples:
                log_to_db(
                    user,
                    f"Загрузка групп оборудования: {reason}",
                    details=f"filename={filename}; {sample}",
                    entity_type="import_equipment_groups",
                    entity_id=None,
                )
    except Exception:
        logger.exception("[IMPORT_EQUIPMENT_GROUPS] failed to write summary log filename=%s", filename)

    message = (
        "Загрузка групп оборудования завершена. "
        f"Обработано строк: {processed_rows}. "
        f"Обновлено агрегатов: {updated_machines}. "
        f"Создано групп: {created_group_sets}. "
        f"Привязано агрегатов к группам: {updated_machine_group_sets}. "
        f"Ошибок: {len(errors)}. Подробности — в логах."
    )
    return {
        "message": message,
        "processed_rows": processed_rows,
        "skipped_empty_rows": skipped_empty_rows,
        "skipped_invalid_rows": skipped_invalid_rows,
        "updated_machines": updated_machines,
        "unchanged_machines": unchanged_machines,
        "created_group_sets": created_group_sets,
        "created_group_set_links": created_group_set_links,
        "updated_machine_group_sets": updated_machine_group_sets,
        "errors_count": len(errors),
    }

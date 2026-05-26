# -*- coding: utf-8 -*-
"""
Синхронизация топливных параметров группы оборудования во всех версиях БД
(страница equipment_group_edit, форма fuelParamsForm).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from flask import current_app

from app.common.models.database_version_model import DatabaseVersion
from app.common.services.database_version_services import database_version_log_prefix
from app.common.services.tranzaction_services import _commit_with_retry, quick_fix_seq
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.services.equipment_groups.equipment_group_details_params_update_services import (
    update_equipment_group_all_details_params,
)
from app.fuel.services.equipment_groups.equipment_group_edit_services import (
    _apply_equipment_group_type_change_from_form,
    _effective_group_database_version_id,
    persist_equipment_group_grouping_station_if_in_form,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_write_services import (
    update_equipment_group_fuel_params_from_form,
)
from app.logs.services.logging_service import log_to_db
from config import SCHEMA_FUEL

logger = logging.getLogger(__name__)

LOG_ACTIONS_BY_TABLE = {
    "Параметры группы оборудования": "Редактирование параметров группы оборудования (EquipmentGroupFuelParam)",
    "Основные параметры": "Редактирование основных параметров (EquipmentGroupFuelParam)",
    "Основные параметры топлива": "Редактирование основных параметров топлива (EquipmentGroupFuelParam)",
    "Дополнительные параметры топлива": "Редактирование дополнительных параметров топлива (EquipmentGroupExtraFuelParam)",
    "Удельные показатели": "Редактирование удельных показателей (EquipmentGroupSpecificFuelConsumption)",
    "Стоимость": "Редактирование стоимости (EquipmentGroupSpecificFuelCost)",
    "Цена": "Редактирование цены (EquipmentGroupSpecificFuelPrice)",
}


def log_equipment_group_fuel_param_changes(
    user,
    equipment_group_id: int,
    group_name: str,
    all_change_details: list[tuple],
    *,
    action_suffix: str = "",
    header_lines: Optional[list[str]] = None,
) -> None:
    """Запись в журнал по таблицам (отдельная запись на каждую модель/таблицу)."""
    if not all_change_details:
        return
    by_table: dict[str, list] = {}
    for table_name, year, attr, old_val, new_val in all_change_details:
        by_table.setdefault(table_name, []).append((year, attr, old_val, new_val))
    for table_name, items in by_table.items():
        action = LOG_ACTIONS_BY_TABLE.get(
            table_name,
            f"Редактирование таблицы «{table_name}»",
        )
        if action_suffix:
            action = f"{action} {action_suffix}".strip()
        log_lines = list(header_lines or [])
        log_lines.append(f"Группа id={equipment_group_id} ({group_name}):")
        for year, attr, old_val, new_val in items:
            log_lines.append(
                f"  Год {year}, параметр {attr}: было {old_val} → стало {new_val}"
            )
        log_to_db(
            user,
            action,
            details="\n".join(log_lines),
            entity_type="equipment_group",
            entity_id=equipment_group_id,
        )


def _apply_fuel_form_side_fields(
    equipment_group_id: int,
    form_data: dict,
    *,
    version_id: Optional[int] = None,
) -> list[str]:
    """Тип группы и станция группировки из fuelParamsForm."""
    warnings: list[str] = []
    if "equipment_group_type_id" in form_data:
        egt_raw = form_data.get("equipment_group_type_id")
        if egt_raw is not None and str(egt_raw).strip():
            try:
                anchor_egt_id = int(str(egt_raw).strip())
            except (TypeError, ValueError):
                anchor_egt_id = None
        else:
            anchor_egt_id = None
        if anchor_egt_id is not None:
            eg_for_ver = EquipmentGroup.query.get(equipment_group_id)
            eff_ver = (
                version_id
                if version_id is not None
                else _effective_group_database_version_id(eg_for_ver)
            )
            new_egt_id = anchor_egt_id
            if version_id is not None:
                from app.fuel.services.equipment_groups.equipment_group_merge_services import (
                    _resolve_equipment_group_type_id_for_version,
                )

                resolved = _resolve_equipment_group_type_id_for_version(
                    anchor_egt_id, version_id
                )
                if resolved is None:
                    return warnings
                new_egt_id = resolved
            egt_err = _apply_equipment_group_type_change_from_form(
                equipment_group_id,
                new_egt_id,
                eff_ver,
            )
            if egt_err:
                raise ValueError(egt_err)
    eg_for_grouping = EquipmentGroup.query.get(equipment_group_id)
    if eg_for_grouping:
        gerr = persist_equipment_group_grouping_station_if_in_form(
            eg_for_grouping,
            dict(form_data),
            version_id=version_id,
        )
        if gerr:
            raise ValueError(gerr)
    return warnings


def _save_fuel_params_for_group(
    group_id: int,
    form_data: dict,
    start_year: int,
    end_year: int,
    *,
    rounding_digits_table1: int,
    rounding_digits_table2: int,
    rounding_digits_table3: int,
    rounding_digits_table4: int,
) -> tuple[list[str], list[tuple]]:
    messages: list[str] = []
    all_change_details: list[tuple] = []
    _ok, msg, details = update_equipment_group_fuel_params_from_form(
        group_id,
        form_data,
        start_year,
        end_year,
        rounding_digits_table1=rounding_digits_table1,
        rounding_digits_table2=rounding_digits_table2,
    )
    if _ok and msg != "Изменений нет.":
        messages.append(msg)
    if details:
        all_change_details.extend(details)
    _ok2, sub_msgs, details2 = update_equipment_group_all_details_params(
        group_id,
        form_data,
        start_year,
        end_year,
        rounding_digits_table3=rounding_digits_table3,
        rounding_digits_table4=rounding_digits_table4,
    )
    if _ok2:
        messages.extend(sub_msgs)
    if details2:
        all_change_details.extend(details2)
    return messages, all_change_details


def update_equipment_group_fuel_params_all_versions_from_form(
    *,
    user,
    equipment_group_id: int,
    form_data: dict,
    start_year: int,
    end_year: int,
    rounding_digits_table1: int = 1,
    rounding_digits_table2: int = 1,
    rounding_digits_table3: int = 1,
    rounding_digits_table4: int = 1,
    request_meta: Optional[dict] = None,
) -> dict[str, Any]:
    """
    Применяет топливные параметры формы ко всем копиям группы (external_code) во всех версиях БД.
    """
    anchor = EquipmentGroup.query.filter_by(id=equipment_group_id).first()
    if not anchor:
        return {"error": "Группа оборудования не найдена", "no_changes": True}

    group_name = (anchor.name or anchor.name_ext or "—").strip() or "—"
    external_code = (anchor.external_code or "").strip()
    request_meta = request_meta or {}

    all_messages: list[str] = []
    aggregate_details: list[tuple] = []
    per_group_log: list[str] = []
    versions_touched_set: set[Optional[int]] = set()
    updated_group_ids: set[int] = set()

    def _process_group(gid: int, version_id: Optional[int]) -> None:
        msgs, details = _save_fuel_params_for_group(
            gid,
            form_data,
            start_year,
            end_year,
            rounding_digits_table1=rounding_digits_table1,
            rounding_digits_table2=rounding_digits_table2,
            rounding_digits_table3=rounding_digits_table3,
            rounding_digits_table4=rounding_digits_table4,
        )
        if msgs or details:
            updated_group_ids.add(gid)
            versions_touched_set.add(version_id)
            if details:
                aggregate_details.extend(details)
                per_group_log.append(
                    f"группа id={gid} ({database_version_log_prefix(version_id)}): "
                    f"{len(details)} изменений"
                )
            all_messages.extend(msgs)

    if not external_code:
        _process_group(equipment_group_id, getattr(anchor, "database_version_id", None))
        try:
            _apply_fuel_form_side_fields(equipment_group_id, form_data)
        except ValueError as exc:
            db.session.rollback()
            return {"error": str(exc), "no_changes": True}
        if not updated_group_ids and not db.session.dirty:
            return {
                "no_changes": True,
                "fallback_single": True,
                "versions_touched": 0,
                "updated_groups": 0,
                "all_change_details": [],
                "group_name": group_name,
            }
        try:
            for seq_table in (
                "gs_fue_equipment_group_fuel_param",
                "gs_fue_equipment_group_extra_fuel_param",
                "gs_fue_equipment_group_specific_fuel_consumption",
                "gs_fue_equipment_group_specific_fuel_cost",
                "gs_fue_equipment_group_specific_fuel_price",
            ):
                try:
                    quick_fix_seq(SCHEMA_FUEL, seq_table, "id")
                except Exception:
                    pass
            _commit_with_retry()
        except Exception:
            db.session.rollback()
            logger.exception(
                "[equipment_group_fuel_all_versions] COMMIT FAILED group_id=%s",
                equipment_group_id,
            )
            raise
        _log_all_versions_result(
            user,
            anchor,
            external_code,
            start_year,
            end_year,
            request_meta,
            versions_touched=0,
            updated_groups=len(updated_group_ids),
            aggregate_details=aggregate_details,
            per_group_log=per_group_log,
            fallback_single=True,
        )
        return {
            "fallback_single": True,
            "versions_touched": 0,
            "updated_groups": len(updated_group_ids),
            "all_change_details": aggregate_details,
            "group_name": group_name,
            "no_changes": False,
        }

    version_ids: list[Optional[int]] = [None]
    for dv in DatabaseVersion.query.filter(DatabaseVersion.id.isnot(None)).all():
        if dv.id:
            version_ids.append(dv.id)

    matched_any = False
    for version_id in version_ids:
        eg_version_filter = (
            EquipmentGroup.database_version_id.is_(None)
            if version_id is None
            else (EquipmentGroup.database_version_id == version_id)
        )
        groups = (
            EquipmentGroup.query.filter_by(external_code=external_code)
            .filter(eg_version_filter)
            .all()
        )
        if not groups:
            continue
        matched_any = True
        for g in groups:
            if not g.id:
                continue
            _process_group(g.id, version_id)
            try:
                _apply_fuel_form_side_fields(g.id, form_data, version_id=version_id)
            except ValueError as exc:
                db.session.rollback()
                return {"error": str(exc), "no_changes": True}

    if not matched_any:
        return {
            "no_changes": True,
            "versions_touched": 0,
            "updated_groups": 0,
            "all_change_details": [],
            "group_name": group_name,
            "warning": "Не найдено групп с таким external_code в других версиях.",
        }

    if not updated_group_ids and not db.session.dirty:
        return {
            "no_changes": True,
            "versions_touched": 0,
            "updated_groups": 0,
            "all_change_details": [],
            "group_name": group_name,
        }

    try:
        for seq_table in (
            "gs_fue_equipment_group_fuel_param",
            "gs_fue_equipment_group_extra_fuel_param",
            "gs_fue_equipment_group_specific_fuel_consumption",
            "gs_fue_equipment_group_specific_fuel_cost",
            "gs_fue_equipment_group_specific_fuel_price",
        ):
            try:
                quick_fix_seq(SCHEMA_FUEL, seq_table, "id")
            except Exception:
                pass
        _commit_with_retry()
    except Exception:
        db.session.rollback()
        logger.exception(
            "[equipment_group_fuel_all_versions] COMMIT FAILED group_id=%s",
            equipment_group_id,
        )
        raise

    versions_touched = len(versions_touched_set)
    updated_groups = len(updated_group_ids)
    _log_all_versions_result(
        user,
        anchor,
        external_code,
        start_year,
        end_year,
        request_meta,
        versions_touched=versions_touched,
        updated_groups=updated_groups,
        aggregate_details=aggregate_details,
        per_group_log=per_group_log,
        fallback_single=False,
    )
    if current_app:
        current_app.logger.info(
            "[equipment_group_fuel_all_versions] SUCCESS anchor_id=%s versions=%s groups=%s",
            equipment_group_id,
            versions_touched,
            updated_groups,
        )
    return {
        "versions_touched": versions_touched,
        "updated_groups": updated_groups,
        "all_change_details": aggregate_details,
        "group_name": group_name,
        "no_changes": False,
        "per_group_log": per_group_log,
    }


def _log_all_versions_result(
    user,
    anchor: EquipmentGroup,
    external_code: str,
    start_year: int,
    end_year: int,
    request_meta: dict,
    *,
    versions_touched: int,
    updated_groups: int,
    aggregate_details: list[tuple],
    per_group_log: list[str],
    fallback_single: bool,
) -> None:
    log_lines = [
        "Синхронизация топливных параметров группы оборудования во всех версиях БД.",
        f"Группа: {(anchor.name or anchor.name_ext or '—')} (id={anchor.id}, external_code={external_code or '—'})",
        f"Пользователь: {user}",
        f"Годы: {start_year}–{end_year}",
        f"Затронуто версий БД: {versions_touched}",
        f"Обновлено групп: {updated_groups}",
        f"Только текущая версия (нет external_code): {fallback_single}",
        f"Мета запроса: {request_meta}",
    ]
    if per_group_log:
        log_lines.append("По группам:")
        log_lines.extend(f"  - {line}" for line in per_group_log[:80])
        if len(per_group_log) > 80:
            log_lines.append(f"  ... ещё {len(per_group_log) - 80} строк")
    if aggregate_details:
        log_lines.append("Изменения (первые 100 строк):")
        for table_name, year, attr, old_val, new_val in aggregate_details[:100]:
            log_lines.append(
                f"  [{table_name}] год {year}, {attr}: было {old_val} → стало {new_val}"
            )
        if len(aggregate_details) > 100:
            log_lines.append(f"  ... ещё {len(aggregate_details) - 100} изменений")
    log_to_db(
        user,
        "Синхронизация топливных параметров группы оборудования во всех версиях БД",
        details="\n".join(log_lines),
        entity_type="equipment_group",
        entity_id=anchor.id,
    )
    log_equipment_group_fuel_param_changes(
        user,
        anchor.id,
        (anchor.name or anchor.name_ext or "—"),
        aggregate_details,
        action_suffix="(детализация по таблицам, все версии)",
        header_lines=[
            f"Сводка по таблицам после синхронизации во всех версиях (external_code={external_code or '—'}).",
        ],
    )

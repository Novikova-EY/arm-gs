# -*- coding: utf-8 -*-
"""
Сохранение данных формы machine_details во всех версиях БД (как «Сохранить» в текущей версии).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from flask import flash, g, redirect, url_for
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.attributes import flag_modified

from app.common.models.database_version_model import DatabaseVersion
from app.common.services.database_version_services import (
    build_database_version_numbers_by_id,
    database_version_log_prefix,
)
from app.common.services.tranzaction_services import _commit_with_retry, quick_fix_seq
from app.common.services.version_entity_resolve_services import resolve_machine_details_ids
from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.generation.models.station.station_model import Station
from app.generation.services.machine_services.machine_services import (
    persist_machine_details_from_validated_forms,
)
from app.generation.services.station_services.station_services import (
    clear_station_aggregation_cache,
    recalculate_station_power,
)
from app.logs.services.logging_service import log_to_db
from config import SCHEMA_FUEL, SCHEMA_GENERATION

logger = logging.getLogger(__name__)


def _all_database_version_ids() -> list[Optional[int]]:
    version_ids: list[Optional[int]] = [None]
    for dv in DatabaseVersion.query.filter(DatabaseVersion.id.isnot(None)).all():
        if dv.id:
            version_ids.append(dv.id)
    return version_ids


def _quick_fix_machine_details_seqs() -> None:
    for schema, table in (
        (SCHEMA_GENERATION, "gs_gen_machines"),
        (SCHEMA_GENERATION, "gs_gen_machine_powers"),
        (SCHEMA_GENERATION, "gs_gen_machine_fuels"),
        (SCHEMA_GENERATION, "gs_gen_machine_tes_types"),
        (SCHEMA_GENERATION, "gs_gen_machine_names"),
        # Автоопределение топливной группы может создавать эти записи из machine_details.
        (SCHEMA_FUEL, "gs_fue_equipment_groups"),
        (SCHEMA_FUEL, "gs_fue_equipment_group_sets"),
        (SCHEMA_FUEL, "gs_fue_equipment_group_type_stations"),
    ):
        try:
            quick_fix_seq(schema, table, "id")
        except Exception:
            pass

def save_machine_details_across_versions(
    *,
    user,
    anchor_station_id: int,
    anchor_machine_id: int,
    main_form,
    advanced_form,
    pgu_machines_form,
    normalized,
    start_year: int,
    end_year: int,
    redirect_args: dict,
    can_edit_fuel: bool,
    can_edit_generation: bool,
    is_pgu_action: bool,
    year_features: dict,
    anchor_station: Station,
    anchor_machine: Machine,
) -> Any:
    """
    Применяет провалидированные формы machine_details ко всем копиям агрегата (external_code).
  """
    external_code = (getattr(anchor_machine, "external_code", None) or "").strip()
    if not external_code:
        flash(
            "У агрегата отсутствует external_code — синхронизация во всех версиях невозможна.",
            "warning",
        )
        return redirect(
            url_for(
                "station_bp.machine_details",
                station_id=anchor_station_id,
                machine_id=anchor_machine_id,
                **redirect_args,
            )
        )

    version_ids = _all_database_version_ids()
    version_numbers = build_database_version_numbers_by_id()
    warnings: list[str] = []
    versions_touched: set[Optional[int]] = set()
    all_change_lines: list[str] = []
    stations_to_recalc: set[tuple[int, int, int]] = set()

    old_db_version = getattr(g, "current_db_version", None)
    _quick_fix_machine_details_seqs()

    try:
        with db.session.no_autoflush:
            for version_id in version_ids:
                resolved = resolve_machine_details_ids(
                    anchor_station_id, anchor_machine_id, version_id
                )
                if not resolved:
                    warnings.append(
                        f"{database_version_log_prefix(version_id, version_numbers)}: "
                        "копия агрегата не найдена, пропуск."
                    )
                    continue

                target_station_id, target_machine_id = resolved
                target_station = db.session.get(Station, target_station_id)
                target_machine = db.session.get(Machine, target_machine_id)
                if not target_station or not target_machine:
                    warnings.append(
                        f"{database_version_log_prefix(version_id, version_numbers)}: "
                        f"станция/агрегат id={target_station_id}/{target_machine_id} не загружены."
                    )
                    continue

                try:
                    g.current_db_version = version_id
                except Exception:
                    pass

                try:
                    changes, pgu_changes = persist_machine_details_from_validated_forms(
                        target_station,
                        target_machine,
                        main_form=main_form,
                        advanced_form=advanced_form,
                        pgu_machines_form=pgu_machines_form,
                        normalized=normalized,
                        user=user,
                        start_year=start_year,
                        end_year=end_year,
                        can_edit_fuel=can_edit_fuel,
                        can_edit_generation=can_edit_generation,
                        is_pgu_action=is_pgu_action and version_id == old_db_version,
                        year_features=year_features,
                        skip_pgu=(version_id != old_db_version),
                    )
                except Exception as exc:
                    logger.exception(
                        "[machine_details_all_versions] persist failed version=%s machine=%s",
                        version_id,
                        target_machine_id,
                    )
                    warnings.append(
                        f"{database_version_log_prefix(version_id, version_numbers)}, "
                        f"агрегат id={target_machine_id}: {exc}"
                    )
                    if isinstance(exc, SQLAlchemyError) or not db.session.is_active:
                        raise
                    continue

                if changes or pgu_changes:
                    versions_touched.add(version_id)
                    all_change_lines.append(
                        f"{database_version_log_prefix(version_id, version_numbers)}, "
                        f"агрегат id={target_machine_id} "
                        f"(№{target_machine.machine_number}): {len(changes)} измен."
                    )
                    stations_to_recalc.add(
                        (target_station_id, start_year, end_year)
                    )

        for st_id, sy, ey in stations_to_recalc:
            st = db.session.get(Station, st_id)
            if st:
                recalculate_station_power(st, sy, ey)

        _commit_with_retry()
        clear_station_aggregation_cache(
            "после сохранения machine_details во всех версиях БД"
        )

        from app.common.services.cache_decorator import (
            invalidate_cache,
            invalidate_cache_pattern,
        )

        invalidate_cache("machine", machine_id=anchor_machine_id)
        invalidate_cache("station_full", station_id=anchor_station_id)
        invalidate_cache_pattern("station_list:*")
        from app.generation.services.machine_services.machine_services import (
            clear_machine_choices_cache,
        )

        clear_machine_choices_cache()

    except Exception:
        db.session.rollback()
        raise
    finally:
        try:
            g.current_db_version = old_db_version
        except Exception:
            pass

    if not versions_touched and not warnings:
        flash("Изменений для синхронизации во всех версиях нет.", "info")
    elif not versions_touched:
        for msg in warnings:
            flash(msg, "warning")
    else:
        flash(
            f"Данные агрегата применены во всех версиях БД "
            f"(затронуто версий: {len(versions_touched)}).",
            "success",
        )
        for msg in warnings:
            flash(msg, "warning")

    log_lines = [
        "Синхронизация machine_details во всех версиях БД.",
        f"Электростанция: {anchor_station.name} (id={anchor_station.id})",
        f"Агрегат: №{anchor_machine.machine_number} (id={anchor_machine.id}, "
        f"external_code={external_code})",
        f"Пользователь: {user}",
        f"Годы: {start_year}–{end_year}",
        f"Затронуто версий БД: {len(versions_touched)}",
    ]
    if all_change_lines:
        log_lines.extend(all_change_lines[:30])
        if len(all_change_lines) > 30:
            log_lines.append(f"... ещё {len(all_change_lines) - 30} строк")
    if warnings:
        log_lines.append("Предупреждения:")
        log_lines.extend(f"  ! {w}" for w in warnings)

    log_to_db(
        user,
        "Синхронизация данных агрегата во всех версиях БД (machine_details)",
        details="\n".join(log_lines),
        entity_type="machine",
        entity_id=anchor_machine_id,
    )

    return redirect(
        url_for(
            "station_bp.machine_details",
            station_id=anchor_station_id,
            machine_id=anchor_machine_id,
            **redirect_args,
        )
    )

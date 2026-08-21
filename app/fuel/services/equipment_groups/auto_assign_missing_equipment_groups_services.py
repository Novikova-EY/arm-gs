# -*- coding: utf-8 -*-
"""Автоопределение топливной группы агрегата — как «Сохранить» на machine_details."""

from __future__ import annotations

from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.sql import func

from app.common.services.database_version_filter import (
    filter_by_db_version,
    get_current_db_version_id,
)
from app.fuel.services.equipment_groups.equipment_group_rebind_services import (
    _get_machine_fuel_param,
)
from app.fuel.services.equipment_groups.equipment_group_set_services import (
    sync_machine_fuel_equipment_group,
)
from app.generation.models.machine.machine_model import Machine
from app.generation.services.station_services.filters_services import (
    build_machines_without_equipment_group_filter,
)


def apply_auto_assign_to_machines(machines) -> dict:
    """
    Для каждого агрегата вызывает sync_machine_fuel_equipment_group
    (режим «по типу группы и плановому году (авто)» на карточке агрегата).
    """
    assigned = 0
    skipped_no_type = 0
    unchanged = 0
    failed = 0
    details: list[str] = []

    for machine in machines or []:
        machine_id = getattr(machine, "id", None)
        version_id = (
            getattr(machine, "database_version_id", None) or get_current_db_version_id()
        )
        type_before = getattr(machine, "id_equipment_group", None)
        mfp_before = (
            _get_machine_fuel_param(machine_id, version_id) if machine_id else None
        )
        old_id = mfp_before.equipment_group_id if mfp_before else None
        try:
            group = sync_machine_fuel_equipment_group(machine, version_id=version_id)
        except Exception as exc:
            failed += 1
            details.append(f"id={machine_id}: {exc}")
            continue

        new_id = getattr(group, "id", None)
        type_after = getattr(machine, "id_equipment_group", None)
        group_name = (getattr(group, "name", None) or "").strip() if group else ""
        if (new_id and new_id != old_id) or (not type_before and type_after):
            assigned += 1
            if hasattr(machine, "updated_at"):
                machine.updated_at = func.now()
                flag_modified(machine, "updated_at")
            label = group_name or f"id={new_id}" if new_id else f"тип id={type_after}"
            details.append(f"id={machine_id}: → {label}")
        elif new_id or type_after:
            unchanged += 1
        elif not type_after:
            skipped_no_type += 1
        else:
            failed += 1
            details.append(f"id={machine_id}: группа не создана")

    return {
        "assigned": assigned,
        "skipped_no_type": skipped_no_type,
        "unchanged": unchanged,
        "failed": failed,
        "details": details,
    }


def auto_assign_missing_fuel_equipment_groups(
    filters: dict | None,
    *,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict:
    """Агрегаты текущей выборки «без группы» в текущей версии БД."""
    from app.generation.services.station_services.station_services import get_stations_list

    list_filters = dict(filters or {})
    list_filters["machines_without_equipment_group"] = True
    result = get_stations_list(
        page=1,
        per_page=1,
        start_year=start_year,
        end_year=end_year,
        return_ids_only=True,
        **list_filters,
    )
    station_ids = result.get("station_ids") or []
    if not station_ids:
        return apply_auto_assign_to_machines([])

    query = Machine.query.filter(Machine.id_station.in_(station_ids))
    query = filter_by_db_version(query, Machine)
    query = query.filter(build_machines_without_equipment_group_filter(Machine))
    machines = query.order_by(Machine.id_station.asc(), Machine.id.asc()).all()
    return apply_auto_assign_to_machines(machines)

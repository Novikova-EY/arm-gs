# -*- coding: utf-8 -*-
"""
Services for merging EquipmentGroup (v2) links.
"""
from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import delete as sa_delete, func, select

from app.extensions import db
from app.common.services.database_version_filter import set_db_version_on_create
from app.generation.models.station.station_model import Station
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_station_model import (
    EquipmentGroupSetStation,
)


EQUIPMENT_GROUP_MERGE_FIELDS = [
    "name", "name_ext", "niv", "comp", "main", "d", "r", "forem",
    "vedomstvo", "obl", "dep", "oes", "er", "fo", "numb", "tm",
    "n1", "n2", "p1", "p2", "ordnumb", "addr", "note",
    "codegor", "be", "gk", "gkf",
]


def _has_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _is_group_in_version(group: EquipmentGroup, version_id: Optional[int]) -> bool:
    if not hasattr(group, "database_version_id"):
        return True
    if version_id is None:
        return group.database_version_id is None
    return group.database_version_id == version_id


def _filter_groups_by_version(
    groups: Iterable[EquipmentGroup], version_id: Optional[int]
) -> list[EquipmentGroup]:
    return [g for g in groups if g and _is_group_in_version(g, version_id)]


def _strict_equipment_group_version_criterion(version_id: Optional[int]):
    """Только группы этой версии БД — без подмешивания legacy (version_id is None)."""
    if version_id is None:
        return EquipmentGroup.database_version_id.is_(None)
    return EquipmentGroup.database_version_id == version_id


def merge_candidates_for_version(
    station_groups: Iterable[EquipmentGroup],
    same_name_groups: Iterable[EquipmentGroup],
    version_id: Optional[int],
) -> list[EquipmentGroup]:
    """
    Кандидаты на переименование/объединение в одной версии БД.

    Группы других версий (и legacy при выбранной версии) в слияние не попадают:
    иначе «Сохранить во всех версиях» склеивает все копии в одну карточку
    чужой версии, и группа пропадает на странице станции текущей версии.
    """
    seen_ids: set[int] = set()
    result: list[EquipmentGroup] = []
    for group in list(station_groups or []) + list(same_name_groups or []):
        if not group or group.id in seen_ids:
            continue
        if not _is_group_in_version(group, version_id):
            continue
        seen_ids.add(group.id)
        result.append(group)
    return result


def _count_filled_fields(group: EquipmentGroup) -> int:
    filled = 0
    for field in EQUIPMENT_GROUP_MERGE_FIELDS:
        if _has_value(getattr(group, field, None)):
            filled += 1
    return filled


def _choose_primary_group(groups: list[EquipmentGroup]) -> Optional[EquipmentGroup]:
    if not groups:
        return None
    return max(groups, key=_count_filled_fields)


def _merge_group_fields(target: EquipmentGroup, source: EquipmentGroup) -> bool:
    changed = False
    for field in EQUIPMENT_GROUP_MERGE_FIELDS:
        target_val = getattr(target, field, None)
        source_val = getattr(source, field, None)
        if not _has_value(target_val) and _has_value(source_val):
            setattr(target, field, source_val)
            changed = True
    return changed


def _merge_group_fields_return_list(
    target: EquipmentGroup, source: EquipmentGroup
) -> list[str]:
    """Сливает поля source → target; возвращает список объединенных полей."""
    merged: list[str] = []
    for field in EQUIPMENT_GROUP_MERGE_FIELDS:
        target_val = getattr(target, field, None)
        source_val = getattr(source, field, None)
        if not _has_value(target_val) and _has_value(source_val):
            setattr(target, field, source_val)
            merged.append(field)
    return merged


def _ensure_set_link(link_id: int, group_id: int) -> None:
    exists = EquipmentGroupSet.query.filter_by(
        equipment_group_id=group_id,
        equipment_group_set_station_id=link_id,
    ).first()
    if not exists:
        db.session.add(
            EquipmentGroupSet(
                equipment_group_id=group_id,
                equipment_group_set_station_id=link_id,
            )
        )


def _reassign_sets_to_primary(
    group_ids: list[int],
    primary_id: int,
    set_station_ids: Optional[list[int]] = None,
) -> None:
    if not group_ids:
        return
    q = EquipmentGroupSet.query.filter(
        EquipmentGroupSet.equipment_group_id.in_(group_ids)
    )
    if set_station_ids is not None:
        if not set_station_ids:
            return
        q = q.filter(
            EquipmentGroupSet.equipment_group_set_station_id.in_(set_station_ids)
        )
    sets = q.all()
    for set_v2 in sets:
        if set_v2.equipment_group_id == primary_id:
            continue
        duplicate = EquipmentGroupSet.query.filter_by(
            equipment_group_id=primary_id,
            equipment_group_set_station_id=set_v2.equipment_group_set_station_id,
        ).first()
        if duplicate:
            db.session.delete(set_v2)
        else:
            set_v2.equipment_group_id = primary_id


def _merge_missing_model_fields(target_row, source_row) -> None:
    """Копирует в target пустые поля из source для однотипных годовых записей."""
    skip_fields = {"id", "equipment_group_id", "created_at", "updated_at"}
    for column in source_row.__table__.columns:
        field = column.name
        if field in skip_fields:
            continue
        target_val = getattr(target_row, field, None)
        source_val = getattr(source_row, field, None)
        if target_val is None and source_val is not None:
            setattr(target_row, field, source_val)


def _reassign_model_rows_to_primary(
    model,
    group_ids: list[int],
    primary_id: int,
    identity_fields: list[str],
) -> None:
    """
    Переназначает строки model с group_ids на primary_id.

    Если у primary уже есть строка с тем же логическим ключом (identity_fields),
    дополняем пустые поля и удаляем дубликат, иначе просто переносим FK.
    """
    if not group_ids:
        return

    primary_rows = model.query.filter_by(equipment_group_id=primary_id).all()
    rows = model.query.filter(model.equipment_group_id.in_(group_ids)).all()

    def _identity_key(row) -> tuple:
        return tuple(getattr(row, field, None) for field in identity_fields)

    primary_by_key = {_identity_key(row): row for row in primary_rows}
    for row in rows:
        if row.equipment_group_id == primary_id:
            continue

        row_key = _identity_key(row)
        duplicate = primary_by_key.get(row_key)
        if duplicate:
            _merge_missing_model_fields(duplicate, row)
            db.session.execute(
                sa_delete(model).where(model.id == row.id)
            )
            if row in db.session:
                db.session.expunge(row)
        else:
            row.equipment_group_id = primary_id
            primary_by_key[row_key] = row


def _reassign_machine_links_to_primary(group_ids: list[int], primary_id: int) -> None:
    """Переназначает ссылки агрегатов на итоговую группу, чтобы не терять привязки."""
    if not group_ids:
        return

    from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam

    rows = MachineFuelParam.query.filter(
        MachineFuelParam.equipment_group_id.in_(group_ids)
    ).all()
    for row in rows:
        if row.equipment_group_id != primary_id:
            row.equipment_group_id = primary_id


def _reassign_group_detail_rows_to_primary(group_ids: list[int], primary_id: int) -> None:
    """
    Переназначает зависимые строки группы на primary, избегая дублей.

    Для каждой модели используется ее фактический логический ключ уникальности.
    """
    if not group_ids:
        return

    from app.fuel.models.fue_equipment_group_extra_fuel_param_model import (
        EquipmentGroupExtraFuelParam,
    )
    from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
    from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
        EquipmentGroupSpecificFuelConsumption,
    )
    from app.fuel.models.fue_equipment_group_specific_fuel_cost_model import (
        EquipmentGroupSpecificFuelCost,
    )
    from app.fuel.models.fue_equipment_group_specific_fuel_price_model import (
        EquipmentGroupSpecificFuelPrice,
    )
    from app.fuel.models.fue_equipment_group_fuel_formula_model import (
        EquipmentGroupFuelFormula,
    )
    from app.fuel.models.coefficient.equipment_group_coefficient_result_model import (
        EquipmentGroupCoefficientResult,
    )

    detail_specs = [
        (EquipmentGroupFuelParam, ["year_number"]),
        (EquipmentGroupExtraFuelParam, ["year_number"]),
        (EquipmentGroupSpecificFuelConsumption, ["year_number"]),
        (EquipmentGroupSpecificFuelCost, ["year_number"]),
        (EquipmentGroupSpecificFuelPrice, ["year_number"]),
        (
            EquipmentGroupFuelFormula,
            ["year_number", "variant_number", "database_version_id"],
        ),
        (
            EquipmentGroupCoefficientResult,
            ["distribution_parameter_id", "year_number", "database_version_id"],
        ),
    ]

    for model, identity_fields in detail_specs:
        _reassign_model_rows_to_primary(model, group_ids, primary_id, identity_fields)

    _reassign_machine_links_to_primary(group_ids, primary_id)


def _remove_orphan_groups(groups: Iterable[EquipmentGroup], primary_id: int) -> int:
    removed = 0
    # Сначала выталкиваем все pending-переназначения detail/set-строк в БД.
    # Иначе прямое удаление группы может сработать раньше, чем обновятся FK,
    # и PostgreSQL вернет ForeignKeyViolation.
    db.session.flush()
    for group in groups:
        if not group or group.id == primary_id:
            continue
        still_used = EquipmentGroupSet.query.filter_by(
            equipment_group_id=group.id
        ).first()
        if not still_used:
            db.session.delete(group)
            removed += 1
    return removed


def rename_equipment_groups_for_station_type(
    *,
    station_id: int,
    equipment_group_type_id: int,
    group_name: str,
) -> int:
    """
    Rename all EquipmentGroup (v2) linked to station/type across versions.
    Returns count of updated groups.
    """
    if not group_name:
        return 0

    links = EquipmentGroupSetStation.query.filter_by(
        station_id=station_id,
        equipment_group_type_id=equipment_group_type_id,
    ).all()

    updated = 0
    seen_ids = set()
    for link in links:
        sets = EquipmentGroupSet.query.filter_by(
            equipment_group_set_station_id=link.id
        ).all()
        for set_v2 in sets:
            group = set_v2.equipment_group
            if not group or group.id in seen_ids:
                continue
            seen_ids.add(group.id)
            if group.name != group_name:
                group.name = group_name
                updated += 1
    return updated


def merge_equipment_groups_by_name_for_station_type(
    *,
    station_id: int,
    equipment_group_type_id: int,
    group_name: str,
) -> dict:
    """
    Merge EquipmentGroup rows by name for all DB versions and
    link station/type EquipmentGroupSetStation to the merged group.
    """
    if not group_name:
        return {"merged": False, "removed_groups": 0}

    links = EquipmentGroupSetStation.query.filter_by(
        station_id=station_id,
        equipment_group_type_id=equipment_group_type_id,
    ).all()

    groups_by_name_all = EquipmentGroup.query.filter(
        EquipmentGroup.name == group_name
    ).all()

    groups_by_version = {}
    for group in groups_by_name_all:
        groups_by_version.setdefault(group.database_version_id, []).append(group)

    links_by_version = {}
    for link in links:
        links_by_version.setdefault(link.database_version_id, []).append(link)

    merged_any = False
    removed_groups_total = 0
    merged_groups_total = 0
    versions_touched = 0

    for version_id, name_groups in groups_by_version.items():
        if not name_groups:
            continue
        primary = _choose_primary_group(name_groups)
        if not primary:
            continue
        if primary.name != group_name:
            primary.name = group_name

        link_groups = []
        for link in links_by_version.get(version_id, []):
            sets = EquipmentGroupSet.query.filter_by(
                equipment_group_set_station_id=link.id
            ).all()
            for set_v2 in sets:
                if set_v2.equipment_group:
                    link_groups.append(set_v2.equipment_group)

        candidates = []
        seen_ids = set()
        for group in name_groups + link_groups:
            if not group or group.id in seen_ids:
                continue
            candidates.append(group)
            seen_ids.add(group.id)

        for group in candidates:
            if group.id == primary.id:
                continue
            _merge_group_fields(primary, group)

        candidate_ids = [g.id for g in candidates if g and g.id != primary.id]
        _reassign_group_detail_rows_to_primary(candidate_ids, primary.id)
        _reassign_sets_to_primary(candidate_ids, primary.id)

        for link in links_by_version.get(version_id, []):
            _ensure_set_link(link.id, primary.id)

        removed_groups_total += _remove_orphan_groups(candidates, primary.id)
        merged_groups_total += len(candidate_ids)
        versions_touched += 1
        merged_any = True

    return {
        "merged": merged_any,
        "removed_groups": removed_groups_total,
        "merged_groups": merged_groups_total,
        "versions_touched": versions_touched,
    }


def rename_or_merge_equipment_group_for_station(
    *,
    station_id: int,
    equipment_group_id: int,
    new_name: str,
    current_version_id: Optional[int],
) -> dict:
    """
    При переименовании группы оборудования: если уже есть группа с таким именем
    на электростанции — объединяем (EquipmentGroupSetStation → одна EquipmentGroup,
    параметры сливаем, дубликат удаляем). Иначе — просто обновляем name.

    Returns:
        dict с полями:
        - merged: bool
        - primary_id: int|None — id оставшейся группы
        - old_name: str — старое имя переименовываемой группы
        - new_name: str
        - deleted_group_id: int|None — id удаленной группы (при merge)
        - merged_fields: list[str] — список объединенных полей (при merge)
        - reassigned_set_ids: list[int] — id переназначенных EquipmentGroupSet (при merge)
    """
    empty_result = {
        "merged": False,
        "primary_id": None,
        "old_name": "",
        "new_name": new_name,
        "deleted_group_id": None,
        "merged_fields": [],
        "reassigned_set_ids": [],
    }
    if not new_name:
        return empty_result

    current_group = EquipmentGroup.query.filter_by(id=equipment_group_id).first()
    if not current_group:
        return empty_result

    old_name = (current_group.name or "").strip()

    # Ищем другую EquipmentGroup с таким же именем (без учета регистра и пробелов) — по всей БД,
    # чтобы объединять дубликаты даже если они привязаны к разным станциям.
    # Только в той же database_version_id, что у редактируемой группы: иначе versioned EG
    # может слиться в legacy (ver=None) и исчезнуть из текущей версии сессии.
    new_name_norm = new_name.strip().lower()
    name_expr = func.lower(func.trim(func.coalesce(EquipmentGroup.name, "")))
    group_version_id = getattr(current_group, "database_version_id", None)
    # current_version_id из сессии учитываем как fallback, если у группы версия не проставлена
    merge_version_id = (
        group_version_id if group_version_id is not None else current_version_id
    )
    existing_same_name = (
        db.session.query(EquipmentGroup)
        .filter(
            name_expr == new_name_norm,
            EquipmentGroup.id != equipment_group_id,
        )
    )
    if merge_version_id is None:
        existing_same_name = existing_same_name.filter(
            EquipmentGroup.database_version_id.is_(None)
        )
    else:
        existing_same_name = existing_same_name.filter(
            EquipmentGroup.database_version_id == merge_version_id
        )
    # Выбираем primary: с наибольшим числом заполненных полей (как в merge_equipment_groups_by_name)
    candidates = existing_same_name.all()
    primary_group = _choose_primary_group(candidates) if candidates else None

    if primary_group is None:
        # Дубликата нет — просто переименовываем
        current_group.name = new_name
        return {
            **empty_result,
            "merged": False,
            "primary_id": equipment_group_id,
            "old_name": old_name,
            "new_name": new_name,
        }

    # Собираем id EquipmentGroupSet для логирования до переназначения
    sets_to_reassign = EquipmentGroupSet.query.filter_by(
        equipment_group_id=equipment_group_id
    ).all()
    reassigned_set_ids = [s.id for s in sets_to_reassign]

    # Есть дубликат — объединяем: current_group → primary_group
    merged_fields = _merge_group_fields_return_list(primary_group, current_group)
    _reassign_group_detail_rows_to_primary([equipment_group_id], primary_group.id)
    _reassign_sets_to_primary([equipment_group_id], primary_group.id)
    _remove_orphan_groups([current_group], primary_group.id)

    return {
        "merged": True,
        "primary_id": primary_group.id,
        "old_name": old_name,
        "new_name": new_name,
        "deleted_group_id": equipment_group_id,
        "merged_fields": merged_fields,
        "reassigned_set_ids": reassigned_set_ids,
    }


def _equipment_group_detail_clone_models() -> list:
    from app.fuel.models.coefficient.equipment_group_coefficient_result_model import (
        EquipmentGroupCoefficientResult,
    )
    from app.fuel.models.fue_equipment_group_electricity_production_cost_model import (
        EquipmentGroupElectricityProductionCost,
    )
    from app.fuel.models.fue_equipment_group_extra_fuel_param_model import (
        EquipmentGroupExtraFuelParam,
    )
    from app.fuel.models.fue_equipment_group_fuel_formula_model import (
        EquipmentGroupFuelFormula,
    )
    from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
    from app.fuel.models.fue_equipment_group_heat_and_tariffs_model import (
        EquipmentGroupHeatAndTariffs,
    )
    from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
        EquipmentGroupSpecificFuelConsumption,
    )
    from app.fuel.models.fue_equipment_group_specific_fuel_cost_model import (
        EquipmentGroupSpecificFuelCost,
    )
    from app.fuel.models.fue_equipment_group_specific_fuel_price_model import (
        EquipmentGroupSpecificFuelPrice,
    )

    return [
        EquipmentGroupFuelParam,
        EquipmentGroupExtraFuelParam,
        EquipmentGroupSpecificFuelConsumption,
        EquipmentGroupSpecificFuelCost,
        EquipmentGroupSpecificFuelPrice,
        EquipmentGroupFuelFormula,
        EquipmentGroupCoefficientResult,
        EquipmentGroupHeatAndTariffs,
        EquipmentGroupElectricityProductionCost,
    ]


def _copy_group_detail_rows_to_clone(
    source_id: int,
    target_id: int,
    target_version_id: Optional[int],
) -> None:
    """Копирует зависимые строки группы на клон; database_version_id приводит к версии клона."""
    from sqlalchemy.exc import IntegrityError

    skip_fields = {"id", "created_at", "updated_at", "version"}
    for model in _equipment_group_detail_clone_models():
        table = model.__table__
        if "equipment_group_id" not in table.c:
            continue
        rows = db.session.execute(
            select(table).where(table.c.equipment_group_id == source_id)
        ).all()
        for row in rows:
            data = dict(row._mapping)
            for field in skip_fields:
                data.pop(field, None)
            data["equipment_group_id"] = target_id
            if "database_version_id" in data:
                data["database_version_id"] = target_version_id
            try:
                with db.session.begin_nested():
                    db.session.execute(table.insert().values(**data))
            except IntegrityError:
                continue


def _clone_equipment_group_into_version(
    source: EquipmentGroup,
    version_id: Optional[int],
) -> EquipmentGroup:
    """Создаёт копию группы в указанной версии БД с тем же external_code."""
    skip = {"id", "created_at", "updated_at"}
    values = {}
    for column in EquipmentGroup.__table__.columns:
        if column.name in skip:
            continue
        values[column.name] = getattr(source, column.name)
    values["database_version_id"] = version_id
    from app.common.services.refdata_fk_resolve import (
        coerce_regional_district_id_for_db_version,
        coerce_regional_energy_system_id_for_db_version,
    )

    values["regional_district_id"] = coerce_regional_district_id_for_db_version(
        values.get("regional_district_id"), version_id
    )
    values["regional_energy_system_id"] = coerce_regional_energy_system_id_for_db_version(
        values.get("regional_energy_system_id"), version_id
    )
    clone = EquipmentGroup(**values)
    db.session.add(clone)
    clone.database_version_id = version_id
    db.session.flush()
    _copy_group_detail_rows_to_clone(source.id, clone.id, version_id)
    return clone


def _find_or_clone_group_in_version(
    source: EquipmentGroup,
    version_id: Optional[int],
) -> EquipmentGroup:
    """Группа этой версии с тем же external_code; если нет — клон source."""
    if _is_group_in_version(source, version_id):
        return source
    external_code = (source.external_code or "").strip()
    if external_code:
        existing = (
            EquipmentGroup.query.filter_by(external_code=external_code)
            .filter(_strict_equipment_group_version_criterion(version_id))
            .first()
        )
        if existing is not None:
            return existing
    return _clone_equipment_group_into_version(source, version_id)


def _reassign_machine_links_for_stations(
    source_group_id: int,
    target_group_id: int,
    station_ids: list[int],
) -> None:
    """Переносит MachineFuelParam с source на target только для агрегатов этих станций."""
    if not station_ids or source_group_id == target_group_id:
        return
    from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
    from app.generation.models.machine.machine_model import Machine

    rows = (
        MachineFuelParam.query.join(Machine, Machine.id == MachineFuelParam.machine_id)
        .filter(
            MachineFuelParam.equipment_group_id == source_group_id,
            Machine.id_station.in_(station_ids),
        )
        .all()
    )
    for row in rows:
        row.equipment_group_id = target_group_id


def _link_ids_for_group_in_version(
    group_id: int,
    version_id: Optional[int],
) -> list[int]:
    q = (
        db.session.query(EquipmentGroupSet.equipment_group_set_station_id)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSetStation.id
            == EquipmentGroupSet.equipment_group_set_station_id,
        )
        .filter(EquipmentGroupSet.equipment_group_id == group_id)
    )
    if version_id is None:
        q = q.filter(EquipmentGroupSetStation.database_version_id.is_(None))
    else:
        q = q.filter(EquipmentGroupSetStation.database_version_id == version_id)
    return [row[0] for row in q.all()]


def _station_ids_from_link_ids(link_ids: list[int]) -> list[int]:
    if not link_ids:
        return []
    rows = (
        db.session.query(EquipmentGroupSetStation.station_id)
        .filter(EquipmentGroupSetStation.id.in_(link_ids))
        .all()
    )
    return [row[0] for row in rows if row[0] is not None]


def _localize_linked_groups_to_version(
    *,
    linked_groups: list[EquipmentGroup],
    version_id: Optional[int],
    link_ids: list[int],
    station_ids: list[int],
) -> list[EquipmentGroup]:
    """
    Если связь версии V указывает на группу другой версии — клонирует её в V
    и переносит связи/агрегаты этой версии (всех станций, не только текущей).
    Исходная группа других версий не удаляется.
    """
    localized: list[EquipmentGroup] = []
    seen_ids: set[int] = set()
    for group in linked_groups:
        if not group:
            continue
        local = _find_or_clone_group_in_version(group, version_id)
        if local.id != group.id:
            version_link_ids = _link_ids_for_group_in_version(group.id, version_id)
            move_link_ids = version_link_ids or list(link_ids or [])
            _reassign_sets_to_primary(
                [group.id],
                local.id,
                set_station_ids=move_link_ids,
            )
            move_station_ids = _station_ids_from_link_ids(move_link_ids) or list(
                station_ids or []
            )
            _reassign_machine_links_for_stations(
                group.id, local.id, move_station_ids
            )
        if local.id not in seen_ids:
            seen_ids.add(local.id)
            localized.append(local)
    return localized


def rename_or_merge_equipment_group_all_versions(
    *,
    station_external_code: str,
    equipment_group_id: int,
    equipment_group_type_id: int,
    new_name: str,
) -> dict:
    """
    Переименование группы оборудования во ВСЕХ версиях БД.

    В каждой версии БД отдельно:
    - находим группу этой станции/типа;
    - если связь указывает на карточку другой версии — клонируем её в текущую;
    - переименовываем;
    - объединяем только дубликаты с тем же именем в ЭТОЙ версии
      (две станции → одна группа этой версии).

    Группы разных версий между собой не сливаются.
    """
    from app.common.models.database_version_model import DatabaseVersion
    from app.common.services.database_version_filter import filter_by_explicit_db_version

    from app.generation.models.station.station_model import Station
    from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
        EquipmentGroupType,
    )

    if not new_name or not station_external_code:
        return {
            "versions_touched": 0,
            "renamed_count": 0,
            "merged_count": 0,
            "removed_count": 0,
            "results_by_version": [],
            "old_name": "",
            "new_name": new_name,
        }

    current_group = EquipmentGroup.query.filter_by(id=equipment_group_id).first()
    old_name = (current_group.name or "").strip() if current_group else ""

    new_name_norm = new_name.strip().lower()

    # ref_uuid и name текущего типа — для поиска эквивалента в других версиях
    current_type = EquipmentGroupType.query.get(equipment_group_type_id)
    type_ref_uuid = getattr(current_type, "ref_uuid", None) if current_type else None
    type_name = (current_type.name or "").strip() if current_type else ""

    def _resolve_type_id_for_version(vid: Optional[int]) -> Optional[int]:
        """Находит EquipmentGroupType.id для версии vid (тот же логический тип)."""
        if type_ref_uuid:
            q = EquipmentGroupType.query.filter(EquipmentGroupType.ref_uuid == type_ref_uuid)
            q = filter_by_explicit_db_version(q, EquipmentGroupType, vid)
            t = q.first()
            return t.id if t else None
        if type_name:
            q = EquipmentGroupType.query.filter(EquipmentGroupType.name == type_name)
            q = filter_by_explicit_db_version(q, EquipmentGroupType, vid)
            t = q.first()
            return t.id if t else None
        return None

    # Все версии: id из БД + None (legacy)
    version_ids: list[Optional[int]] = [None]
    for dv in DatabaseVersion.query.filter(DatabaseVersion.id.isnot(None)).all():
        if dv.id:
            version_ids.append(dv.id)

    versions_touched = 0
    renamed_count = 0
    merged_count = 0
    removed_count = 0
    results_by_version: list[dict] = []

    for version_id in version_ids:
        # equipment_group_type_id для этой версии (может отличаться от текущей)
        type_id_in_version = _resolve_type_id_for_version(version_id)
        if type_id_in_version is None:
            continue

        # Station.id в этой версии по external_code
        station_version_filter = (
            Station.database_version_id.is_(None)
            if version_id is None
            else (Station.database_version_id == version_id)
        )
        stations_in_version = (
            Station.query.filter_by(external_code=station_external_code)
            .filter(station_version_filter)
            .all()
        )
        station_ids = [s.id for s in stations_in_version]
        if not station_ids:
            continue

        # EquipmentGroupSetStation (gs_fue_equipment_group_type_stations) для этих станций,
        # типа группы (в этой версии) и версии
        link_filter = (
            EquipmentGroupSetStation.database_version_id.is_(None)
            if version_id is None
            else (EquipmentGroupSetStation.database_version_id == version_id)
        )
        station_links = (
            EquipmentGroupSetStation.query.filter(
                EquipmentGroupSetStation.station_id.in_(station_ids),
                EquipmentGroupSetStation.equipment_group_type_id == type_id_in_version,
                link_filter,
            )
            .all()
        )
        link_ids = [l.id for l in station_links]
        if not link_ids:
            continue

        # Группы по связям этой версии — без фильтра по версии самой группы:
        # связь могла указывать на карточку другой версии после ошибочного merge.
        linked_groups = (
            db.session.query(EquipmentGroup)
            .join(EquipmentGroupSet, EquipmentGroupSet.equipment_group_id == EquipmentGroup.id)
            .filter(EquipmentGroupSet.equipment_group_set_station_id.in_(link_ids))
            .distinct()
            .all()
        )
        if not linked_groups:
            continue

        all_station_groups = _localize_linked_groups_to_version(
            linked_groups=linked_groups,
            version_id=version_id,
            link_ids=link_ids,
            station_ids=station_ids,
        )
        if not all_station_groups:
            continue

        # Дубликаты по имени — только в этой же версии БД (не legacy + не другие версии)
        name_expr = func.lower(func.trim(func.coalesce(EquipmentGroup.name, "")))
        same_name_in_version = (
            db.session.query(EquipmentGroup)
            .filter(
                name_expr == new_name_norm,
                _strict_equipment_group_version_criterion(version_id),
            )
            .all()
        )
        groups_with_new = merge_candidates_for_version(
            all_station_groups,
            same_name_in_version,
            version_id,
        )
        if not groups_with_new:
            continue

        # Переименовываем группы, у которых имя отличается от new_name
        groups_to_rename = [
            g for g in groups_with_new
            if (g.name or "").strip().lower() != new_name_norm
        ]
        for g in groups_to_rename:
            g.name = new_name
            renamed_count += 1

        # Объединяем дубликаты, если их больше одной
        if len(groups_with_new) <= 1:
            versions_touched += 1
            results_by_version.append(
                {
                    "version_id": version_id,
                    "action": "renamed",
                    "count": len(groups_to_rename),
                }
            )
            continue

        primary = _choose_primary_group(groups_with_new)
        if not primary or not _is_group_in_version(primary, version_id):
            versions_touched += 1
            continue

        primary.name = new_name
        candidate_ids = [g.id for g in groups_with_new if g.id != primary.id]
        for g in groups_with_new:
            if g.id != primary.id:
                _merge_group_fields_return_list(primary, g)
        _reassign_group_detail_rows_to_primary(candidate_ids, primary.id)
        # Кандидаты уже той же версии — переносим все их связи, включая вторую станцию.
        _reassign_sets_to_primary(candidate_ids, primary.id)
        removed = _remove_orphan_groups(groups_with_new, primary.id)
        removed_count += removed
        merged_count += len(candidate_ids)
        versions_touched += 1
        results_by_version.append(
            {
                "version_id": version_id,
                "action": "merged",
                "renamed": len(groups_to_rename),
                "merged_into": primary.id,
                "removed": removed,
            }
        )

    return {
        "versions_touched": versions_touched,
        "renamed_count": renamed_count,
        "merged_count": merged_count,
        "removed_count": removed_count,
        "results_by_version": results_by_version,
        "old_name": old_name,
        "new_name": new_name,
    }


def _get_station_type_pairs_for_equipment_group(equipment_group_id: int) -> list[tuple[str, int]]:
    """
    Возвращает список (station_external_code, equipment_group_type_id) для всех связей
    группы оборудования через EquipmentGroupSet -> EquipmentGroupSetStation.
    """
    from app.generation.models.station.station_model import Station

    pairs: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    sets = EquipmentGroupSet.query.filter_by(equipment_group_id=equipment_group_id).all()
    for s in sets:
        link = EquipmentGroupSetStation.query.get(s.equipment_group_set_station_id)
        if not link:
            continue
        station = Station.query.get(link.station_id)
        if not station or not (station.external_code or "").strip():
            continue
        ext_code = (station.external_code or "").strip()
        key = (ext_code, link.equipment_group_type_id)
        if key not in seen:
            seen.add(key)
            pairs.append(key)
    return pairs


def _parse_int_form_val(val) -> Optional[int]:
    """Парсит значение из формы в int или None."""
    if not val or not str(val).strip():
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _resolve_equipment_group_type_id_for_version(
    anchor_type_id: int, version_id: Optional[int]
) -> Optional[int]:
    """ID типа группы в справочнике для версии vid по ref_uuid или имени якорной записи."""
    from app.common.services.version_entity_resolve_services import (
        resolve_equipment_group_type_id_for_version,
    )

    return resolve_equipment_group_type_id_for_version(anchor_type_id, version_id)


def _database_version_label(version_id: Optional[int]) -> str:
    """Фраза для вставки в текст предупреждения (после «для …»)."""
    if version_id is None:
        return "групп без указанной версии БД в данных"
    from app.common.models.database_version_model import DatabaseVersion

    dv = DatabaseVersion.query.get(version_id)
    if dv and getattr(dv, "version_number", None) is not None:
        return f"групп версии БД №{dv.version_number}"
    return f"групп (версия БД id={version_id})"


def _equipment_group_type_skip_message(version_id: Optional[int]) -> str:
    """Пояснение при «Сохранить во всех версиях», если тип не сопоставился со справочником."""
    scope = _database_version_label(version_id)
    return (
        f"Режим «Сохранить во всех версиях»: тип группы оборудования не обновлён для {scope}. "
        "В справочнике «Типы групп оборудования» нет строки с тем же типом (по коду/имени) "
        "и с той же версией БД, что ожидается для этих групп. "
        "Остальные поля могли сохраниться. Если нужна только текущая версия — нажмите «Сохранить», "
        "без «во всех версиях»."
    )


# Человекочитаемые названия полей для логов
_EQUIPMENT_GROUP_FIELD_LABELS = {
    "name": "Наименование",
    "name_ext": "Название (БД Топливо)",
    "niv": "Группа оборудования/составная станция",
    "comp": "Признак составной станции",
    "main": "Код группы оборудования",
    "d": "Признак действующей электростанции",
    "r": "Признак расширяемой электростанции",
    "forem": "Признак ФОРЭМ",
    "vedomstvo": "Ведомство",
    "obl": "Код субъекта РФ",
    "dep": "Код департамента",
    "oes": "Код ОЭС",
    "er": "Код экономического района",
    "fo": "Код федерального округа",
    "numb": "Код группы оборудования",
    "tm": "tm",
    "n1": "n1",
    "n2": "n2",
    "p1": "p1",
    "p2": "p2",
    "ordnumb": "Порядковый номер",
    "addr": "Адрес",
    "note": "Примечание",
    "codegor": "Код города",
    "be": "be",
    "gk": "Генерирующая компания",
    "gkf": "Филиал ГК",
    "k": "Коэффициент k",
    "regional_district_id": "Субъект РФ",
    "regional_energy_system_id": "Региональная энергосистема",
    "equipment_group_type_id": "Тип группы оборудования (связь со станцией)",
    "grouping_station_id": "Привязка к станции (Модуль «Генерация»)",
}


def _format_val_for_log(val) -> str:
    """Форматирует значение для отображения в логе."""
    if val is None:
        return "—"
    if isinstance(val, str):
        return val.strip() or "—"
    return str(val)


def _format_fk_for_log(field: str, pk_id) -> str:
    """Форматирует FK (regional_district_id, regional_energy_system_id) для лога: название или ID."""
    if pk_id is None:
        return "—"
    if field == "regional_district_id":
        from app.refdata.models.territories.regional_district_model import RegionalDistrict
        obj = RegionalDistrict.query.get(pk_id)
        if obj and hasattr(obj, "name"):
            return (obj.name or "").strip() or str(pk_id)
    elif field == "regional_energy_system_id":
        from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
        obj = RegionalEnergySystem.query.get(pk_id)
        if obj and hasattr(obj, "name"):
            return (obj.name or "").strip() or str(pk_id)
    elif field == "grouping_station_id":
        obj = Station.query.get(pk_id)
        if obj and hasattr(obj, "name"):
            return (obj.name or "").strip() or str(pk_id)
    elif field == "equipment_group_type_id":
        from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
            EquipmentGroupType,
        )

        obj = EquipmentGroupType.query.get(pk_id)
        if obj and hasattr(obj, "name"):
            return (obj.name or "").strip() or str(pk_id)
    return str(pk_id)


def _apply_egt_anchor_to_groups(
    groups: list,
    new_egt_anchor_id: Optional[int],
    version_id,
    equipment_group_type_skip_warnings: list[str],
) -> tuple[Optional[str], bool]:
    """
    Применяет тип группы из формы. new_egt_anchor_id is None — снять тип (прочерк).
    Returns (error, applied_any). Если тип не сопоставился со справочником версии —
    warning и applied_any=False.
    """
    from app.fuel.services.equipment_groups.equipment_group_edit_services import (
        _apply_equipment_group_type_change_from_form,
    )

    if new_egt_anchor_id is None:
        tid = None
    else:
        tid = _resolve_equipment_group_type_id_for_version(new_egt_anchor_id, version_id)
        if tid is None:
            equipment_group_type_skip_warnings.append(
                _equipment_group_type_skip_message(version_id)
            )
            return None, False
    applied = False
    for g in groups:
        err = _apply_equipment_group_type_change_from_form(g.id, tid, version_id)
        if err:
            return err, False
        applied = True
    return None, applied


def update_equipment_group_all_versions(
    *,
    equipment_group_id: int,
    form_data: dict,
) -> dict:
    """
    Применяет данные формы редактирования группы оборудования ко всем эквивалентным
    группам во всех версиях БД.

    form_data — словарь полей (name, name_ext, niv, comp, main, d, r, forem, vedomstvo, obl, dep,
    oes, er, fo, numb, tm, n1, n2, p1, p2, ordnumb, addr, note, codegor, be, gk, gkf,
    regional_district_id, regional_energy_system_id, equipment_group_type_id,
    grouping_station_id).

    Возвращает dict с versions_touched, updated_count, fallback_single (опционально).
    """
    from app.common.models.database_version_model import DatabaseVersion
    from app.common.services.database_version_filter import filter_by_explicit_db_version
    from app.common.services.version_entity_resolve_services import (
        resolve_refdata_fk_id_for_version,
    )
    from app.fuel.services.equipment_groups.equipment_group_edit_services import (
        _effective_group_database_version_id,
        _station_ids_from_group_set_rows,
        _validate_and_sync_composite_fields,
        form_has_grouping_station_sync,
        grouping_station_ids_from_form,
        persist_equipment_group_grouping_station_if_in_form,
    )

    raw_form = form_data or {}
    grouping_sync = form_has_grouping_station_sync(raw_form)
    grouping_ids = grouping_station_ids_from_form(raw_form) if grouping_sync else None
    grouping_loaded = None
    if grouping_sync and (
        "grouping_station_ids_loaded" in raw_form
        or "grouping_station_ids_loaded_present" in raw_form
    ):
        grouping_loaded = grouping_station_ids_from_form(
            raw_form, key="grouping_station_ids_loaded"
        )
    form_data = dict(raw_form)
    if grouping_sync:
        form_data["grouping_station_ids"] = grouping_ids or []
        form_data["grouping_station_ids_present"] = "1"
        if grouping_loaded is not None:
            form_data["grouping_station_ids_loaded"] = grouping_loaded
            form_data["grouping_station_ids_loaded_present"] = "1"

    text_fields = [
        "name",
        "name_ext",
        "tm",
        "n1",
        "n2",
        "p1",
        "p2",
        "ordnumb",
        "addr",
        "note",
    ]
    int_fields = [
        "niv",
        "comp",
        "main",
        "d",
        "r",
        "forem",
        "vedomstvo",
        "numb",
        "obl",
        "dep",
        "oes",
        "er",
        "fo",
        "codegor",
        "be",
        "gk",
        "gkf",
    ]
    int_fk_fields = ["regional_district_id", "regional_energy_system_id"]

    def _parse_decimal_form_val(val):
        from decimal import Decimal, InvalidOperation
        if not val or not str(val).strip():
            return None
        try:
            return Decimal(str(val).strip().replace(",", "."))
        except (InvalidOperation, ValueError, TypeError):
            return None

    values = {}
    for field in text_fields:
        val = form_data.get(field)
        if val is not None:
            values[field] = (val.strip() if val else None)
    for field in int_fields:
        if field not in form_data:
            continue
        values[field] = _parse_int_form_val(form_data.get(field))
    k_val = form_data.get("k")
    if k_val is not None:
        values["k"] = _parse_decimal_form_val(k_val)
    for field in int_fk_fields:
        val = form_data.get(field)
        if val is not None:
            parsed = _parse_int_form_val(val)
            values[field] = parsed

    egt_in_form = "equipment_group_type_id" in form_data
    new_egt_anchor_id: Optional[int] = None
    if egt_in_form:
        raw_egt = form_data.get("equipment_group_type_id")
        if raw_egt is not None and str(raw_egt).strip():
            new_egt_anchor_id = _parse_int_form_val(raw_egt)

    if not values and not egt_in_form:
        if not grouping_sync and "grouping_station_id" not in form_data:
            return {"versions_touched": 0, "updated_count": 0}

    # ID из формы — для текущей версии; в других версиях ищем соответствие по ref_uuid / external_code
    new_rd_id = _parse_int_form_val(form_data.get("regional_district_id"))
    new_res_id = _parse_int_form_val(form_data.get("regional_energy_system_id"))
    from app.refdata.models.territories.regional_district_model import RegionalDistrict
    from app.refdata.models.energy_systems.regional_energy_system_model import (
        RegionalEnergySystem,
    )

    def _resolve_rd_id_for_version(vid: Optional[int]) -> Optional[int]:
        if not new_rd_id:
            return None
        return resolve_refdata_fk_id_for_version(
            RegionalDistrict, new_rd_id, vid
        )

    def _resolve_res_id_for_version(vid: Optional[int]) -> Optional[int]:
        if not new_res_id:
            return None
        return resolve_refdata_fk_id_for_version(
            RegionalEnergySystem, new_res_id, vid
        )

    def _apply_values_to_group(
        group: EquipmentGroup, values_to_apply: dict | None = None
    ) -> tuple[bool, list[tuple[str, str, str]]]:
        """Применяет значения к группе. Возвращает (changed, [(field_label, old_val, new_val), ...])."""
        v = values_to_apply if values_to_apply is not None else values
        changes: list[tuple[str, str, str]] = []
        for field, val in v.items():
            if hasattr(group, field):
                old_val = getattr(group, field, None)
                if old_val != val:
                    setattr(group, field, val)
                    label = _EQUIPMENT_GROUP_FIELD_LABELS.get(field, field)
                    if field in ("regional_district_id", "regional_energy_system_id"):
                        old_str = _format_fk_for_log(field, old_val)
                        new_str = _format_fk_for_log(field, val)
                    else:
                        old_str = _format_val_for_log(old_val)
                        new_str = _format_val_for_log(val)
                    changes.append((label, old_str, new_str))
        if any(f in v for f in ("main", "comp", "niv", "numb")):
            verr = _validate_and_sync_composite_fields(group)
            if verr:
                raise ValueError(verr)
        return bool(changes), changes

    def _grouping_ids_for_group(group: EquipmentGroup) -> list[int]:
        return _station_ids_from_group_set_rows(
            EquipmentGroupSet.query.filter_by(equipment_group_id=group.id).all(),
            _effective_group_database_version_id(group),
        )

    def _format_station_ids_log(ids: list[int]) -> str:
        if not ids:
            return "не указано"
        return ", ".join(
            _format_fk_for_log("grouping_station_id", sid) for sid in ids
        )

    def _apply_grouping_stations_from_form(
        group: EquipmentGroup, persist_version_id
    ) -> tuple[Optional[str], bool, Optional[tuple[str, str, str]]]:
        if not grouping_sync and "grouping_station_id" not in form_data:
            return None, False, None
        old_ids = _grouping_ids_for_group(group)
        err = persist_equipment_group_grouping_station_if_in_form(
            group, form_data, version_id=persist_version_id
        )
        if err:
            return err, False, None
        new_ids = _grouping_ids_for_group(group)
        if old_ids == new_ids:
            return None, False, None
        return (
            None,
            True,
            (
                _EQUIPMENT_GROUP_FIELD_LABELS.get(
                    "grouping_station_id", "Станция для группировки"
                ),
                _format_station_ids_log(old_ids),
                _format_station_ids_log(new_ids),
            ),
        )

    # Ищем группы во всех версиях ТОЛЬКО по external_code (никак иначе)
    current_group = EquipmentGroup.query.filter_by(id=equipment_group_id).first()
    if not current_group:
        return {"versions_touched": 0, "updated_count": 0}
    external_code = (current_group.external_code or "").strip()
    if not external_code:
        # Fallback: обновить только текущую группу
        _, change_details = _apply_values_to_group(current_group, values)
        out_details = list(change_details or [])
        if grouping_sync or "grouping_station_id" in form_data:
            egs_err_fb, grouping_changed_fb, grouping_log_fb = (
                _apply_grouping_stations_from_form(
                    current_group,
                    _effective_group_database_version_id(current_group),
                )
            )
            if egs_err_fb:
                return {
                    "versions_touched": 0,
                    "updated_count": 0,
                    "error": egs_err_fb,
                }
            if grouping_changed_fb and grouping_log_fb:
                out_details.append(grouping_log_fb)
        if egt_in_form:
            old_egt_fb = None
            s0 = EquipmentGroupSet.query.filter_by(
                equipment_group_id=current_group.id
            ).first()
            if s0:
                lnk0 = EquipmentGroupSetStation.query.get(
                    s0.equipment_group_set_station_id
                )
                if lnk0:
                    old_egt_fb = lnk0.equipment_group_type_id
            egt_skips_fb: list[str] = []
            egt_err_fb, egt_applied = _apply_egt_anchor_to_groups(
                [current_group],
                new_egt_anchor_id,
                _effective_group_database_version_id(current_group),
                egt_skips_fb,
            )
            if egt_err_fb:
                return {
                    "versions_touched": 0,
                    "updated_count": 0,
                    "error": egt_err_fb,
                }
            if egt_applied and old_egt_fb != new_egt_anchor_id:
                out_details.append(
                    (
                        _EQUIPMENT_GROUP_FIELD_LABELS.get(
                            "equipment_group_type_id",
                            "Тип группы оборудования (связь со станцией)",
                        ),
                        _format_fk_for_log("equipment_group_type_id", old_egt_fb),
                        _format_fk_for_log(
                            "equipment_group_type_id", new_egt_anchor_id
                        ),
                    )
                )
            if egt_skips_fb and not out_details:
                return {
                    "versions_touched": 0,
                    "updated_count": 0,
                    "no_changes": True,
                    "equipment_group_type_skip_warnings": egt_skips_fb,
                    "equipment_group_type_only_skipped": True,
                }
        if not out_details:
            return {"versions_touched": 0, "updated_count": 0, "no_changes": True}
        return {
            "versions_touched": 0,
            "updated_count": 1,
            "fallback_single": True,
            "change_details": out_details,
        }

    # Все версии
    version_ids: list[Optional[int]] = [None]
    for dv in DatabaseVersion.query.filter(DatabaseVersion.id.isnot(None)).all():
        if dv.id:
            version_ids.append(dv.id)

    versions_touched_set: set[Optional[int]] = set()
    updated_count = 0
    updated_ids: set[int] = set()
    matched_any = False
    change_details: list[tuple[str, str, str]] = []  # (field_label, old_val, new_val)
    equipment_group_type_skip_warnings: list[str] = []

    from app.common.services.tranzaction_services import quick_fix_seq
    from config import SCHEMA_FUEL

    for seq_table in (
        "gs_fue_equipment_groups",
        "gs_fue_equipment_group_sets",
        "gs_fue_equipment_group_type_stations",
    ):
        try:
            quick_fix_seq(SCHEMA_FUEL, seq_table, "id")
        except Exception:
            pass

    # Для каждой версии: ищем группы ТОЛЬКО по external_code
    for version_id in version_ids:
        eg_version_filter = (
            EquipmentGroup.database_version_id.is_(None)
            if version_id is None
            else (EquipmentGroup.database_version_id == version_id)
        )
        groups_to_update = (
            EquipmentGroup.query.filter_by(external_code=external_code)
            .filter(eg_version_filter)
            .all()
        )
        if not groups_to_update:
            continue
        matched_any = True

        # Объединяем дубликаты, если их больше одной
        if len(groups_to_update) > 1:
            primary = _choose_primary_group(groups_to_update)
            if primary:
                candidate_ids = [g.id for g in groups_to_update if g.id != primary.id]
                for g in groups_to_update:
                    if g.id != primary.id:
                        _merge_group_fields_return_list(primary, g)
                _reassign_group_detail_rows_to_primary(candidate_ids, primary.id)
                _reassign_sets_to_primary(candidate_ids, primary.id)
                _remove_orphan_groups(groups_to_update, primary.id)
                groups_to_update = [primary]

        values_to_apply = dict(values)
        if "regional_district_id" in form_data:
            if new_rd_id is None:
                values_to_apply["regional_district_id"] = None
            else:
                resolved_rd_id = _resolve_rd_id_for_version(version_id)
                if resolved_rd_id is not None:
                    values_to_apply["regional_district_id"] = resolved_rd_id
                else:
                    values_to_apply.pop("regional_district_id", None)
        if "regional_energy_system_id" in form_data:
            if new_res_id is None:
                values_to_apply["regional_energy_system_id"] = None
            else:
                resolved_res_id = _resolve_res_id_for_version(version_id)
                if resolved_res_id is not None:
                    values_to_apply["regional_energy_system_id"] = resolved_res_id
                else:
                    values_to_apply.pop("regional_energy_system_id", None)

        version_changed = False
        field_changed_ids: set[int] = set()
        for g in groups_to_update:
            if g.id not in updated_ids:
                updated_ids.add(g.id)
                changed, changes = _apply_values_to_group(g, values_to_apply)
                if changed:
                    field_changed_ids.add(g.id)
                    updated_count += 1
                    version_changed = True
                    if not change_details:
                        change_details = changes
        if grouping_sync or "grouping_station_id" in form_data:
            for g in groups_to_update:
                egs_err, grouping_changed, grouping_log = (
                    _apply_grouping_stations_from_form(g, version_id)
                )
                if egs_err:
                    return {
                        "versions_touched": 0,
                        "updated_count": 0,
                        "error": egs_err,
                    }
                if grouping_changed:
                    version_changed = True
                    if g.id not in field_changed_ids:
                        updated_count += 1
                        field_changed_ids.add(g.id)
                    if grouping_log and not change_details:
                        change_details = [grouping_log]
        if egt_in_form and groups_to_update:
            egt_err, egt_any = _apply_egt_anchor_to_groups(
                groups_to_update,
                new_egt_anchor_id,
                version_id,
                equipment_group_type_skip_warnings,
            )
            if egt_err:
                return {
                    "versions_touched": 0,
                    "updated_count": 0,
                    "error": egt_err,
                }
            if egt_any:
                version_changed = True
                for g in groups_to_update:
                    if g.id not in field_changed_ids:
                        updated_count += 1
                        field_changed_ids.add(g.id)
                if not change_details:
                    change_details = [
                        (
                            _EQUIPMENT_GROUP_FIELD_LABELS.get(
                                "equipment_group_type_id",
                                "Тип группы оборудования (связь со станцией)",
                            ),
                            "—",
                            _format_fk_for_log(
                                "equipment_group_type_id", new_egt_anchor_id
                            ),
                        )
                    ]
        if version_changed:
            versions_touched_set.add(version_id)

    # Гарантированно обновить группу, которую просматривает пользователь
    if equipment_group_id not in updated_ids:
        user_group = EquipmentGroup.query.filter_by(id=equipment_group_id).first()
        if user_group:
            vid = getattr(user_group, "database_version_id", None)
            eff_u = _effective_group_database_version_id(user_group)
            values_to_apply = dict(values)
            if "regional_district_id" in form_data:
                if new_rd_id is None:
                    values_to_apply["regional_district_id"] = None
                else:
                    resolved_rd_id = _resolve_rd_id_for_version(vid)
                    if resolved_rd_id is not None:
                        values_to_apply["regional_district_id"] = resolved_rd_id
                    else:
                        values_to_apply.pop("regional_district_id", None)
            if "regional_energy_system_id" in form_data:
                if new_res_id is None:
                    values_to_apply["regional_energy_system_id"] = None
                else:
                    resolved_res_id = _resolve_res_id_for_version(vid)
                    if resolved_res_id is not None:
                        values_to_apply["regional_energy_system_id"] = resolved_res_id
                    else:
                        values_to_apply.pop("regional_energy_system_id", None)
            matched_any = True
            changed, changes = _apply_values_to_group(user_group, values_to_apply)
            grouping_changed_u = False
            if grouping_sync or "grouping_station_id" in form_data:
                egs_err_u2, grouping_changed_u, grouping_log_u = (
                    _apply_grouping_stations_from_form(user_group, eff_u)
                )
                if egs_err_u2:
                    return {
                        "versions_touched": 0,
                        "updated_count": 0,
                        "error": egs_err_u2,
                    }
                if grouping_changed_u and grouping_log_u and not change_details:
                    change_details = [grouping_log_u]
            if changed:
                updated_count += 1
                versions_touched_set.add(vid)
                if not change_details:
                    change_details = changes
            elif grouping_changed_u:
                updated_count += 1
                versions_touched_set.add(vid)
            if egt_in_form:
                egt_err_u, egt_applied_u = _apply_egt_anchor_to_groups(
                    [user_group],
                    new_egt_anchor_id,
                    eff_u,
                    equipment_group_type_skip_warnings,
                )
                if egt_err_u:
                    return {
                        "versions_touched": 0,
                        "updated_count": 0,
                        "error": egt_err_u,
                    }
                if egt_applied_u:
                    if not changed:
                        updated_count += 1
                    versions_touched_set.add(vid)
                    if not change_details:
                        change_details = [
                            (
                                _EQUIPMENT_GROUP_FIELD_LABELS.get(
                                    "equipment_group_type_id",
                                    "Тип группы оборудования (связь со станцией)",
                                ),
                                "—",
                                _format_fk_for_log(
                                    "equipment_group_type_id", new_egt_anchor_id
                                ),
                            )
                        ]

    result = {
        "versions_touched": len(versions_touched_set),
        "updated_count": updated_count,
        "change_details": change_details,
    }
    if equipment_group_type_skip_warnings:
        result["equipment_group_type_skip_warnings"] = equipment_group_type_skip_warnings
    if matched_any and updated_count == 0:
        if new_egt_anchor_id and equipment_group_type_skip_warnings:
            result["equipment_group_type_only_skipped"] = True
        else:
            result["no_changes"] = True
    return result

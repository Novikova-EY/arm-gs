# -*- coding: utf-8 -*-
"""
Перенос привязки агрегатов с одной итоговой группы оборудования на другую.

Нужен для составных станций: агрегат часто висит на родителе (comp=1),
а топливные параметры живут на дочерней группе (main=parent.numb).
Список выбора на machine_details дополняется кластером parent+children,
даже если у дочерней группы еще нет EquipmentGroupSet.
"""
from __future__ import annotations

from typing import Iterable

from app.extensions import db
from app.common.services.database_version_filter import (
    get_current_db_version_id,
    set_db_version_on_create,
)
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
from app.fuel.services.equipment_groups.composite_station_semantics import (
    _as_int,
    is_composite_child_group,
    is_composite_parent_group,
)
from app.generation.models.machine.machine_model import Machine
from app.generation.models.station.station_model import Station


def format_equipment_group_choice_label(group) -> str:
    """Подпись для селекта: «1502 – Название (составная)»."""
    if group is None:
        return "–"
    name = (getattr(group, "name", None) or getattr(group, "name_ext", None) or "").strip()
    if not name:
        name = f"Группа #{getattr(group, 'id', '–')}"
    numb = _as_int(getattr(group, "numb", None))
    prefix = f"{numb} – " if numb is not None else ""
    suffix = " (составная)" if is_composite_parent_group(group) else ""
    return f"{prefix}{name}{suffix}"


def composite_cluster_lookup_keys(seed_groups: Iterable) -> tuple[set[int], set[int]]:
    """
    Ключи поиска кластера составной станции.

    Returns:
        parent_numbs – numb родителей, по ним ищем детей (main=numb);
        child_mains – main детей, по ним ищем родителя и сиблингов.
    """
    parent_numbs: set[int] = set()
    child_mains: set[int] = set()
    for group in seed_groups or []:
        if group is None:
            continue
        if is_composite_parent_group(group):
            numb = _as_int(getattr(group, "numb", None))
            if numb is not None:
                parent_numbs.add(numb)
        if is_composite_child_group(group):
            main = _as_int(getattr(group, "main", None))
            if main is not None:
                child_mains.add(main)
    return parent_numbs, child_mains


def _apply_group_version_filter(query, version_id: int | None):
    if version_id is None:
        return query.filter(EquipmentGroup.database_version_id.is_(None))
    return query.filter(EquipmentGroup.database_version_id == version_id)


def _load_groups_by_criterion(criterion, version_id: int | None) -> list[EquipmentGroup]:
    rows = _apply_group_version_filter(
        EquipmentGroup.query.filter(criterion),
        version_id,
    ).all()
    if rows or version_id is None:
        return rows
    return (
        EquipmentGroup.query.filter(criterion)
        .filter(EquipmentGroup.database_version_id.is_(None))
        .all()
    )


def collect_composite_cluster_groups(
    seed_groups: Iterable[EquipmentGroup],
    version_id: int | None,
) -> list[EquipmentGroup]:
    """Родитель + дети + сиблинги для уже известных групп той же версии БД."""
    by_id: dict[int, EquipmentGroup] = {}
    for group in seed_groups or []:
        if group is None or getattr(group, "id", None) is None:
            continue
        by_id[int(group.id)] = group

    parent_numbs, child_mains = composite_cluster_lookup_keys(by_id.values())
    mains_for_children = parent_numbs | child_mains
    if mains_for_children:
        for child in _load_groups_by_criterion(
            EquipmentGroup.main.in_(mains_for_children),
            version_id,
        ):
            by_id[int(child.id)] = child
    if child_mains:
        for parent in _load_groups_by_criterion(
            EquipmentGroup.numb.in_(child_mains),
            version_id,
        ):
            by_id[int(parent.id)] = parent
    return _prefer_current_version_groups(by_id.values(), version_id)


def _choice_group_identity_key(group) -> str:
    code = (getattr(group, "external_code", None) or "").strip()
    if code:
        return f"code:{code}"
    numb = _as_int(getattr(group, "numb", None))
    name = (getattr(group, "name", None) or getattr(group, "name_ext", None) or "").strip().lower()
    if numb is not None or name:
        return f"numb:{numb or ''}|name:{name}"
    return f"id:{getattr(group, 'id', None)}"


def _prefer_current_version_groups(
    groups: Iterable[EquipmentGroup],
    version_id: int | None,
) -> list[EquipmentGroup]:
    """
    Одна строка на external_code (или numb+name): текущая версия БД, иначе legacy NULL.
    Иначе в селекте карточки агрегата две копии с одним numb (версия + без версии).
    """
    items = [group for group in groups or [] if group is not None]
    if version_id is None:
        return [group for group in items if getattr(group, "database_version_id", None) is None]

    def _rank(group) -> tuple:
        gvid = getattr(group, "database_version_id", None)
        return (
            0 if gvid == version_id else 1,
            0 if gvid is not None else 1,
            -(int(getattr(group, "id", 0) or 0)),
        )

    by_key: dict[str, EquipmentGroup] = {}
    for group in items:
        key = _choice_group_identity_key(group)
        current = by_key.get(key)
        if current is None or _rank(group) < _rank(current):
            by_key[key] = group
    return list(by_key.values())


def _sort_choice_groups(groups: Iterable[EquipmentGroup]) -> list[EquipmentGroup]:
    def _key(group: EquipmentGroup):
        numb = _as_int(getattr(group, "numb", None))
        name = (getattr(group, "name", None) or "").strip().lower()
        return (numb is None, numb if numb is not None else 0, name, int(group.id))

    return sorted((g for g in groups if g is not None), key=_key)


def _linked_equipment_groups_for_station(
    station_id: int,
    version_id: int | None,
) -> list[EquipmentGroup]:
    link_q = EquipmentGroupSetStation.query.filter(
        EquipmentGroupSetStation.station_id == station_id,
    )
    if version_id is None:
        link_q = link_q.filter(EquipmentGroupSetStation.database_version_id.is_(None))
    else:
        link_q = link_q.filter(EquipmentGroupSetStation.database_version_id == version_id)

    link_ids = [row.id for row in link_q.with_entities(EquipmentGroupSetStation.id).all()]
    if not link_ids:
        return []

    rows = (
        db.session.query(EquipmentGroup)
        .join(
            EquipmentGroupSet,
            EquipmentGroupSet.equipment_group_id == EquipmentGroup.id,
        )
        .filter(EquipmentGroupSet.equipment_group_set_station_id.in_(link_ids))
        .distinct()
        .all()
    )
    return _prefer_current_version_groups(rows, version_id)


def linked_station_ids_for_equipment_group(
    equipment_group_id: int | None,
    version_id: int | None,
) -> list[int]:
    """Станции текущей версии БД, с которыми связана итоговая группа."""
    if not equipment_group_id:
        return []
    query = (
        db.session.query(EquipmentGroupSetStation.station_id)
        .join(
            EquipmentGroupSet,
            EquipmentGroupSet.equipment_group_set_station_id == EquipmentGroupSetStation.id,
        )
        .filter(
            EquipmentGroupSet.equipment_group_id == equipment_group_id,
            EquipmentGroupSetStation.station_id.isnot(None),
        )
        .distinct()
    )
    if version_id is None:
        query = query.filter(EquipmentGroupSetStation.database_version_id.is_(None))
    else:
        query = query.filter(EquipmentGroupSetStation.database_version_id == version_id)
    return [int(row[0]) for row in query.all() if row[0] is not None]


def station_is_primary_owner_of_equipment_group(
    station_id: int | None,
    equipment_group_id: int | None,
    version_id: int | None = None,
) -> bool:
    """Станция «владеет» группой: единственная связь или первая по имени среди связанных.

    Общая группа «ТЭС-2 и ТЭС-3…» показывается на ТЭС-2, но не на ТЭС-3.
    """
    if station_id is None or equipment_group_id is None:
        return False
    if version_id is None:
        version_id = get_current_db_version_id()
    linked_ids = linked_station_ids_for_equipment_group(equipment_group_id, version_id)
    if int(station_id) not in linked_ids:
        return False
    if len(linked_ids) == 1:
        return True
    stations = Station.query.filter(Station.id.in_(linked_ids)).all()
    ordered = sorted(
        stations,
        key=lambda item: ((getattr(item, "name", None) or "").casefold(), int(item.id)),
    )
    return bool(ordered) and int(ordered[0].id) == int(station_id)


def get_station_fuel_equipment_group_choice_tuples(
    station_id: int,
    version_id: int | None = None,
) -> list[tuple[int, str]]:
    """
    Группы для селекта на machine_details: связанные со станцией
    (включая общую группу нескольких станций)
    плюс кластер составной станции (дети/родитель без собственной связки).
    """
    if version_id is None:
        version_id = get_current_db_version_id()

    linked = _linked_equipment_groups_for_station(station_id, version_id)
    if not linked:
        return []
    groups = collect_composite_cluster_groups(linked, version_id)
    groups = _prefer_current_version_groups(groups, version_id)
    return [
        (int(group.id), format_equipment_group_choice_label(group))
        for group in _sort_choice_groups(groups)
    ]


def get_rebind_target_choices_for_group(
    group: EquipmentGroup | None,
    version_id: int | None = None,
) -> list[tuple[int, str]]:
    """Цели переноса с карточки группы: кластер составной станции без текущей группы."""
    if group is None or getattr(group, "id", None) is None:
        return []
    if version_id is None:
        version_id = getattr(group, "database_version_id", None)
        if version_id is None:
            version_id = get_current_db_version_id()

    seed = [group]
    source_id = int(group.id)
    set_rows = EquipmentGroupSet.query.filter_by(equipment_group_id=source_id).all()
    station_ids: set[int] = set()
    for set_row in set_rows:
        link = getattr(set_row, "equipment_group_set_station", None)
        station_id = getattr(link, "station_id", None) if link else None
        if station_id is not None:
            station_ids.add(int(station_id))
    for station_id in station_ids:
        seed.extend(_linked_equipment_groups_for_station(station_id, version_id))

    cluster = collect_composite_cluster_groups(seed, version_id)
    cluster = _prefer_current_version_groups(cluster, version_id)
    return [
        (int(item.id), format_equipment_group_choice_label(item))
        for item in _sort_choice_groups(cluster)
        if int(item.id) != source_id
    ]


def count_machines_bound_to_equipment_group(
    equipment_group_id: int,
    version_id: int | None,
) -> int:
    query = MachineFuelParam.query.filter(
        MachineFuelParam.equipment_group_id == equipment_group_id,
        MachineFuelParam.machine_id.isnot(None),
    )
    if version_id is None:
        query = query.filter(MachineFuelParam.database_version_id.is_(None))
    else:
        query = query.filter(MachineFuelParam.database_version_id == version_id)
    return int(query.count() or 0)


def _get_machine_fuel_param(machine_id: int, version_id: int | None) -> MachineFuelParam | None:
    """
    Одна запись на агрегат (uq_machine_fuel_param_machine_id).
    Сначала ищем точное совпадение версии, иначе любую строку этого machine_id.
    """
    by_machine = MachineFuelParam.query.filter(MachineFuelParam.machine_id == machine_id)
    if version_id is None:
        exact = by_machine.filter(MachineFuelParam.database_version_id.is_(None)).first()
    else:
        exact = by_machine.filter(MachineFuelParam.database_version_id == version_id).first()
    if exact is not None:
        return exact
    return by_machine.first()


def _ensure_machine_fuel_param(machine_id: int, version_id: int | None) -> MachineFuelParam:
    row = _get_machine_fuel_param(machine_id, version_id)
    if row is not None:
        if version_id is not None and row.database_version_id != version_id:
            row.database_version_id = version_id
            db.session.add(row)
        return row
    row = MachineFuelParam(machine_id=machine_id)
    if version_id is not None:
        row.database_version_id = version_id
    else:
        current = get_current_db_version_id()
        if current is not None:
            set_db_version_on_create(row)
    db.session.add(row)
    db.session.flush()
    return row


def ensure_equipment_group_linked_to_station(
    *,
    equipment_group_id: int,
    station_id: int | None,
    version_id: int | None,
    equipment_group_type_id: int | None = None,
) -> EquipmentGroupSet | None:
    """
    Гарантирует EquipmentGroupSet группы на станции указанной версии БД.

    Станция и тип группы приводятся к version_id (external_code / ref_uuid).
    Если связки нет – создает EquipmentGroupSetStation в этой версии.
    Смешанные связи (клон станции другой версии при database_version_id=version_id)
    переносятся на каноническую строку.
    """
    if not equipment_group_id or not station_id:
        return None

    from app.common.services.version_entity_resolve_services import (
        resolve_fuel_equipment_group_id_for_version,
    )
    from app.fuel.services.equipment_groups.equipment_group_set_services import (
        _create_equipment_group_set_with_retry,
        find_or_create_versioned_equipment_group_set_station,
        resolve_station_and_type_for_version,
        retarget_mismatched_version_links_for_group,
    )

    resolved_group_id = resolve_fuel_equipment_group_id_for_version(
        int(equipment_group_id), version_id
    )
    if resolved_group_id:
        equipment_group_id = int(resolved_group_id)

    resolved_station_id, resolved_type_id = resolve_station_and_type_for_version(
        station_id, equipment_group_type_id, version_id
    )
    if resolved_station_id is None:
        return None
    station_id = resolved_station_id
    if resolved_type_id is not None:
        equipment_group_type_id = resolved_type_id
    elif equipment_group_type_id is not None:
        equipment_group_type_id = None

    existing_sets = (
        EquipmentGroupSet.query.join(
            EquipmentGroupSetStation,
            EquipmentGroupSetStation.id
            == EquipmentGroupSet.equipment_group_set_station_id,
        )
        .filter(
            EquipmentGroupSet.equipment_group_id == equipment_group_id,
            EquipmentGroupSetStation.station_id == station_id,
        )
    )
    if version_id is None:
        existing_sets = existing_sets.filter(
            EquipmentGroupSetStation.database_version_id.is_(None)
        )
    else:
        existing_sets = existing_sets.filter(
            EquipmentGroupSetStation.database_version_id == version_id
        )
    if equipment_group_type_id is not None:
        typed = existing_sets.filter(
            EquipmentGroupSetStation.equipment_group_type_id == equipment_group_type_id
        ).first()
        if typed:
            retarget_mismatched_version_links_for_group(
                equipment_group_id, typed.equipment_group_set_station, version_id
            )
            return typed
    existing = existing_sets.first()
    if existing:
        retarget_mismatched_version_links_for_group(
            equipment_group_id, existing.equipment_group_set_station, version_id
        )
        return existing

    link = None
    if equipment_group_type_id is not None:
        link = find_or_create_versioned_equipment_group_set_station(
            station_id, equipment_group_type_id, version_id
        )
    if link is None:
        link_q = EquipmentGroupSetStation.query.filter(
            EquipmentGroupSetStation.station_id == station_id,
        )
        if version_id is None:
            link_q = link_q.filter(EquipmentGroupSetStation.database_version_id.is_(None))
        else:
            link_q = link_q.filter(
                EquipmentGroupSetStation.database_version_id == version_id
            )
        link = link_q.first()
    if link is None:
        return None

    created = _create_equipment_group_set_with_retry(equipment_group_id, link.id)
    retarget_mismatched_version_links_for_group(equipment_group_id, link, version_id)
    return created


def infer_equipment_group_type_id_for_station_group(
    *,
    station_id: int | None,
    equipment_group_id: int | None = None,
    version_id: int | None = None,
) -> int | None:
    """Тип группы по связке станция (+ топливная группа) в версии БД.

    Если подходящих типов несколько – None (неоднозначно).
    """
    if not station_id:
        return None
    query = (
        db.session.query(EquipmentGroupSetStation.equipment_group_type_id)
        .join(
            EquipmentGroupSet,
            EquipmentGroupSet.equipment_group_set_station_id
            == EquipmentGroupSetStation.id,
        )
        .filter(EquipmentGroupSetStation.station_id == int(station_id))
        .filter(EquipmentGroupSetStation.equipment_group_type_id.isnot(None))
    )
    if version_id is None:
        query = query.filter(EquipmentGroupSetStation.database_version_id.is_(None))
    else:
        query = query.filter(
            EquipmentGroupSetStation.database_version_id == version_id
        )
    if equipment_group_id:
        query = query.filter(
            EquipmentGroupSet.equipment_group_id == int(equipment_group_id)
        )
    type_ids = {
        row[0] for row in query.distinct().all() if row[0] is not None
    }
    if len(type_ids) != 1:
        return None
    return next(iter(type_ids))


def apply_inferred_equipment_group_type_to_machine(
    machine: Machine | None,
    *,
    version_id: int | None,
    equipment_group_id: int | None = None,
) -> int | None:
    """Заполняет пустой Machine.id_equipment_group по связке станции."""
    if machine is None or getattr(machine, "id_equipment_group", None):
        return None
    inferred = infer_equipment_group_type_id_for_station_group(
        station_id=getattr(machine, "id_station", None),
        equipment_group_id=equipment_group_id,
        version_id=version_id,
    )
    if inferred is None and equipment_group_id:
        inferred = infer_equipment_group_type_id_for_station_group(
            station_id=getattr(machine, "id_station", None),
            equipment_group_id=None,
            version_id=version_id,
        )
    if inferred is None:
        return None
    machine.id_equipment_group = inferred
    db.session.add(machine)
    return inferred


def rebind_machine_to_equipment_group(
    *,
    machine: Machine | None,
    target_group_id: int,
    version_id: int | None = None,
) -> dict:
    """
    Привязывает агрегат к итоговой группе: создает связку со станцией при необходимости,
    пишет MachineFuelParam.equipment_group_id и numb1120.
    Если у агрегата не заполнен тип группы, берет его из связки станции.
    """
    if machine is None or not getattr(machine, "id", None):
        return {"error": "Агрегат не найден.", "changed": False}
    target = EquipmentGroup.query.get(int(target_group_id))
    if target is None:
        return {"error": "Целевая группа оборудования не найдена.", "changed": False}

    if version_id is None:
        version_id = getattr(machine, "database_version_id", None)
        if version_id is None:
            version_id = get_current_db_version_id()

    ensure_equipment_group_linked_to_station(
        equipment_group_id=int(target.id),
        station_id=getattr(machine, "id_station", None),
        version_id=version_id,
        equipment_group_type_id=getattr(machine, "id_equipment_group", None),
    )
    inferred_type_id = apply_inferred_equipment_group_type_to_machine(
        machine,
        version_id=version_id,
        equipment_group_id=int(target.id),
    )
    if inferred_type_id is not None:
        ensure_equipment_group_linked_to_station(
            equipment_group_id=int(target.id),
            station_id=getattr(machine, "id_station", None),
            version_id=version_id,
            equipment_group_type_id=inferred_type_id,
        )

    mfp = _ensure_machine_fuel_param(int(machine.id), version_id)
    old_id = mfp.equipment_group_id
    old_numb1120 = mfp.numb1120
    mfp.equipment_group_id = int(target.id)
    target_numb = _as_int(getattr(target, "numb", None))
    if target_numb is not None:
        mfp.numb1120 = target_numb
    db.session.add(mfp)

    return {
        "changed": old_id != int(target.id) or (
            target_numb is not None and old_numb1120 != target_numb
        ) or inferred_type_id is not None,
        "old_group_id": old_id,
        "new_group_id": int(target.id),
        "old_numb1120": old_numb1120,
        "new_numb1120": mfp.numb1120,
        "inferred_type_id": inferred_type_id,
        "target_label": format_equipment_group_choice_label(target),
        "machine_id": int(machine.id),
    }


def _move_group_parameters(
    source: EquipmentGroup,
    target: EquipmentGroup,
    version_id: int | None,
) -> int | None:
    """Переносит параметры между головой и ГО, не затирая цель пустой оболочкой."""
    from app.common.services.get_services.years.years_get_services import get_reference_years
    from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
    from app.fuel.models.fue_equipment_group_extra_fuel_param_model import EquipmentGroupExtraFuelParam
    from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import EquipmentGroupSpecificFuelConsumption
    from app.fuel.models.fue_equipment_group_specific_fuel_cost_model import EquipmentGroupSpecificFuelCost
    from app.fuel.models.fue_equipment_group_specific_fuel_price_model import EquipmentGroupSpecificFuelPrice
    from app.fuel.models.fue_equipment_group_natural_fuel_model import EquipmentGroupNaturalFuel
    from app.fuel.models.fue_equipment_group_fuel_formula_model import EquipmentGroupFuelFormula
    from app.fuel.models.fue_equipment_group_electricity_production_cost_model import EquipmentGroupElectricityProductionCost
    from app.fuel.models.fue_equipment_group_heat_and_tariffs_model import EquipmentGroupHeatAndTariffs
    from app.fuel.models.coefficient.equipment_group_coefficient_result_model import EquipmentGroupCoefficientResult
    from app.fuel.services.equipment_groups.equipment_group_merge_services import (
        _reassign_model_rows_to_primary,
    )
    from app.fuel.services.equipment_groups.equipment_group_edit_services import (
        _apply_equipment_group_type_change_from_form,
    )

    source_sets = EquipmentGroupSet.query.filter_by(equipment_group_id=source.id).all()
    source_type_ids = {
        row.equipment_group_set_station.equipment_group_type_id
        for row in source_sets
        if row.equipment_group_set_station is not None
        and row.equipment_group_set_station.equipment_group_type_id is not None
    }
    specs = [
        (EquipmentGroupFuelParam, ["year_number"]),
        (EquipmentGroupExtraFuelParam, ["year_number"]),
        (EquipmentGroupSpecificFuelConsumption, ["year_number"]),
        (EquipmentGroupSpecificFuelCost, ["year_number"]),
        (EquipmentGroupSpecificFuelPrice, ["year_number"]),
        (EquipmentGroupNaturalFuel, ["year_number"]),
        (EquipmentGroupFuelFormula, ["year_number", "variant_number", "database_version_id"]),
        (EquipmentGroupElectricityProductionCost, ["year_number", "cost_code"]),
        (EquipmentGroupHeatAndTariffs, ["kod_goroda", "name_eto", "var_razv", "year_number", "database_version_id"]),
        (EquipmentGroupCoefficientResult, ["distribution_parameter_id", "year_number", "database_version_id"]),
    ]
    rows_by_model = {
        model: model.query.filter_by(equipment_group_id=source.id).all()
        for model, _ in specs
    }
    shell_fields = {
        "id", "equipment_group_id", "name", "year_number", "database_version_id",
        "numb1120", "numb1", "created_at", "updated_at",
    }
    has_parameters = any(
        getattr(row, attr.key) is not None
        and not (attr.key == "ved" and row.ved == 0)
        for row in rows_by_model[EquipmentGroupFuelParam]
        for attr in EquipmentGroupFuelParam.__mapper__.column_attrs
        if attr.key not in shell_fields
    )
    if not (
        has_parameters or source_type_ids
        or any(rows for model, rows in rows_by_model.items() if model != EquipmentGroupFuelParam)
        or any(getattr(source, field) is not None for field in ("tm", "n1", "n2", "p1", "p2", "note"))
    ):
        return None

    for set_row in source_sets:
        link = set_row.equipment_group_set_station
        if link is not None and link.station_id is not None:
            ensured = ensure_equipment_group_linked_to_station(
                equipment_group_id=target.id,
                station_id=link.station_id,
                version_id=version_id,
                equipment_group_type_id=link.equipment_group_type_id,
            )
            if ensured is None:
                raise ValueError("Не удалось связать целевую группу со станцией исходной группы.")

    if len(source_type_ids) == 1:
        error = _apply_equipment_group_type_change_from_form(
            target.id, next(iter(source_type_ids)), version_id
        )
        if error:
            raise ValueError(error)

    years = set(get_reference_years())
    moved_rows = 0
    for model, identity_fields in specs:
        rows = rows_by_model[model]
        moved_rows += len(rows)
        years.update(row.year_number for row in rows if row.year_number is not None)
        _reassign_model_rows_to_primary(
            model, [source.id], target.id, identity_fields, overwrite_existing=True
        )
        # NUMB1120 is also used for lookups outside the FK relationship.
        for row in model.query.filter_by(equipment_group_id=target.id).all():
            if "numb1120" in model.__mapper__.attrs:
                row.numb1120 = target.numb
            if "name" in model.__mapper__.attrs:
                row.name = target.name or target.name_ext

    for field in ("tm", "n1", "n2", "p1", "p2", "note"):
        value = getattr(source, field)
        if value is not None:
            setattr(target, field, value)
        setattr(source, field, None)
    if source.niv is not None:
        target.niv = source.niv
    if is_composite_parent_group(source):
        source.niv = None
    for year in sorted(years):
        db.session.add(EquipmentGroupFuelParam(
            equipment_group_id=source.id,
            year_number=year,
            database_version_id=version_id,
            numb1120=source.numb,
            ved=0,
        ))

    # A station/type link can be shared with the target; detach only the source.
    error = _apply_equipment_group_type_change_from_form(source.id, None, version_id)
    if error:
        raise ValueError(error)
    return moved_rows


def rebind_source_group_machines(
    *,
    source_group_id: int,
    target_group_id: int,
    version_id: int | None = None,
) -> dict:
    """Переносит агрегаты; между головой и ГО также переносит все параметры."""
    source = EquipmentGroup.query.get(int(source_group_id))
    target = EquipmentGroup.query.get(int(target_group_id))
    if source is None:
        return {"error": "Исходная группа оборудования не найдена."}
    if target is None:
        return {"error": "Целевая группа оборудования не найдена."}
    if int(source.id) == int(target.id):
        return {"error": "Выберите другую группу оборудования."}

    allowed_ids = {
        gid for gid, _label in get_rebind_target_choices_for_group(source, version_id)
    }
    if int(target.id) not in allowed_ids:
        return {
            "error": (
                "Целевая группа не входит в составной кластер этой группы "
                "и не связана с теми же электростанциями."
            )
        }

    if version_id is None:
        version_id = getattr(source, "database_version_id", None)
        if version_id is None:
            version_id = get_current_db_version_id()

    if any(group.database_version_id not in (None, version_id) for group in (source, target)):
        return {"error": "Группы оборудования должны принадлежать текущей версии БД."}

    move_parameters = is_composite_parent_group(source) or is_composite_parent_group(target)
    mfp_q = MachineFuelParam.query.filter(
        MachineFuelParam.equipment_group_id == int(source.id),
        MachineFuelParam.machine_id.isnot(None),
    )
    if version_id is None:
        mfp_q = mfp_q.filter(MachineFuelParam.database_version_id.is_(None))
    else:
        mfp_q = mfp_q.filter(MachineFuelParam.database_version_id == version_id)

    rebound = 0
    machine_ids: list[int] = []
    for mfp in mfp_q.all():
        machine = getattr(mfp, "machine", None) or Machine.query.get(mfp.machine_id)
        result = rebind_machine_to_equipment_group(
            machine=machine,
            target_group_id=int(target.id),
            version_id=version_id,
        )
        if result.get("error"):
            raise ValueError(result["error"])
        rebound += 1
        if result.get("machine_id"):
            machine_ids.append(int(result["machine_id"]))

    if rebound == 0:
        set_rows = EquipmentGroupSet.query.filter_by(
            equipment_group_id=int(source.id)
        ).all()
        linked_stations = 0
        for set_row in set_rows:
            link = getattr(set_row, "equipment_group_set_station", None)
            if not link or not link.station_id:
                continue
            ensured = ensure_equipment_group_linked_to_station(
                equipment_group_id=int(target.id),
                station_id=link.station_id,
                version_id=version_id,
                equipment_group_type_id=link.equipment_group_type_id,
            )
            if ensured is not None:
                linked_stations += 1
        if linked_stations:
            moved_rows = (
                _move_group_parameters(source, target, version_id)
                if move_parameters else None
            )
            return {
                "moved_parameter_rows": moved_rows,
                "rebound_machines": 0,
                "linked_stations": linked_stations,
                "target_id": int(target.id),
                "target_label": format_equipment_group_choice_label(target),
                "source_label": format_equipment_group_choice_label(source),
            }
        return {"error": "Нет агрегатов для переноса и нет связи исходной группы со станцией."}

    remaining = mfp_q.count()
    if remaining:
        raise ValueError("Не все агрегаты исходной группы удалось перенести.")
    moved_rows = (
        _move_group_parameters(source, target, version_id)
        if move_parameters else None
    )
    return {
        "moved_parameter_rows": moved_rows,
        "rebound_machines": rebound,
        "machine_ids": machine_ids,
        "target_id": int(target.id),
        "target_label": format_equipment_group_choice_label(target),
        "source_label": format_equipment_group_choice_label(source),
    }

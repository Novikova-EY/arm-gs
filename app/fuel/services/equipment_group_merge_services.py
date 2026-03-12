# -*- coding: utf-8 -*-
"""
Services for merging EquipmentGroup (v2) links.
"""
from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import func, or_

from app.extensions import db
from app.common.services.database_version_filter import set_db_version_on_create
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
    """Сливает поля source → target; возвращает список объединённых полей."""
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


def _reassign_sets_to_primary(group_ids: list[int], primary_id: int) -> None:
    if not group_ids:
        return
    sets = EquipmentGroupSet.query.filter(
        EquipmentGroupSet.equipment_group_id.in_(group_ids)
    ).all()
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


def _remove_orphan_groups(groups: Iterable[EquipmentGroup], primary_id: int) -> int:
    removed = 0
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
    на станции — объединяем (EquipmentGroupSetStation → одна EquipmentGroup,
    параметры сливаем, дубликат удаляем). Иначе — просто обновляем name.

    Returns:
        dict с полями:
        - merged: bool
        - primary_id: int|None — id оставшейся группы
        - old_name: str — старое имя переименовываемой группы
        - new_name: str
        - deleted_group_id: int|None — id удалённой группы (при merge)
        - merged_fields: list[str] — список объединённых полей (при merge)
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

    # Ищем другую EquipmentGroup с таким же именем (без учёта регистра и пробелов) — по всей БД,
    # чтобы объединять дубликаты даже если они привязаны к разным станциям
    new_name_norm = new_name.strip().lower()
    name_expr = func.lower(func.trim(func.coalesce(EquipmentGroup.name, "")))
    existing_same_name = (
        db.session.query(EquipmentGroup)
        .filter(
            name_expr == new_name_norm,
            EquipmentGroup.id != equipment_group_id,
        )
    )
    # Учитываем версию: точное совпадение или legacy (database_version_id is None)
    if current_version_id is None:
        existing_same_name = existing_same_name.filter(
            EquipmentGroup.database_version_id.is_(None)
        )
    else:
        existing_same_name = existing_same_name.filter(
            or_(
                EquipmentGroup.database_version_id == current_version_id,
                EquipmentGroup.database_version_id.is_(None),
            )
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


def rename_or_merge_equipment_group_all_versions(
    *,
    station_external_code: str,
    equipment_group_id: int,
    equipment_group_type_id: int,
    new_name: str,
) -> dict:
    """
    Переименование группы оборудования во ВСЕХ версиях БД.

    Логика:
    - Берём external_code станции и id типа группы оборудования (в текущей версии)
    - equipment_group_type_id версионируем: в каждой версии у одного логического типа
      может быть свой ID. Ищем EquipmentGroupType по ref_uuid (или по имени) в каждой версии.
    - Для каждой версии: находим Station.id по external_code (Station в этой версии)
    - По связи gs_fue_equipment_group_type_stations (EquipmentGroupSetStation) с station_id,
      equipment_group_type_id (для этой версии) и database_version_id находим EquipmentGroup
    - Меняем наименование EquipmentGroup
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

        # EquipmentGroup через связь EquipmentGroupSet -> equipment_group_set_station_id
        eg_version_filter = (
            EquipmentGroup.database_version_id.is_(None)
            if version_id is None
            else or_(
                EquipmentGroup.database_version_id == version_id,
                EquipmentGroup.database_version_id.is_(None),
            )
        )
        all_station_groups = (
            db.session.query(EquipmentGroup)
            .join(EquipmentGroupSet, EquipmentGroupSet.equipment_group_id == EquipmentGroup.id)
            .filter(
                EquipmentGroupSet.equipment_group_set_station_id.in_(link_ids),
                eg_version_filter,
            )
            .distinct()
            .all()
        )
        if not all_station_groups:
            continue

        # Дополнительно ищем ВСЕ группы с таким же именем в версии (как в single-version),
        # чтобы объединять дубликаты даже при совпадении наименования с БД
        name_expr = func.lower(func.trim(func.coalesce(EquipmentGroup.name, "")))
        same_name_in_version = (
            db.session.query(EquipmentGroup)
            .filter(name_expr == new_name_norm, eg_version_filter)
            .all()
        )
        # Объединяем: все группы по станции+типу + все с таким же именем (дедупликация по id)
        seen_ids: set[int] = set()
        groups_with_new: list[EquipmentGroup] = []
        for g in all_station_groups + same_name_in_version:
            if g and g.id not in seen_ids:
                seen_ids.add(g.id)
                groups_with_new.append(g)

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
        if not primary:
            versions_touched += 1
            continue

        primary.name = new_name
        candidate_ids = [g.id for g in groups_with_new if g.id != primary.id]
        for g in groups_with_new:
            if g.id != primary.id:
                _merge_group_fields_return_list(primary, g)
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


def update_equipment_group_all_versions(
    *,
    equipment_group_id: int,
    form_data: dict,
) -> dict:
    """
    Применяет данные формы редактирования группы оборудования ко всем эквивалентным
    группам во всех версиях БД.

    form_data — словарь полей (name, niv, comp, main, d, r, forem, vedomstvo, obl, dep,
    oes, er, fo, numb, tm, n1, n2, p1, p2, ordnumb, addr, note, codegor, be, gk, gkf,
    regional_district_id, regional_energy_system_id).

    Возвращает dict с versions_touched, updated_count, fallback_single (опционально).
    """
    from app.common.models.database_version_model import DatabaseVersion
    from app.common.services.database_version_filter import filter_by_explicit_db_version

    from app.generation.models.station.station_model import Station
    from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
        EquipmentGroupType,
    )

    str_fields = [
        "name", "niv", "comp", "main", "d", "r", "forem", "vedomstvo",
        "obl", "dep", "oes", "er", "fo", "numb", "tm", "n1", "n2", "p1", "p2",
        "ordnumb", "addr", "note", "codegor", "be", "gk", "gkf",
    ]
    int_fk_fields = ["regional_district_id", "regional_energy_system_id"]

    values = {}
    for field in str_fields:
        val = form_data.get(field)
        if val is not None:
            values[field] = (val.strip() if val else None)
    for field in int_fk_fields:
        val = form_data.get(field)
        if val is not None:
            parsed = _parse_int_form_val(val)
            values[field] = parsed

    if not values:
        return {"versions_touched": 0, "updated_count": 0}

    pairs = _get_station_type_pairs_for_equipment_group(equipment_group_id)
    if not pairs:
        # Fallback: для групп без связей станция+external_code (напр. котельная)
        # По EquipmentGroup.regional_district_id -> RegionalDistrict.id берём ref_uuid.
        # По ref_uuid для каждой версии находим RegionalDistrict.id и вставляем в EquipmentGroup.
        # Аналогично для RegionalEnergySystem.
        if "regional_district_id" in form_data or "regional_energy_system_id" in form_data:
            from app.common.models.database_version_model import DatabaseVersion
            from app.common.services.database_version_filter import filter_by_explicit_db_version
            from app.refdata.models.territories.regional_district_model import RegionalDistrict
            from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem

            group = EquipmentGroup.query.filter_by(id=equipment_group_id).first()
            if not group:
                return {"versions_touched": 0, "updated_count": 0}

            new_rd_id = _parse_int_form_val(form_data.get("regional_district_id"))
            new_res_id = _parse_int_form_val(form_data.get("regional_energy_system_id"))

            # ref_uuid из RegionalDistrict.id и RegionalEnergySystem.id (значения из формы)
            rd_ref_uuid = None
            res_ref_uuid = None
            if new_rd_id:
                rd = RegionalDistrict.query.get(new_rd_id)
                if rd:
                    rd_ref_uuid = getattr(rd, "ref_uuid", None)
            if new_res_id:
                res = RegionalEnergySystem.query.get(new_res_id)
                if res:
                    res_ref_uuid = getattr(res, "ref_uuid", None)

            if not rd_ref_uuid and not res_ref_uuid:
                if "regional_district_id" in form_data:
                    group.regional_district_id = new_rd_id
                if "regional_energy_system_id" in form_data:
                    group.regional_energy_system_id = new_res_id
                return {
                    "versions_touched": 0,
                    "updated_count": 1,
                    "fallback_single": True,
                }

            def _resolve_rd_id_for_version(vid: Optional[int]) -> Optional[int]:
                if not rd_ref_uuid:
                    return None
                q = RegionalDistrict.query.filter(RegionalDistrict.ref_uuid == rd_ref_uuid)
                q = filter_by_explicit_db_version(q, RegionalDistrict, vid)
                r = q.first()
                return r.id if r else None

            def _resolve_res_id_for_version(vid: Optional[int]) -> Optional[int]:
                if not res_ref_uuid:
                    return None
                q = RegionalEnergySystem.query.filter(RegionalEnergySystem.ref_uuid == res_ref_uuid)
                q = filter_by_explicit_db_version(q, RegionalEnergySystem, vid)
                r = q.first()
                return r.id if r else None

            # ref_uuid текущей группы для поиска эквивалентов
            rd_ref_uuid_match = None
            res_ref_uuid_match = None
            if group.regional_district_id:
                rd_cur = RegionalDistrict.query.get(group.regional_district_id)
                if rd_cur:
                    rd_ref_uuid_match = getattr(rd_cur, "ref_uuid", None)
            if group.regional_energy_system_id:
                res_cur = RegionalEnergySystem.query.get(group.regional_energy_system_id)
                if res_cur:
                    res_ref_uuid_match = getattr(res_cur, "ref_uuid", None)
            if not rd_ref_uuid_match and not res_ref_uuid_match:
                rd_ref_uuid_match = rd_ref_uuid
                res_ref_uuid_match = res_ref_uuid

            def _resolve_rd_id_match_for_version(vid: Optional[int]) -> Optional[int]:
                if not rd_ref_uuid_match:
                    return None
                q = RegionalDistrict.query.filter(RegionalDistrict.ref_uuid == rd_ref_uuid_match)
                q = filter_by_explicit_db_version(q, RegionalDistrict, vid)
                r = q.first()
                return r.id if r else None

            def _resolve_res_id_match_for_version(vid: Optional[int]) -> Optional[int]:
                if not res_ref_uuid_match:
                    return None
                q = RegionalEnergySystem.query.filter(RegionalEnergySystem.ref_uuid == res_ref_uuid_match)
                q = filter_by_explicit_db_version(q, RegionalEnergySystem, vid)
                r = q.first()
                return r.id if r else None

            version_ids: list[Optional[int]] = [None]
            for dv in DatabaseVersion.query.filter(DatabaseVersion.id.isnot(None)).all():
                if dv.id:
                    version_ids.append(dv.id)

            versions_touched_set: set[Optional[int]] = set()
            updated_count = 0
            group_name = (group.name or "").strip()

            for version_id in version_ids:
                rd_id_match = _resolve_rd_id_match_for_version(version_id)
                res_id_match = _resolve_res_id_match_for_version(version_id)
                rd_id_for_version = _resolve_rd_id_for_version(version_id)
                res_id_for_version = _resolve_res_id_for_version(version_id)
                if rd_id_match is None and res_id_match is None:
                    continue

                eg_version_filter = (
                    EquipmentGroup.database_version_id.is_(None)
                    if version_id is None
                    else or_(
                        EquipmentGroup.database_version_id == version_id,
                        EquipmentGroup.database_version_id.is_(None),
                    )
                )
                q = db.session.query(EquipmentGroup).filter(eg_version_filter)
                if rd_id_match is not None:
                    q = q.filter(EquipmentGroup.regional_district_id == rd_id_match)
                if res_id_match is not None:
                    q = q.filter(EquipmentGroup.regional_energy_system_id == res_id_match)
                if group_name:
                    name_expr = func.lower(func.trim(func.coalesce(EquipmentGroup.name, "")))
                    q = q.filter(name_expr == group_name.lower())
                groups_in_version = q.all()

                if not groups_in_version and (rd_id_for_version is not None or res_id_for_version is not None):
                    # Группы в этой версии нет — создаём по данным формы
                    new_eg = EquipmentGroup(name=group_name or group.name)
                    if version_id is not None:
                        new_eg.database_version_id = version_id
                    for field, val in values.items():
                        if field == "regional_district_id":
                            setattr(new_eg, field, rd_id_for_version)
                        elif field == "regional_energy_system_id":
                            setattr(new_eg, field, res_id_for_version)
                        elif hasattr(new_eg, field):
                            setattr(new_eg, field, val)
                    db.session.add(new_eg)
                    db.session.flush()
                    groups_in_version = [new_eg]
                elif not groups_in_version:
                    continue

                for g in groups_in_version:
                    for field, val in values.items():
                        if field == "regional_district_id" and "regional_district_id" in form_data:
                            setattr(g, field, rd_id_for_version)
                        elif field == "regional_energy_system_id" and "regional_energy_system_id" in form_data:
                            setattr(g, field, res_id_for_version)
                        elif hasattr(g, field):
                            setattr(g, field, val)
                    updated_count += 1
                versions_touched_set.add(version_id)

            if versions_touched_set:
                return {
                    "versions_touched": len(versions_touched_set),
                    "updated_count": updated_count,
                }
            if "regional_district_id" in form_data:
                group.regional_district_id = new_rd_id
            if "regional_energy_system_id" in form_data:
                group.regional_energy_system_id = new_res_id
            return {
                "versions_touched": 0,
                "updated_count": 1,
                "fallback_single": True,
            }
        return {"versions_touched": 0, "updated_count": 0}

    # Все версии
    version_ids: list[Optional[int]] = [None]
    for dv in DatabaseVersion.query.filter(DatabaseVersion.id.isnot(None)).all():
        if dv.id:
            version_ids.append(dv.id)

    def _resolve_type_id_for_version(
        equipment_group_type_id: int, vid: Optional[int]
    ) -> Optional[int]:
        current_type = EquipmentGroupType.query.get(equipment_group_type_id)
        type_ref_uuid = getattr(current_type, "ref_uuid", None) if current_type else None
        type_name = (current_type.name or "").strip() if current_type else ""
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

    def _apply_values_to_group(group: EquipmentGroup) -> int:
        n = 0
        for field, val in values.items():
            if hasattr(group, field):
                setattr(group, field, val)
                n += 1
        return n

    versions_touched_set: set[Optional[int]] = set()
    updated_count = 0
    updated_ids: set[int] = set()

    for station_external_code, equipment_group_type_id in pairs:
        for version_id in version_ids:
            type_id_in_version = _resolve_type_id_for_version(
                equipment_group_type_id, version_id
            )
            if type_id_in_version is None:
                continue

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

            eg_version_filter = (
                EquipmentGroup.database_version_id.is_(None)
                if version_id is None
                else or_(
                    EquipmentGroup.database_version_id == version_id,
                    EquipmentGroup.database_version_id.is_(None),
                )
            )
            all_station_groups = (
                db.session.query(EquipmentGroup)
                .join(
                    EquipmentGroupSet,
                    EquipmentGroupSet.equipment_group_id == EquipmentGroup.id,
                )
                .filter(
                    EquipmentGroupSet.equipment_group_set_station_id.in_(link_ids),
                    eg_version_filter,
                )
                .distinct()
                .all()
            )
            if not all_station_groups:
                continue

            # Дополнительно ищем ВСЕ группы с таким же именем (как на station_details),
            # чтобы объединять дубликаты даже при совпадении наименования с БД
            new_name = (values.get("name") or "").strip()
            groups_to_update = list(all_station_groups)
            if new_name:
                new_name_norm = new_name.lower()
                name_expr = func.lower(func.trim(func.coalesce(EquipmentGroup.name, "")))
                same_name_in_version = (
                    db.session.query(EquipmentGroup)
                    .filter(name_expr == new_name_norm, eg_version_filter)
                    .all()
                )
                seen_ids: set[int] = set()
                groups_to_update = []
                for g in all_station_groups + same_name_in_version:
                    if g and g.id not in seen_ids:
                        seen_ids.add(g.id)
                        groups_to_update.append(g)

            # Объединяем дубликаты, если их больше одной
            if len(groups_to_update) > 1:
                primary = _choose_primary_group(groups_to_update)
                if primary:
                    candidate_ids = [g.id for g in groups_to_update if g.id != primary.id]
                    for g in groups_to_update:
                        if g.id != primary.id:
                            _merge_group_fields_return_list(primary, g)
                    _reassign_sets_to_primary(candidate_ids, primary.id)
                    _remove_orphan_groups(groups_to_update, primary.id)
                    groups_to_update = [primary]

            for g in groups_to_update:
                if g.id not in updated_ids:
                    updated_ids.add(g.id)
                    _apply_values_to_group(g)
                    updated_count += 1
            versions_touched_set.add(version_id)

    return {
        "versions_touched": len(versions_touched_set),
        "updated_count": updated_count,
    }

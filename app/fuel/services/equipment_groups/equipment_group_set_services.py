# -*- coding: utf-8 -*-
"""
Сервис для обеспечения наличия EquipmentGroupSetStation и EquipmentGroupSet
при выборе типа группы оборудования на агрегате.
Логика аналогична загрузке из Excel (stations_equipment_groups).
"""

from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.common.services.tranzaction_services import quick_fix_seq
from app.common.services.database_version_filter import get_current_db_version_id
from app.generation.models.station.station_model import Station
from app.generation.models.machine.machine_model import Machine
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
    EquipmentGroupType,
)
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
from config import SCHEMA_FUEL


NEW_EQUIPMENT_GROUP_SUFFIX = " (нов)"
EQUIPMENT_GROUP_CONTEXT_COPY_FIELDS = (
    "name_ext",
    "niv",
    "comp",
    "main",
    "d",
    "r",
    "forem",
    "vedomstvo",
    "obl",
    "regional_district_id",
    "regional_energy_system_id",
    "dep",
    "id_department",
    "oes",
    "er",
    "fo",
    "numb",
    "tm",
    "n1",
    "n2",
    "p1",
    "p2",
    "ordnumb",
    "addr",
    "note",
    "codegor",
    "be",
    "gk",
    "gkf",
)


def _quick_fix_equipment_group_seqs() -> None:
    for table in (
        "gs_fue_equipment_groups",
        "gs_fue_equipment_group_sets",
        "gs_fue_equipment_group_type_stations",
    ):
        try:
            quick_fix_seq(SCHEMA_FUEL, table, "id")
        except Exception:
            pass


def _find_equipment_group_set_link(
    equipment_group_id: int,
    equipment_group_set_station_id: int,
) -> EquipmentGroupSet | None:
    return (
        EquipmentGroupSet.query
        .filter_by(
            equipment_group_id=equipment_group_id,
            equipment_group_set_station_id=equipment_group_set_station_id,
        )
        .first()
    )


def _create_equipment_group_set_with_retry(
    equipment_group_id: int,
    equipment_group_set_station_id: int,
) -> EquipmentGroupSet:
    """
    Возвращает существующую или создаёт новую связку EquipmentGroupSet.
    При рассинхронизации sequence (UniqueViolation по PK) повторяет insert
    после выравнивания sequence; при дубликате бизнес-ключа возвращает запись.
    """
    existing = _find_equipment_group_set_link(
        equipment_group_id,
        equipment_group_set_station_id,
    )
    if existing:
        return existing

    last_exc: Exception | None = None
    for _attempt in range(3):
        _quick_fix_equipment_group_seqs()
        existing = _find_equipment_group_set_link(
            equipment_group_id,
            equipment_group_set_station_id,
        )
        if existing:
            return existing

        set_v2 = EquipmentGroupSet(
            equipment_group_id=equipment_group_id,
            equipment_group_set_station_id=equipment_group_set_station_id,
        )
        try:
            with db.session.begin_nested():
                db.session.add(set_v2)
                db.session.flush()
            return set_v2
        except IntegrityError as exc:
            last_exc = exc
            existing = _find_equipment_group_set_link(
                equipment_group_id,
                equipment_group_set_station_id,
            )
            if existing:
                return existing

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Не удалось создать EquipmentGroupSet")


def _generate_stable_external_code_equipment_group(
    station_external_code: str | None,
    type_ref_uuid: str | None,
    numb: int | str | None,
    group_variant: str | None = None,
) -> str:
    key = (
        f"import|equipment_group|station|{station_external_code or ''}"
        f"|type|{type_ref_uuid or ''}|numb|{numb or ''}"
        f"|variant|{group_variant or 'base'}"
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def _find_equipment_group_by_external_code(
    external_code: str | None,
    version_id: int | None,
) -> EquipmentGroup | None:
    if not external_code:
        return None

    query = EquipmentGroup.query.filter(EquipmentGroup.external_code == external_code)
    if version_id is None:
        query = query.filter(EquipmentGroup.database_version_id.is_(None))
    else:
        query = query.filter(EquipmentGroup.database_version_id == version_id)
    return query.order_by(EquipmentGroup.id.asc()).first()


def _year_has_plan_feature(year_number: int | None, version_id: int | None) -> bool:
    if year_number is None:
        return False
    from app.common.services.get_services.years.year_feature_services import (
        get_year_feature_dict_for_version,
    )

    year_features = get_year_feature_dict_for_version(version_id)
    return str(year_features.get(year_number) or "").strip().lower() == "план"


def _machine_requires_new_equipment_group(machine: Machine | None, version_id: int | None) -> bool:
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


def compose_equipment_group_name(
    station: Station | None,
    group_type: EquipmentGroupType | None,
    *,
    is_new_group: bool = False,
) -> str | None:
    """«Станция (тип группы)» — для групп с ровно одной привязанной станцией."""
    if not station or not station.name or not group_type or not group_type.name:
        return None
    base_name = f"{station.name} ({group_type.name})"
    return f"{base_name}{NEW_EQUIPMENT_GROUP_SUFFIX}" if is_new_group else base_name


def _compose_equipment_group_name(
    station: Station | None,
    group_type: EquipmentGroupType | None,
    *,
    is_new_group: bool,
) -> str | None:
    return compose_equipment_group_name(
        station, group_type, is_new_group=is_new_group
    )


def _is_new_equipment_group_name(name: str | None) -> bool:
    return bool(name and str(name).strip().endswith(NEW_EQUIPMENT_GROUP_SUFFIX))


def get_single_station_and_type_for_equipment_group(
    equipment_group_id: int,
) -> tuple[Station | None, EquipmentGroupType | None]:
    """
    Если у группы ровно одна уникальная станция в связях EquipmentGroupSet
    и единый тип группы — возвращает (station, type), иначе (None, None) для типа
    при неоднозначности (станцию всё же вернёт только при одной станции и одном типе).
    """
    if not equipment_group_id:
        return None, None
    set_rows = (
        EquipmentGroupSet.query.filter_by(equipment_group_id=equipment_group_id)
        .order_by(EquipmentGroupSet.id.asc())
        .all()
    )
    stations_by_id: dict[int, Station] = {}
    type_ids: set[int | None] = set()
    type_by_id: dict[int, EquipmentGroupType] = {}
    for set_row in set_rows:
        link = getattr(set_row, "equipment_group_set_station", None)
        if link is None:
            link = EquipmentGroupSetStation.query.get(
                set_row.equipment_group_set_station_id
            )
        if not link:
            continue
        sid = getattr(link, "station_id", None)
        if sid is None:
            continue
        station = getattr(link, "station", None)
        if station is None:
            station = Station.query.get(sid)
        if station is not None:
            stations_by_id[int(sid)] = station
        tid = getattr(link, "equipment_group_type_id", None)
        type_ids.add(tid)
        if tid is not None:
            eg_type = getattr(link, "equipment_group_type", None)
            if eg_type is None:
                eg_type = EquipmentGroupType.query.get(tid)
            if eg_type is not None:
                type_by_id[int(tid)] = eg_type
    if len(stations_by_id) != 1:
        return None, None
    station = next(iter(stations_by_id.values()))
    # Нужен ровно один тип во всех связях (не «—» и не смесь типов)
    if len(type_ids) != 1:
        return None, None
    only_type_id = next(iter(type_ids))
    if only_type_id is None:
        return None, None
    group_type = type_by_id.get(int(only_type_id))
    if group_type is None:
        return None, None
    return station, group_type


def suggested_equipment_group_name(
    equipment_group_id: int,
    *,
    current_name: str | None = None,
) -> str | None:
    """
    Предлагаемое название при ровно одной станции и одном типе.
    Сохраняет суффикс « (нов)», если он уже был в current_name.
    """
    station, group_type = get_single_station_and_type_for_equipment_group(
        equipment_group_id
    )
    if not station or not group_type:
        return None
    return compose_equipment_group_name(
        station,
        group_type,
        is_new_group=_is_new_equipment_group_name(current_name),
    )


def resolve_auto_equipment_group_name(
    *,
    suggested: str | None,
    old_name: str | None,
    submitted_name: str | None = None,
    old_suggested: str | None = None,
    force: bool = False,
) -> str | None:
    """
    Решает, нужно ли выставить suggested как name.

    force — всегда (массовое обновление).
    Иначе: пустое имя; или пользователь не менял поле, а старое было
    автосгенерированным / пустым / уже совпадает с новым suggested.
    Ручное имя сохраняется.
    """
    if not suggested:
        return None
    suggested = suggested.strip()
    if not suggested:
        return None
    if force:
        return suggested
    old = (old_name or "").strip()
    submitted = (
        old if submitted_name is None else (submitted_name or "").strip()
    )
    old_sug = (old_suggested or "").strip()
    if not submitted:
        return suggested
    if submitted != old:
        # Пользователь явно задал другое название в этой форме
        return None
    if not old or old == old_sug or old == suggested:
        return suggested
    return None


def apply_auto_equipment_group_name(
    group: EquipmentGroup,
    *,
    force: bool = False,
    old_name: str | None = None,
    submitted_name: str | None = None,
    old_suggested: str | None = None,
) -> str | None:
    """
    При необходимости пишет group.name. Возвращает новое имя или None,
    если менять не нужно.
    """
    if group is None or getattr(group, "id", None) is None:
        return None
    baseline = old_name if old_name is not None else getattr(group, "name", None)
    suggested = suggested_equipment_group_name(
        int(group.id),
        current_name=baseline if submitted_name is None else submitted_name or baseline,
    )
    new_name = resolve_auto_equipment_group_name(
        suggested=suggested,
        old_name=baseline,
        submitted_name=submitted_name,
        old_suggested=old_suggested,
        force=force,
    )
    if not new_name:
        return None
    current = (getattr(group, "name", None) or "").strip()
    if current == new_name:
        return None
    group.name = new_name
    return new_name


def _get_linked_equipment_groups(link_id: int, version_id: int | None = None) -> list[EquipmentGroup]:
    rows = (
        EquipmentGroupSet.query
        .join(EquipmentGroup, EquipmentGroup.id == EquipmentGroupSet.equipment_group_id)
        .filter(EquipmentGroupSet.equipment_group_set_station_id == link_id)
        .order_by(EquipmentGroup.id.asc())
        .all()
    )
    groups = [
        row.equipment_group for row in rows if getattr(row, "equipment_group", None) is not None
    ]
    if version_id is None:
        matching = [
            group
            for group in groups
            if getattr(group, "database_version_id", None) is None
        ]
    else:
        matching = [
            group
            for group in groups
            if getattr(group, "database_version_id", None) == version_id
        ]
    return matching if matching else groups


def resolve_station_id_for_version(
    station_id: int | None,
    version_id: int | None,
) -> int | None:
    """ID электростанции с тем же external_code в указанной версии БД."""
    if station_id is None:
        return None
    from app.common.services.version_entity_resolve_services import (
        resolve_entity_id_by_external_code_for_version,
    )

    return resolve_entity_id_by_external_code_for_version(Station, int(station_id), version_id)


def resolve_station_and_type_for_version(
    station_id: int | None,
    equipment_group_type_id: int | None,
    version_id: int | None,
) -> tuple[int | None, int | None]:
    """
    Приводит station_id и тип группы к version_id.

    Если станция задана, но копии в этой версии нет — (None, None), чтобы не писать
    смешанную связь (станция одной версии, database_version_id другой).
    """
    from app.common.services.version_entity_resolve_services import (
        resolve_equipment_group_type_id_for_version,
    )

    resolved_station_id = station_id
    if station_id is not None:
        resolved_station_id = resolve_station_id_for_version(int(station_id), version_id)
        if resolved_station_id is None:
            return None, None

    resolved_type_id = equipment_group_type_id
    if equipment_group_type_id is not None:
        resolved_type_id = resolve_equipment_group_type_id_for_version(
            int(equipment_group_type_id), version_id
        )
    return resolved_station_id, resolved_type_id


def _count_sets_on_link(set_station_id: int) -> int:
    return (
        EquipmentGroupSet.query.filter_by(
            equipment_group_set_station_id=set_station_id
        ).count()
        or 0
    )


def _point_group_set_at_link(
    set_row: EquipmentGroupSet,
    new_link: EquipmentGroupSetStation,
) -> None:
    """Переносит EquipmentGroupSet на каноническую связь; пустой старый SetStation удаляет."""
    if set_row is None or new_link is None:
        return
    if set_row.equipment_group_set_station_id == new_link.id:
        return
    old_link_id = set_row.equipment_group_set_station_id
    dup = (
        EquipmentGroupSet.query.filter_by(
            equipment_group_id=set_row.equipment_group_id,
            equipment_group_set_station_id=new_link.id,
        ).first()
    )
    if dup is not None and dup.id != set_row.id:
        db.session.delete(set_row)
    else:
        set_row.equipment_group_set_station_id = new_link.id
        db.session.add(set_row)
    db.session.flush()
    if old_link_id and _count_sets_on_link(old_link_id) == 0:
        old_link = db.session.get(EquipmentGroupSetStation, old_link_id)
        if old_link is not None:
            db.session.delete(old_link)
            db.session.flush()


def find_or_create_versioned_equipment_group_set_station(
    station_id: int | None,
    equipment_group_type_id: int | None,
    version_id: int | None,
) -> EquipmentGroupSetStation | None:
    """
    Находит или создаёт EquipmentGroupSetStation с FK уже в version_id.
    Не проставляет «текущую» версию поверх явного None (legacy).
    equipment_group_type_id=None — связь без типа (прочерк / составная станция).
    """
    link_query = EquipmentGroupSetStation.query
    if equipment_group_type_id is None:
        link_query = link_query.filter(
            EquipmentGroupSetStation.equipment_group_type_id.is_(None)
        )
    else:
        link_query = link_query.filter(
            EquipmentGroupSetStation.equipment_group_type_id == equipment_group_type_id
        )
    if station_id is None:
        link_query = link_query.filter(EquipmentGroupSetStation.station_id.is_(None))
    else:
        link_query = link_query.filter(EquipmentGroupSetStation.station_id == station_id)
    if version_id is None:
        link_query = link_query.filter(EquipmentGroupSetStation.database_version_id.is_(None))
    else:
        link_query = link_query.filter(EquipmentGroupSetStation.database_version_id == version_id)
    link = link_query.first()
    if link:
        return link

    _quick_fix_equipment_group_seqs()
    link = EquipmentGroupSetStation(
        station_id=station_id,
        equipment_group_type_id=equipment_group_type_id,
        database_version_id=version_id,
    )
    try:
        with db.session.begin_nested():
            db.session.add(link)
            db.session.flush()
        return link
    except IntegrityError:
        existing = link_query.first()
        if existing:
            return existing
        raise


def retarget_mismatched_version_links_for_group(
    equipment_group_id: int,
    canonical_link: EquipmentGroupSetStation,
    version_id: int | None,
) -> None:
    """
    Если у группы в этой версии БД связь указывает на клон станции/типа другой версии,
    переносит EquipmentGroupSet на каноническую связь version_id.
    """
    if not equipment_group_id or canonical_link is None:
        return

    set_rows = EquipmentGroupSet.query.filter_by(
        equipment_group_id=equipment_group_id
    ).all()
    for set_row in set_rows:
        link = getattr(set_row, "equipment_group_set_station", None)
        if link is None or link.id == canonical_link.id:
            continue
        if getattr(link, "database_version_id", None) != version_id:
            continue
        station = getattr(link, "station", None)
        group_type = getattr(link, "equipment_group_type", None)
        station_vid = getattr(station, "database_version_id", None) if station else None
        type_vid = getattr(group_type, "database_version_id", None) if group_type else None
        mixed = (
            (station is not None and station_vid != version_id)
            or (group_type is not None and type_vid != version_id)
        )
        if not mixed:
            continue
        resolved_station_id = (
            resolve_station_id_for_version(link.station_id, version_id)
            if link.station_id
            else None
        )
        same_station = (
            resolved_station_id is not None
            and resolved_station_id == canonical_link.station_id
        )
        # Только та же станция: same_type схлопывал бы ТЭС-2 и ТЭС-3
        # с одним типом группы в одну связь.
        if same_station:
            _point_group_set_at_link(set_row, canonical_link)


def _sync_equipment_group_context_from_source(
    target: EquipmentGroup,
    source: EquipmentGroup | None,
    station: Station | None,
) -> bool:
    """
    Новая variant-группа, созданная из карточки агрегата, должна наследовать
    территориальные и идентификационные поля от базовой группы, иначе она
    не проходит фильтры страницы fuel/stations_equipment_groups.
    """
    changed = False

    if source is not None:
        for field_name in EQUIPMENT_GROUP_CONTEXT_COPY_FIELDS:
            source_value = getattr(source, field_name, None)
            if getattr(target, field_name, None) != source_value:
                setattr(target, field_name, source_value)
                changed = True

    if station is not None:
        from app.common.services.refdata_fk_resolve import (
            coerce_regional_district_id_for_db_version,
            coerce_regional_energy_system_id_for_db_version,
        )

        target_vid = getattr(target, "database_version_id", None)
        station_rd = coerce_regional_district_id_for_db_version(
            getattr(station, "id_regional_district", None),
            target_vid,
        )
        station_res = coerce_regional_energy_system_id_for_db_version(
            getattr(station, "id_regional_energy_system", None),
            target_vid,
        )
        if station_rd is not None and getattr(target, "regional_district_id", None) != station_rd:
            target.regional_district_id = station_rd
            changed = True
        if station_res is not None and getattr(target, "regional_energy_system_id", None) != station_res:
            target.regional_energy_system_id = station_res
            changed = True

    old_rd = getattr(target, "regional_district_id", None)
    old_res = getattr(target, "regional_energy_system_id", None)
    target._populate_regional_ids()
    if (
        getattr(target, "regional_district_id", None),
        getattr(target, "regional_energy_system_id", None),
    ) != (old_rd, old_res):
        changed = True

    if changed:
        db.session.add(target)
    return changed


def ensure_equipment_group_set_for_station(
    station_id: int,
    equipment_group_type_id: int,
    version_id: int | None = None,
) -> EquipmentGroupSet | None:
    """
    Проверяет наличие EquipmentGroupSetStation для (station_id, equipment_group_type_id).
    Если нет — создает EquipmentGroupSetStation, затем EquipmentGroup и EquipmentGroupSet.
    Логика аналогична import_fuel_db_equipment_groups (шаг 4.1).

    Args:
        station_id: ID электростанции
        equipment_group_type_id: ID типа группы оборудования (EquipmentGroupType)
        version_id: ID версии БД (если None — использует текущую)

    Returns:
        EquipmentGroupSet или None при ошибке
    """
    return ensure_equipment_group_set_variant_for_station(
        station_id=station_id,
        equipment_group_type_id=equipment_group_type_id,
        version_id=version_id,
        is_new_group=False,
    )


def ensure_equipment_group_set_variant_for_station(
    station_id: int,
    equipment_group_type_id: int,
    version_id: int | None = None,
    *,
    is_new_group: bool = False,
) -> EquipmentGroupSet | None:
    """
    Обеспечивает наличие связки EquipmentGroupSetStation и конкретной fuel-группы
    для варианта обычного или «(нов)» оборудования.
    """
    if version_id is None:
        version_id = get_current_db_version_id()

    resolved_station_id, resolved_type_id = resolve_station_and_type_for_version(
        station_id, equipment_group_type_id, version_id
    )
    if station_id is not None and resolved_station_id is None:
        return None
    if equipment_group_type_id is not None and resolved_type_id is None:
        return None
    station_id = resolved_station_id if resolved_station_id is not None else station_id
    equipment_group_type_id = (
        resolved_type_id if resolved_type_id is not None else equipment_group_type_id
    )

    station = db.session.get(Station, station_id) if station_id else None
    if station_id and not station:
        return None
    group_type = db.session.get(EquipmentGroupType, equipment_group_type_id)
    if not group_type:
        return None

    link = find_or_create_versioned_equipment_group_set_station(
        station_id, equipment_group_type_id, version_id
    )
    if not link:
        return None

    station_ext_code = (getattr(station, "external_code", None) or "").strip() if station else ""
    type_key = getattr(group_type, "ref_uuid", None) or group_type.name or str(equipment_group_type_id)
    target_external_code = _generate_stable_external_code_equipment_group(
        station_ext_code,
        type_key,
        None,
        group_variant="new" if is_new_group else None,
    )
    linked_equipment_groups = _get_linked_equipment_groups(link.id, version_id)
    base_group_on_link = next(
        (group for group in linked_equipment_groups if not _is_new_equipment_group_name(getattr(group, "name", None))),
        None,
    )
    from app.fuel.services.equipment_groups.equipment_group_rebind_services import (
        linked_station_ids_for_equipment_group,
        station_is_primary_owner_of_equipment_group,
    )

    variant_groups = [
        group
        for group in linked_equipment_groups
        if _is_new_equipment_group_name(getattr(group, "name", None)) == is_new_group
    ]
    # Общая группа двух станций — валидная цель автопривязки.
    # Если на связи уже есть и «своя», и общая — берём «свою».
    owned_target_on_link = next(
        (
            group
            for group in variant_groups
            if station_is_primary_owner_of_equipment_group(
                station_id, group.id, version_id
            )
        ),
        None,
    )
    target_group_on_link = owned_target_on_link or (
        variant_groups[0] if variant_groups else None
    )

    if target_group_on_link is not None:
        _sync_equipment_group_context_from_source(
            target_group_on_link,
            base_group_on_link if base_group_on_link and base_group_on_link.id != target_group_on_link.id else None,
            station,
        )
        set_v2 = (
            EquipmentGroupSet.query
            .filter_by(
                equipment_group_id=target_group_on_link.id,
                equipment_group_set_station_id=link.id,
            )
            .first()
        )
        if set_v2:
            return set_v2

    equipment_group = _find_equipment_group_by_external_code(
        target_external_code,
        version_id,
    )
    if equipment_group is not None:
        already_linked = linked_station_ids_for_equipment_group(
            equipment_group.id, version_id
        )
        if already_linked and int(station_id) not in already_linked:
            equipment_group = None
            target_external_code = _generate_stable_external_code_equipment_group(
                station_ext_code,
                type_key,
                None,
                group_variant="new-owned" if is_new_group else "owned",
            )
            equipment_group = _find_equipment_group_by_external_code(
                target_external_code,
                version_id,
            )

    if equipment_group is None:
        _quick_fix_equipment_group_seqs()
        equipment_group = EquipmentGroup(
            name=_compose_equipment_group_name(
                station,
                group_type,
                is_new_group=is_new_group,
            )
        )
        equipment_group.external_code = target_external_code
        equipment_group.database_version_id = version_id
        db.session.add(equipment_group)
        db.session.flush()
    _sync_equipment_group_context_from_source(
        equipment_group,
        base_group_on_link if base_group_on_link and base_group_on_link.id != equipment_group.id else None,
        station,
    )

    return _create_equipment_group_set_with_retry(
        equipment_group.id,
        link.id,
    )


def get_station_fuel_equipment_group_choice_tuples(
    station_id: int,
    version_id: int | None = None,
) -> list[tuple[int, str]]:
    """
    Список (id, название) итоговых групп оборудования (gs_fue_equipment_groups),
    привязанных к электростанции через v2-связки для указанной версии БД,
    плюс дочерние/родительские группы составного кластера.
    """
    from app.fuel.services.equipment_groups.equipment_group_rebind_services import (
        get_station_fuel_equipment_group_choice_tuples as _choice_tuples,
    )

    return _choice_tuples(station_id, version_id)


def sync_machine_fuel_equipment_group(machine: Machine | None, version_id: int | None = None) -> EquipmentGroup | None:
    """
    Синхронизирует конкретную fuel-группу агрегата с его текущим типом группы оборудования.
    Если тип снят, очищает MachineFuelParam.equipment_group_id.
    """
    if machine is None:
        return None
    if version_id is None:
        version_id = getattr(machine, "database_version_id", None) or get_current_db_version_id()

    machine_fuel_param = getattr(machine, "machine_fuel_param", None)
    if machine_fuel_param is None and getattr(machine, "id", None):
        from app.fuel.services.equipment_groups.equipment_group_rebind_services import (
            _get_machine_fuel_param,
        )

        machine_fuel_param = _get_machine_fuel_param(machine.id, version_id)
    if machine.id_station and not machine.id_equipment_group:
        from app.fuel.services.equipment_groups.equipment_group_rebind_services import (
            apply_inferred_equipment_group_type_to_machine,
        )

        existing_group_id = (
            machine_fuel_param.equipment_group_id if machine_fuel_param else None
        )
        apply_inferred_equipment_group_type_to_machine(
            machine,
            version_id=version_id,
            equipment_group_id=existing_group_id,
        )
    if not machine.id_station or not machine.id_equipment_group:
        if machine_fuel_param is not None and machine_fuel_param.equipment_group_id is not None:
            machine_fuel_param.equipment_group_id = None
            db.session.add(machine_fuel_param)
        return None

    is_new_group = _machine_requires_new_equipment_group(machine, version_id)
    set_v2 = ensure_equipment_group_set_variant_for_station(
        station_id=machine.id_station,
        equipment_group_type_id=machine.id_equipment_group,
        version_id=version_id,
        is_new_group=is_new_group,
    )
    if set_v2 is None:
        if machine_fuel_param is not None and machine_fuel_param.equipment_group_id is not None:
            machine_fuel_param.equipment_group_id = None
            db.session.add(machine_fuel_param)
        return None

    if machine_fuel_param is None:
        from app.fuel.services.equipment_groups.equipment_group_rebind_services import (
            _ensure_machine_fuel_param,
        )

        machine_fuel_param = _ensure_machine_fuel_param(machine.id, version_id)

    if machine_fuel_param.equipment_group_id != set_v2.equipment_group_id:
        machine_fuel_param.equipment_group_id = set_v2.equipment_group_id
        db.session.add(machine_fuel_param)

    return set_v2.equipment_group

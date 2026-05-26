# -*- coding: utf-8 -*-
"""
Разрешение id сущности в текущей версии БД по external_code.

После смены версии в сессии числовой id в URL может относиться к другой версии;
external_code стабилен между версиями.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, TypeVar

from app.extensions import db
from app.common.services.database_version_filter import get_current_db_version_id

T = TypeVar("T")


def apply_db_version_filter(query, model_class: type, version_id: Optional[int]):
    if not hasattr(model_class, "database_version_id"):
        return query
    col = model_class.database_version_id
    if version_id is None:
        return query.filter(col.is_(None))
    return query.filter(col == version_id)


def load_by_id_with_version(
    model_class: type,
    entity_id: int,
    requested_version_id: Optional[int],
    *,
    query_factory: Optional[Callable[[], Any]] = None,
) -> Optional[T]:
    """
    Загружает запись по id в запрошенной версии БД.
    Если не найдена — по external_code якорной строки с этим id.
    """
    def _base_query():
        if query_factory is not None:
            return query_factory()
        return db.session.query(model_class).filter(model_class.id == entity_id)

    entity = apply_db_version_filter(_base_query(), model_class, requested_version_id).first()
    if entity:
        return entity

    # Якорь — запись с id из URL (без фильтра версии); при query_factory id уже в запросе
    if query_factory is not None:
        anchor = query_factory().first()
    else:
        anchor = db.session.query(model_class).filter(model_class.id == entity_id).first()
    if not anchor:
        return None

    external_code = (getattr(anchor, "external_code", None) or "").strip()
    if not external_code:
        return None

    resolved_q = db.session.query(model_class).filter(
        model_class.external_code == external_code
    )
    return apply_db_version_filter(resolved_q, model_class, requested_version_id).first()


def load_station_with_version(
    query_factory: Callable[[], Any],
    requested_version_id: Optional[int],
    *,
    station_id: Optional[int] = None,
):
    """Как load_by_id_with_version для Station с опциями joinedload в query_factory."""
    from app.generation.models.station.station_model import Station

    entity_id = station_id if station_id is not None else 0
    station = load_by_id_with_version(
        Station,
        entity_id,
        requested_version_id,
        query_factory=query_factory,
    )
    if station:
        return station, station.database_version_id
    return None, requested_version_id


def resolve_machine_details_ids(
    station_id: int,
    machine_id: int,
    requested_version_id: Optional[int] | None = None,
) -> Optional[tuple[int, int]]:
    """
    Возвращает (station_id, machine_id) в текущей версии БД или None.
    machine_id=0 (новый агрегат) — только станция.
    """
    from app.generation.models.station.station_model import Station
    from app.generation.models.machine.machine_model import Machine

    if requested_version_id is None:
        requested_version_id = get_current_db_version_id()

    station = load_by_id_with_version(Station, station_id, requested_version_id)
    if not station:
        return None

    if machine_id == 0:
        return station.id, 0

    machine = load_by_id_with_version(Machine, machine_id, requested_version_id)
    if not machine:
        return None

    if machine.id_station != station.id:
        station_for_machine = load_by_id_with_version(
            Station, machine.id_station, requested_version_id
        )
        if station_for_machine:
            station = station_for_machine

    return station.id, machine.id


def resolve_refdata_fk_id_for_version(
    model_cls,
    source_pk_id: int | None,
    target_version_id: Optional[int],
) -> int | None:
    """
    Находит id строки справочника с тем же ref_uuid в указанной версии БД.
    source_pk_id — id записи из формы (обычно текущей версии).
    """
    if source_pk_id is None:
        return None
    src = db.session.get(model_cls, int(source_pk_id))
    if not src:
        return None
    if getattr(src, "database_version_id", None) == target_version_id:
        return int(source_pk_id)
    ref_uuid = (getattr(src, "ref_uuid", None) or "").strip()
    if not ref_uuid:
        return None
    q = apply_db_version_filter(
        db.session.query(model_cls).filter(model_cls.ref_uuid == ref_uuid),
        model_cls,
        target_version_id,
    )
    tgt = q.first()
    return int(tgt.id) if tgt else None


def resolve_gen_company_id_for_version(
    anchor_gen_company_id: Optional[int], version_id: Optional[int]
) -> Optional[int]:
    """ID GenCompany в целевой версии БД по ref_uuid."""
    if not anchor_gen_company_id:
        return None
    from app.refdata.models.gen_companies.gen_company_model import GenCompany

    return resolve_refdata_fk_id_for_version(
        GenCompany, int(anchor_gen_company_id), version_id
    )


def resolve_station_group_id_for_version(
    group_id: Optional[int], version_id: Optional[int]
) -> Optional[int]:
    """ID StationGroup в целевой версии по имени (ref_uuid у групп станций нет)."""
    if not group_id:
        return None
    from app.generation.models.station.station_group_model import StationGroup

    sg = StationGroup.query.get(int(group_id))
    if not sg or not (sg.name or "").strip():
        return None
    if getattr(sg, "database_version_id", None) == version_id:
        return int(group_id)
    q = apply_db_version_filter(StationGroup.query, StationGroup, version_id).filter(
        StationGroup.name == sg.name
    )
    tgt = q.first()
    return int(tgt.id) if tgt else None


def resolve_entity_id_by_external_code_for_version(
    model_cls,
    source_pk_id: int | None,
    target_version_id: Optional[int],
) -> int | None:
    """ID сущности generation/fuel в целевой версии по external_code."""
    if source_pk_id is None:
        return None
    src = db.session.get(model_cls, int(source_pk_id))
    if not src:
        return None
    if getattr(src, "database_version_id", None) == target_version_id:
        return int(source_pk_id)
    external_code = (getattr(src, "external_code", None) or "").strip()
    if not external_code:
        return None
    q = apply_db_version_filter(
        db.session.query(model_cls).filter(model_cls.external_code == external_code),
        model_cls,
        target_version_id,
    )
    tgt = q.first()
    return int(tgt.id) if tgt else None


def resolve_fuel_equipment_group_id_for_version(
    source_pk_id: int | None, target_version_id: Optional[int]
) -> int | None:
    """ID EquipmentGroup (топливный модуль) в целевой версии по external_code."""
    if source_pk_id is None:
        return None
    from app.fuel.models.fue_equipment_group_model import EquipmentGroup

    return resolve_entity_id_by_external_code_for_version(
        EquipmentGroup, source_pk_id, target_version_id
    )


def resolve_equipment_group_type_id_for_version(
    anchor_type_id: int, version_id: Optional[int]
) -> Optional[int]:
    """ID типа группы оборудования в справочнике для версии vid (ref_uuid или имя)."""
    from sqlalchemy import func as sa_func

    from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
        EquipmentGroupType,
    )

    anchor = EquipmentGroupType.query.get(anchor_type_id)
    if not anchor:
        return None

    anchor_vid = getattr(anchor, "database_version_id", None)
    if (anchor_vid is None and version_id is None) or (anchor_vid == version_id):
        return anchor.id

    type_ref_uuid = getattr(anchor, "ref_uuid", None)
    if type_ref_uuid:
        t = apply_db_version_filter(
            EquipmentGroupType.query.filter(
                EquipmentGroupType.ref_uuid == type_ref_uuid
            ),
            EquipmentGroupType,
            version_id,
        ).first()
        if t:
            return t.id

    type_name = (anchor.name or "").strip()
    if type_name:
        t = apply_db_version_filter(
            EquipmentGroupType.query.filter(EquipmentGroupType.name == type_name),
            EquipmentGroupType,
            version_id,
        ).first()
        if t:
            return t.id
        t = apply_db_version_filter(
            EquipmentGroupType.query.filter(
                sa_func.lower(sa_func.trim(EquipmentGroupType.name))
                == type_name.lower()
            ),
            EquipmentGroupType,
            version_id,
        ).first()
        if t:
            return t.id

    return None


def entity_log_ids_by_external_code(model_class: type, entity_id: int) -> list[int]:
    """
    Все id записей с тем же external_code (копии по версиям БД).
    Для журнала изменений: log.entity_id — id версии, из которой сохраняли.
    """
    anchor = db.session.get(model_class, entity_id)
    if anchor is None:
        anchor = db.session.query(model_class).filter(model_class.id == entity_id).first()
    if not anchor:
        return [entity_id]
    external_code = (getattr(anchor, "external_code", None) or "").strip()
    if not external_code:
        return [entity_id]
    ids = [
        row[0]
        for row in db.session.query(model_class.id)
        .filter(model_class.external_code == external_code)
        .all()
    ]
    if entity_id not in ids:
        ids.append(entity_id)
    return ids or [entity_id]

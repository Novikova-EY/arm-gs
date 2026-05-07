# -*- coding: utf-8 -*-
"""Helpers for stations_equipment_groups based on v2 equipment group models."""

from __future__ import annotations

from collections import defaultdict
import re

from sqlalchemy import and_, exists, func, or_, cast, select
from sqlalchemy.types import String
from sqlalchemy.orm import aliased, selectinload

from app.common.services.help_services import _clean_name
from app.common.services.database_version_filter import get_current_db_version_id
from app.generation.models.machine.machine_model import Machine
from app.common.services.get_services.years.years_get_services import (
    get_filter_start_year,
    get_filter_end_year,
)
from app.fuel.models.fue_equipment_group_set_station_model import (
    EquipmentGroupSetStation,
)
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_model import EquipmentGroup


def _normalized_sql_text(expr):
    """Грубая SQL-нормализация строк для legacy-сопоставлений по названию."""
    text_expr = func.coalesce(cast(expr, String), "")
    return func.lower(
        func.replace(
            func.replace(
                func.replace(
                    func.replace(text_expr, " ", ""),
                    ".",
                    "",
                ),
                "-",
                "",
            ),
            '"',
            "",
        )
    )


def _territorial_direct_match_clause(eg, filters, version_id):
    """
    Совпадение с выбранными ФО / субъектом / РЭС по полям regional_*_id у EquipmentGroup.
    """
    from app.refdata.models.territories.regional_district_model import RegionalDistrict

    res_ids = filters.get("regional_energy_system_filter") or None
    rd_ids = filters.get("regional_district_filter") or None
    fd_ids = filters.get("federal_district_filter") or None
    parts = []
    if res_ids:
        parts.append(eg.regional_energy_system_id.in_(res_ids))
    if rd_ids:
        parts.append(eg.regional_district_id.in_(rd_ids))
    if fd_ids:
        RD = RegionalDistrict
        rd_ver = (
            RD.database_version_id.is_(None)
            if version_id is None
            else RD.database_version_id == version_id
        )
        parts.append(
            exists(
                select(1)
                .select_from(RD)
                .where(
                    RD.id == eg.regional_district_id,
                    RD.id_federal_district.in_(fd_ids),
                    rd_ver,
                )
            )
        )
    if not parts:
        return None
    return and_(*parts)


def _equipment_group_ids_with_station_links_subquery():
    """
    Подзапрос групп, у которых есть хотя бы одна реальная station-bound связь.

    Связки EquipmentGroupSet -> EquipmentGroupSetStation со `station_id = NULL`
    считаем standalone-логикой для котельных и не исключаем такие группы из
    standalone-выборок страницы.
    """
    from app.extensions import db

    return (
        db.session.query(EquipmentGroupSet.equipment_group_id)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSet.equipment_group_set_station_id == EquipmentGroupSetStation.id,
        )
        .filter(EquipmentGroupSetStation.station_id.isnot(None))
        .distinct()
    )


def _territorial_obl_mapping_match_exists(eg, filters, version_id):
    """
    Для котельных и др. групп, у которых obl задан, а regional_*_id в строке БД пусты:
    сопоставление через TerritoriesEnergyExternalMapping → RegionalDistrict / РЭС.
    РЭС: прямое совпадение по маппингу или связь субъект↔РЭС (M2M), как в карточке группы.
    """
    from app.fuel.models.external_mapping.fue_em_federal_district_model import (
        FederalDistrictExternalMapping,
    )
    from app.fuel.models.external_mapping.fue_em_territories_energy_model import (
        TerritoriesEnergyExternalMapping,
    )
    from app.refdata.models.territories.federal_district_model import FederalDistrict
    from app.refdata.models.energy_systems.regional_energy_system_model import (
        RegionalEnergySystem,
    )
    from app.refdata.models.energy_systems.regional_district_regional_energy_system_model import (
        regional_district_regional_energy_system,
    )
    from app.refdata.models.territories.regional_district_model import RegionalDistrict

    TEM = TerritoriesEnergyExternalMapping
    RD = RegionalDistrict
    FD = FederalDistrict
    FDEM = FederalDistrictExternalMapping
    RES = RegionalEnergySystem

    res_ids = filters.get("regional_energy_system_filter") or None
    rd_ids = filters.get("regional_district_filter") or None
    fd_ids = filters.get("federal_district_filter") or None
    if not (res_ids or rd_ids or fd_ids):
        return None

    obl_link = or_(
        cast(TEM.obl, String) == cast(eg.obl, String),
        cast(eg.obl, String) == TEM.external_id,
    )
    rd_ver = (
        RD.database_version_id.is_(None)
        if version_id is None
        else RD.database_version_id == version_id
    )
    fd_ver = (
        FD.database_version_id.is_(None)
        if version_id is None
        else FD.database_version_id == version_id
    )
    res_ver = (
        or_(RES.id.is_(None), RES.database_version_id.is_(None))
        if version_id is None
        else or_(RES.id.is_(None), RES.database_version_id == version_id)
    )

    stmt = (
        select(1)
        .select_from(TEM)
        .outerjoin(RD, RD.ref_uuid == TEM.regional_district_ref_uuid)
        .outerjoin(RES, RES.ref_uuid == TEM.regional_energy_system_ref_uuid)
        .where(
            obl_link,
            res_ver,
        )
    )
    if rd_ids:
        RDByName = aliased(RD)
        normalized_tem_external_name = _normalized_sql_text(TEM.external_name)
        normalized_tem_name_ext = _normalized_sql_text(TEM.name_ext)
        rd_name_match_exists = exists(
            select(1)
            .select_from(RDByName)
            .where(
                RDByName.id.in_(rd_ids),
                (
                    RDByName.database_version_id.is_(None)
                    if version_id is None
                    else RDByName.database_version_id == version_id
                ),
                or_(
                    normalized_tem_external_name.like(
                        func.concat("%", _normalized_sql_text(RDByName.name), "%")
                    ),
                    normalized_tem_external_name.like(
                        func.concat("%", _normalized_sql_text(RDByName.name_full), "%")
                    ),
                    normalized_tem_name_ext.like(
                        func.concat("%", _normalized_sql_text(RDByName.name), "%")
                    ),
                    normalized_tem_name_ext.like(
                        func.concat("%", _normalized_sql_text(RDByName.name_full), "%")
                    ),
                ),
            )
        )
        stmt = stmt.where(
            or_(
                and_(RD.id.in_(rd_ids), rd_ver),
                and_(TEM.regional_district_ref_uuid.is_(None), rd_name_match_exists),
            )
        )
    if fd_ids:
        fd_mapping_match = exists(
            select(1)
            .select_from(FDEM)
            .join(FD, FD.ref_uuid == FDEM.federal_district_ref_uuid)
            .where(
                or_(
                    FDEM.external_id == cast(TEM.fo, String),
                    FDEM.external_id == cast(eg.fo, String),
                ),
                FD.id.in_(fd_ids),
                fd_ver,
            )
        )
        stmt = stmt.where(
            or_(
                and_(RD.id_federal_district.in_(fd_ids), rd_ver),
                fd_mapping_match,
            )
        )
    if res_ids:
        assoc_match_exists = exists(
            select(1)
            .select_from(regional_district_regional_energy_system)
            .where(
                regional_district_regional_energy_system.c.regional_district_id == RD.id,
                regional_district_regional_energy_system.c.regional_energy_system_id.in_(
                    res_ids
                ),
            )
        )
        assoc_other_exists = exists(
            select(1)
            .select_from(regional_district_regional_energy_system)
            .where(
                regional_district_regional_energy_system.c.regional_district_id == RD.id,
                ~regional_district_regional_energy_system.c.regional_energy_system_id.in_(
                    res_ids
                ),
            )
        )
        stmt = stmt.where(
            or_(
                RES.id.in_(res_ids),
                and_(
                    TEM.regional_energy_system_ref_uuid.is_(None),
                    assoc_match_exists,
                    ~assoc_other_exists,
                ),
            )
        )

    return exists(stmt)


def _territorial_filter_or_fk_or_obl(eg, filters, version_id):
    """ФО / субъект / РЭС: прямой FK ИЛИ маппинг по obl (котельные без заполненных FK)."""
    need = (
        filters.get("regional_energy_system_filter")
        or filters.get("regional_district_filter")
        or filters.get("federal_district_filter")
    )
    if not need:
        return None
    direct = _territorial_direct_match_clause(eg, filters, version_id)
    obl_ex = _territorial_obl_mapping_match_exists(eg, filters, version_id)
    if direct is not None and obl_ex is not None:
        return or_(direct, obl_ex)
    return direct if direct is not None else obl_ex


def get_standalone_equipment_group_ids(version_id=None, strict_version=False):
    """
    Возвращает множество ID групп оборудования (EquipmentGroup), не привязанных
    ни к одной электростанции (нет записей в EquipmentGroupSet).

    :param strict_version: если True, при выбранной версии только database_version_id == version_id.
    """
    from app.extensions import db

    if version_id is None:
        version_id = get_current_db_version_id()

    subq = _equipment_group_ids_with_station_links_subquery()
    q = db.session.query(EquipmentGroup.id).filter(
        ~EquipmentGroup.id.in_(subq)
    )
    if version_id is None:
        q = q.filter(EquipmentGroup.database_version_id.is_(None))
    elif strict_version:
        q = q.filter(EquipmentGroup.database_version_id == version_id)
    else:
        q = q.filter(or_(EquipmentGroup.database_version_id == version_id, EquipmentGroup.database_version_id.is_(None)))
    return {r[0] for r in q.all()}


def get_standalone_equipment_group_blocks(version_id=None, only_ids=None):
    """
    Возвращает блоки для одиночных групп оборудования в формате, совместимом
    с reorganize_by_equipment_group_first: list of
    {equipment_group, rowspan, station_entries: [{station, station_rowspan, links: [{equipment_group_type, machines, rowspan}]}]}).
    Для одиночных групп: station=None, агрегаты не выводятся.
    Если для группы есть связи через EquipmentGroupSet -> EquipmentGroupSetStation,
    показываем типы групп оборудования; иначе рисуем одну пустую строку.

    :param only_ids: если задан, загружаются только эти ID (без полного скана всех standalone).
    """
    if only_ids is not None:
        ids = set(only_ids)
    else:
        ids = get_standalone_equipment_group_ids(version_id)
    if not ids:
        return []

    groups = (
        EquipmentGroup.query.filter(EquipmentGroup.id.in_(ids))
        .options(
            selectinload(EquipmentGroup.regional_district),
            selectinload(EquipmentGroup.regional_energy_system),
            selectinload(EquipmentGroup.territories_energy_external_mapping),
            selectinload(EquipmentGroup.department_external_mapping),
            selectinload(EquipmentGroup.union_energy_system_external_mapping),
            selectinload(EquipmentGroup.economic_region_external_mapping),
            selectinload(EquipmentGroup.federal_district_external_mapping),
            selectinload(EquipmentGroup.business_unit_external_mapping),
            selectinload(EquipmentGroup.gen_company_external_mapping),
            selectinload(EquipmentGroup.gen_company_branch_external_mapping),
            selectinload(EquipmentGroup.cities_external_mapping),
            selectinload(EquipmentGroup.equipment_group_links_v2).selectinload(
                EquipmentGroupSet.equipment_group_set_station
            ).selectinload(EquipmentGroupSetStation.equipment_group_type),
        )
        .order_by(EquipmentGroup.name, EquipmentGroup.name_ext, EquipmentGroup.id)
        .all()
    )

    def _dedupe_key(group):
        external_code = (getattr(group, "external_code", None) or "").strip()
        return external_code or f"id:{getattr(group, 'id', None)}"

    def _dedupe_priority(group):
        group_version_id = getattr(group, "database_version_id", None)
        return (
            0 if version_id is not None and group_version_id == version_id else 1,
            0 if group_version_id is not None else 1,
            -(getattr(group, "id", 0) or 0),
        )

    deduped_groups = {}
    for group in groups:
        key = _dedupe_key(group)
        current_best = deduped_groups.get(key)
        if current_best is None or _dedupe_priority(group) < _dedupe_priority(
            current_best
        ):
            deduped_groups[key] = group

    groups = list(deduped_groups.values())
    groups.sort(key=_equipment_group_sort_key)

    blocks = []
    for eg in groups:
        links_data = []
        for eg_set in (eg.equipment_group_links_v2 or []):
            eg_set_station = getattr(eg_set, "equipment_group_set_station", None)
            if not eg_set_station or getattr(eg_set_station, "station_id", None) is not None:
                continue
            if not _is_current_version(eg_set_station, version_id):
                continue
            links_data.append(
                {
                    "equipment_group_type": getattr(
                        eg_set_station, "equipment_group_type", None
                    ),
                    "machines": [],
                    "rowspan": 1,
                }
            )
        if not links_data:
            links_data = [
                {
                    "equipment_group_type": None,
                    "machines": [],
                    "rowspan": 1,
                }
            ]
        links_data.sort(
            key=lambda item: _equipment_group_type_sort_key(
                item.get("equipment_group_type")
            )
        )
        blocks.append({
            "equipment_group": eg,
            "rowspan": len(links_data),
            "station_entries": [
                {
                    "station": None,
                    "station_rowspan": len(links_data),
                    "links": links_data,
                }
            ],
            "has_multiple_equipment_group_set_station": False,
        })
    return blocks


def _union_energy_system_and_est_filter_clause(eg_model, filters, version_id):
    """
    Фильтр по ОЭС и типу ЕЭС для EquipmentGroup.

    Раньше использовался только INNER JOIN: oes → UnionEnergySystemExternalMapping.
    У части групп oes пустой, но заполнен regional_energy_system_id — тогда цепочка
    РЭС → ОЭС → тип ЕЭС из справочника должна проходить так же, как у станций.
    """
    ues_ids = filters.get("union_energy_system_filter") or []
    est_ids = filters.get("energy_system_type_filter") or []
    if not ues_ids and not est_ids:
        return None

    from app.fuel.models.external_mapping.fue_em_union_energy_system_model import (
        UnionEnergySystemExternalMapping,
    )
    from app.refdata.models.energy_systems.union_energy_system_model import (
        UnionEnergySystem,
    )
    from app.refdata.models.energy_systems.regional_energy_system_model import (
        RegionalEnergySystem,
    )

    UESM = UnionEnergySystemExternalMapping
    UES = UnionEnergySystem
    RES = RegionalEnergySystem

    ues_conds = []
    if ues_ids:
        ues_conds.append(UES.id.in_(ues_ids))
    if est_ids:
        ues_conds.append(UES.id_energy_system_type.in_(est_ids))
    ues_hierarchy_match = and_(*ues_conds)

    if version_id is None:
        ues_ver = UES.database_version_id.is_(None)
        res_ver = RES.database_version_id.is_(None)
    else:
        ues_ver = UES.database_version_id == version_id
        res_ver = or_(RES.database_version_id == version_id, RES.database_version_id.is_(None))

    oes_path = exists(
        select(1)
        .select_from(UESM)
        .join(UES, UESM.union_energy_system_ref_uuid == UES.ref_uuid)
        .where(
            cast(eg_model.oes, String) == UESM.external_id,
            ues_hierarchy_match,
            ues_ver,
        )
    )

    res_path = exists(
        select(1)
        .select_from(RES)
        .join(UES, RES.id_union_energy_system == UES.id)
        .where(
            eg_model.regional_energy_system_id == RES.id,
            ues_hierarchy_match,
            ues_ver,
            res_ver,
        )
    )

    return or_(oes_path, res_path)


def get_filtered_standalone_equipment_group_ids(filters, version_id=None, strict_version=False):
    """
    Возвращает ID standalone-групп (котельные и др.), отфильтрованных по
    территориальным атрибутам самой группы (obl, oes через external mapping).

    :param strict_version: если True, при выбранной версии показывать только группы
        с database_version_id == version_id (без legacy NULL). Для страницы
        stations_equipment_group_fuel_params.
    """
    from app.extensions import db

    if version_id is None:
        version_id = get_current_db_version_id()

    _filters = {k: v for k, v in (filters or {}).items()
                if k not in ("page", "start_year", "end_year")}
    territorial_keys = (
        "energy_system_type_filter",
        "union_energy_system_filter",
        "regional_energy_system_filter",
        "federal_district_filter",
        "regional_district_filter",
    )
    equipment_group_name_filter = (_filters.get("equipment_group_name_filter") or "").strip() or None
    if not any(_filters.get(k) for k in territorial_keys) and not equipment_group_name_filter:
        return get_standalone_equipment_group_ids(version_id, strict_version=strict_version)

    subq = _equipment_group_ids_with_station_links_subquery()
    q = (
        db.session.query(EquipmentGroup.id)
        .filter(~EquipmentGroup.id.in_(subq))
    )
    # Фильтр по версии: strict_version=True — только текущая (для fuel_params)
    if version_id is None:
        q = q.filter(EquipmentGroup.database_version_id.is_(None))
    elif strict_version:
        q = q.filter(EquipmentGroup.database_version_id == version_id)
    else:
        q = q.filter(or_(EquipmentGroup.database_version_id == version_id, EquipmentGroup.database_version_id.is_(None)))

    terr_clause = _territorial_filter_or_fk_or_obl(EquipmentGroup, _filters, version_id)
    if terr_clause is not None:
        q = q.filter(terr_clause)

    ues_est_clause = _union_energy_system_and_est_filter_clause(
        EquipmentGroup, _filters, version_id
    )
    if ues_est_clause is not None:
        q = q.filter(ues_est_clause)

    # Фильтр по названию группы оборудования (для котельных и др. standalone)
    if equipment_group_name_filter:
        pattern = f"%{equipment_group_name_filter}%"
        q = q.filter(
            or_(
                EquipmentGroup.name.ilike(pattern),
                EquipmentGroup.name_ext.ilike(pattern),
            )
        )

    return {r[0] for r in q.distinct().all()}


def _linked_equipment_group_ids_matching_station_filters(
    _filters, version_id, strict_version: bool = False
):
    """
    ID групп оборудования со связью на станцию, удовлетворяющую фильтрам
    названия электростанции и/или генерирующей компании (логика как у station_list).

    Возвращает None, если оба фильтра пусты — тогда ограничение не применяется.
    Standalone-группы (без station_id) в результат не входят.
    """
    station_name = (_filters.get("station_name_filter") or "").strip()
    gen_company = (_filters.get("gen_company_filter") or "").strip()
    if not station_name and not gen_company:
        return None

    from app.extensions import db
    from app.generation.models.station.station_model import Station
    from app.generation.models.machine.machine_model import Machine
    from app.refdata.models.gen_companies.gen_company_model import GenCompany

    q = (
        db.session.query(EquipmentGroupSet.equipment_group_id)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSetStation.id == EquipmentGroupSet.equipment_group_set_station_id,
        )
        .join(EquipmentGroup, EquipmentGroup.id == EquipmentGroupSet.equipment_group_id)
        .join(Station, Station.id == EquipmentGroupSetStation.station_id)
        .filter(EquipmentGroupSetStation.station_id.isnot(None))
    )

    if version_id is None:
        q = q.filter(EquipmentGroup.database_version_id.is_(None))
        q = q.filter(EquipmentGroupSetStation.database_version_id.is_(None))
    elif strict_version:
        q = q.filter(EquipmentGroup.database_version_id == version_id)
        q = q.filter(EquipmentGroupSetStation.database_version_id == version_id)
    else:
        q = q.filter(
            or_(
                EquipmentGroup.database_version_id == version_id,
                EquipmentGroup.database_version_id.is_(None),
            )
        )
        q = q.filter(
            or_(
                EquipmentGroupSetStation.database_version_id == version_id,
                EquipmentGroupSetStation.database_version_id.is_(None),
            )
        )

    if station_name:
        q = q.filter(Station.name.ilike(f"%{station_name}%"))

    if gen_company:
        gen_rows = GenCompany.query.filter(GenCompany.name.ilike(f"%{gen_company}%")).all()
        gen_ids = [c.id for c in gen_rows]
        if not gen_ids:
            return set()
        q = q.join(Machine, Machine.id_station == Station.id).filter(
            Machine.id_gen_company.in_(gen_ids)
        )

    return {r[0] for r in q.distinct().all()}


def get_filtered_equipment_group_ids_all(
    filters,
    version_id=None,
    strict_version=False,
    standalone_ids_precalc=None,
):
    """
    EquipmentGroup-first: возвращает ID всех групп оборудования (и привязанных к станциям,
    и standalone), отфильтрованных по атрибутам самой EquipmentGroup.

    Фильтры: территориальные (EST, ОЭС, РЭС, ФО, субъект), название группы,
    тип электростанции ТЭС (для привязанных групп — только если станция ТЭС; standalone всегда включаются).

    :param standalone_ids_precalc: если передан (например из build_equipment_group_hierarchy_eg_first),
        не вызывается повторный запрос get_standalone_equipment_group_ids при фильтре по типу электростанции.
    """
    from app.extensions import db
    from app.generation.models.station.station_model import Station

    if version_id is None:
        version_id = get_current_db_version_id()

    _filters = {k: v for k, v in (filters or {}).items()
                if k not in ("page", "start_year", "end_year")}

    # Базовый запрос: все EquipmentGroup (без ограничения standalone)
    q = db.session.query(EquipmentGroup.id)
    if version_id is None:
        q = q.filter(EquipmentGroup.database_version_id.is_(None))
    elif strict_version:
        q = q.filter(EquipmentGroup.database_version_id == version_id)
    else:
        q = q.filter(or_(
            EquipmentGroup.database_version_id == version_id,
            EquipmentGroup.database_version_id.is_(None),
        ))

    # Территориальные фильтры (FK или obl→маппинг для котельных без заполненных regional_*_id)
    terr_clause = _territorial_filter_or_fk_or_obl(EquipmentGroup, _filters, version_id)
    if terr_clause is not None:
        q = q.filter(terr_clause)

    ues_est_clause = _union_energy_system_and_est_filter_clause(
        EquipmentGroup, _filters, version_id
    )
    if ues_est_clause is not None:
        q = q.filter(ues_est_clause)

    equipment_group_name_filter = (_filters.get("equipment_group_name_filter") or "").strip() or None
    if equipment_group_name_filter:
        pattern = f"%{equipment_group_name_filter}%"
        q = q.filter(
            or_(
                EquipmentGroup.name.ilike(pattern),
                EquipmentGroup.name_ext.ilike(pattern),
            )
        )

    territorial_ids = {r[0] for r in q.distinct().all()}

    station_pick = _linked_equipment_group_ids_matching_station_filters(
        _filters, version_id, strict_version
    )
    if station_pick is not None:
        territorial_ids &= station_pick

    # Фильтр по типу электростанции ТЭС: оставляем группы, привязанные к ТЭС, или standalone
    station_type_filter = _filters.get("station_type_filter")
    if not station_type_filter:
        return territorial_ids

    subq_linked = (
        db.session.query(EquipmentGroupSet.equipment_group_id)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSetStation.id == EquipmentGroupSet.equipment_group_set_station_id,
        )
        .join(Station, Station.id == EquipmentGroupSetStation.station_id)
        .filter(Station.id_station_type.in_(station_type_filter))
        .distinct()
    )
    ids_linked_to_tes = {r[0] for r in subq_linked.all()}
    if standalone_ids_precalc is not None:
        standalone_ids = standalone_ids_precalc
    else:
        standalone_ids = get_standalone_equipment_group_ids(
            version_id, strict_version=strict_version
        )
    allowed_ids = ids_linked_to_tes | standalone_ids
    return territorial_ids & allowed_ids


def _get_ordered_equipment_group_ids(filtered_eg_ids):
    """Возвращает ID групп оборудования в порядке отображения на странице."""
    if not filtered_eg_ids:
        return []

    from app.extensions import db

    rows = (
        db.session.query(EquipmentGroup.id)
        .filter(EquipmentGroup.id.in_(filtered_eg_ids))
        .order_by(EquipmentGroup.name, EquipmentGroup.name_ext, EquipmentGroup.id)
        .all()
    )
    return [row[0] for row in rows]


def _build_visible_equipment_group_blocks(
    ordered_eg_ids,
    standalone_ids,
    version_id,
    filters=None,
    start_year=None,
    end_year=None,
):
    """
    Строит только реально отображаемые блоки групп оборудования и сохраняет
    исходный порядок ordered_eg_ids.
    """
    if not ordered_eg_ids:
        return []

    ordered_id_set = set(ordered_eg_ids)
    standalone_chunk_ids = ordered_id_set & standalone_ids
    linked_ids = [eg_id for eg_id in ordered_eg_ids if eg_id not in standalone_chunk_ids]
    blocks_by_id = {}

    if linked_ids:
        linked_blocks = build_equipment_group_blocks_from_eg_ids(
            set(linked_ids),
            filters=filters,
            start_year=start_year,
            end_year=end_year,
        )
        for block in linked_blocks:
            eg = block.get("equipment_group")
            eg_id = getattr(eg, "id", None)
            if eg_id is not None:
                blocks_by_id[eg_id] = block

    if standalone_chunk_ids:
        standalone_blocks = get_standalone_equipment_group_blocks(
            version_id,
            only_ids=standalone_chunk_ids,
        )
        for block in standalone_blocks:
            eg = block.get("equipment_group")
            eg_id = getattr(eg, "id", None)
            if eg_id is not None:
                blocks_by_id[eg_id] = block

    return [blocks_by_id[eg_id] for eg_id in ordered_eg_ids if eg_id in blocks_by_id]


def _paginate_visible_equipment_group_blocks(
    filtered_eg_ids,
    standalone_ids,
    version_id,
    filters=None,
    start_year=None,
    end_year=None,
    page=1,
    per_page=None,
):
    """
    Пагинирует по реально отображаемым группам оборудования, а не по сырым ID.
    Это гарантирует, что на странице видно ровно N групп, если они существуют.
    """
    ordered_eg_ids = _get_ordered_equipment_group_ids(filtered_eg_ids)
    if not ordered_eg_ids:
        return [], 0, 1, 1

    if isinstance(per_page, str) and per_page.lower() == "all":
        blocks = _build_visible_equipment_group_blocks(
            ordered_eg_ids,
            standalone_ids,
            version_id,
            filters=filters,
            start_year=start_year,
            end_year=end_year,
        )
        return blocks, len(blocks), 1, 1

    try:
        per_page_int = int(per_page)
    except (TypeError, ValueError):
        per_page_int = None

    if per_page_int is None or per_page_int <= 0:
        blocks = _build_visible_equipment_group_blocks(
            ordered_eg_ids,
            standalone_ids,
            version_id,
            filters=filters,
            start_year=start_year,
            end_year=end_year,
        )
        return blocks, len(blocks), 1, 1

    requested_page = max(int(page or 1), 1)
    chunk_size = max(per_page_int * 3, 50)

    def collect_page_blocks(target_page):
        target_start = (target_page - 1) * per_page_int
        target_end = target_start + per_page_int
        visible_total = 0
        page_blocks = []

        for start_idx in range(0, len(ordered_eg_ids), chunk_size):
            chunk_ids = ordered_eg_ids[start_idx:start_idx + chunk_size]
            chunk_blocks = _build_visible_equipment_group_blocks(
                chunk_ids,
                standalone_ids,
                version_id,
                filters=filters,
                start_year=start_year,
                end_year=end_year,
            )
            chunk_count = len(chunk_blocks)
            if chunk_count and visible_total < target_end and visible_total + chunk_count > target_start:
                slice_start = max(0, target_start - visible_total)
                slice_end = min(chunk_count, target_end - visible_total)
                page_blocks.extend(chunk_blocks[slice_start:slice_end])
            visible_total += chunk_count

        return page_blocks, visible_total

    page_blocks, visible_total = collect_page_blocks(requested_page)
    total_pages = max(1, (visible_total + per_page_int - 1) // per_page_int)
    current_page = min(requested_page, total_pages)

    if current_page != requested_page:
        page_blocks, visible_total = collect_page_blocks(current_page)

    return page_blocks, visible_total, total_pages, current_page


def _paginate_equipment_group_hierarchy(hierarchy, page=1, per_page=None):
    """
    Пагинация по финальному порядку отображения на странице:
    EST -> UES -> РЭС -> equipment_group_blocks.
    """
    flat_items = []
    for est_block in hierarchy or []:
        for ues_block in est_block.get("ues_list", []):
            for res_block in ues_block.get("res_list", []):
                for equipment_group_block in res_block.get("equipment_group_blocks", []):
                    flat_items.append(
                        {
                            "est_id": est_block.get("est_id"),
                            "est_name": est_block.get("est_name"),
                            "ues_id": ues_block.get("ues_id"),
                            "ues_name": ues_block.get("ues_name"),
                            "res_id": res_block.get("res_id"),
                            "res_name": res_block.get("res_name"),
                            "equipment_group_block": equipment_group_block,
                        }
                    )

    total_count = len(flat_items)
    if not flat_items:
        return [], 0, 1, 1

    if isinstance(per_page, str) and per_page.lower() == "all":
        return hierarchy, total_count, 1, 1

    try:
        per_page_int = int(per_page)
    except (TypeError, ValueError):
        per_page_int = None

    if per_page_int is None or per_page_int <= 0:
        return hierarchy, total_count, 1, 1

    total_pages = max(1, (total_count + per_page_int - 1) // per_page_int)
    current_page = min(max(int(page or 1), 1), total_pages)
    start_idx = (current_page - 1) * per_page_int
    end_idx = start_idx + per_page_int
    page_items = flat_items[start_idx:end_idx]

    grouped = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    est_names = {}
    ues_names = {}
    res_names = {}
    for item in page_items:
        est_id = item["est_id"]
        ues_id = item["ues_id"]
        res_id = item["res_id"]
        est_names[est_id] = item["est_name"]
        ues_names[ues_id] = item["ues_name"]
        res_names[res_id] = item["res_name"]
        grouped[est_id][ues_id][res_id].append(item["equipment_group_block"])

    paged_hierarchy = []
    for est_block in hierarchy or []:
        est_id = est_block.get("est_id")
        if est_id not in grouped:
            continue
        ues_list = []
        for ues_block in est_block.get("ues_list", []):
            ues_id = ues_block.get("ues_id")
            if ues_id not in grouped[est_id]:
                continue
            res_list = []
            for res_block in ues_block.get("res_list", []):
                res_id = res_block.get("res_id")
                blocks = grouped[est_id][ues_id].get(res_id)
                if not blocks:
                    continue
                res_list.append(
                    {
                        "res_id": res_id,
                        "res_name": res_names.get(res_id, res_block.get("res_name")),
                        "equipment_group_blocks": blocks,
                    }
                )
            if res_list:
                ues_list.append(
                    {
                        "ues_id": ues_id,
                        "ues_name": ues_names.get(ues_id, ues_block.get("ues_name")),
                        "res_list": res_list,
                    }
                )
        if ues_list:
            paged_hierarchy.append(
                {
                    "est_id": est_id,
                    "est_name": est_names.get(est_id, est_block.get("est_name")),
                    "ues_list": ues_list,
                }
            )

    return paged_hierarchy, total_count, total_pages, current_page


def _version_filter_with_legacy(query, model_class):
    """
    Добавляет фильтр по версии БД с учетом legacy (как _filter_by_version_with_fallback):
    при текущей версии — включаем и текущую версию, и записи без версии (NULL).
    """
    version_id = get_current_db_version_id()
    if not hasattr(model_class, "database_version_id"):
        return query
    col = model_class.database_version_id
    if version_id is None:
        return query.filter(col.is_(None))
    return query.filter(or_(col == version_id, col.is_(None)))


def get_equipment_group_ids_for_stations(station_ids):
    """
    Возвращает множество ID групп оборудования (EquipmentGroup), связанных
    со станциями через EquipmentGroupSet -> EquipmentGroupSetStation.
    """
    if not station_ids:
        return set()
    from app.extensions import db

    q = (
        db.session.query(EquipmentGroup.id)
        .join(EquipmentGroupSet, EquipmentGroupSet.equipment_group_id == EquipmentGroup.id)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSetStation.id == EquipmentGroupSet.equipment_group_set_station_id,
        )
        .filter(EquipmentGroupSetStation.station_id.in_(station_ids))
    )
    q = _version_filter_with_legacy(q, EquipmentGroupSetStation)
    q = _version_filter_with_legacy(q, EquipmentGroup)
    return {r[0] for r in q.distinct().all()}


def get_filtered_equipment_group_ids(filters, start_year=None, end_year=None):
    """
    Возвращает множество ID групп оборудования (EquipmentGroup), соответствующих
    применяемым фильтрам станций. Список формируется по модели EquipmentGroup
    через связь EquipmentGroupSet -> EquipmentGroupSetStation -> Station.

    Учитывает database_version_id с fallback на legacy (NULL), как в
    build_station_equipment_groups_v2.
    """
    from app.generation.services.station_services.station_services import get_stations_list

    _start = start_year if start_year is not None else get_filter_start_year()
    _end = end_year if end_year is not None else get_filter_end_year()

    _filters = {k: v for k, v in (filters or {}).items()
                if k not in ("page", "start_year", "end_year")}
    result = get_stations_list(
        page=1,
        per_page=1,
        start_year=_start,
        end_year=_end,
        return_ids_only=True,
        **_filters,
    )
    station_ids = result.get("station_ids") or []
    if not station_ids:
        return set()

    from app.extensions import db

    # ID берутся из EquipmentGroup (модель — источник)
    # Фильтр по версии с учетом legacy (как build_station_equipment_groups_v2)
    q = (
        db.session.query(EquipmentGroup.id)
        .join(EquipmentGroupSet, EquipmentGroupSet.equipment_group_id == EquipmentGroup.id)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSetStation.id == EquipmentGroupSet.equipment_group_set_station_id,
        )
        .filter(EquipmentGroupSetStation.station_id.in_(station_ids))
    )
    q = _version_filter_with_legacy(q, EquipmentGroupSetStation)
    q = _version_filter_with_legacy(q, EquipmentGroup)

    # Фильтр по названию группы оборудования
    equipment_group_name_filter = (_filters.get("equipment_group_name_filter") or "").strip() or None
    if equipment_group_name_filter:
        pattern = f"%{equipment_group_name_filter}%"
        q = q.filter(
            or_(
                EquipmentGroup.name.ilike(pattern),
                EquipmentGroup.name_ext.ilike(pattern),
            )
        )

    rows = q.distinct().all()
    return {r[0] for r in rows}


def _is_current_version(entity, current_version_id) -> bool:
    if entity is None:
        return False
    if not hasattr(entity, "database_version_id"):
        return True
    if current_version_id is None:
        return entity.database_version_id is None
    return entity.database_version_id == current_version_id


def _filter_by_version_with_fallback(items, current_version_id):
    """
    Возвращает элементы текущей версии, а если их нет — элементы без версии (legacy).
    """
    if not items:
        return []
    if current_version_id is None:
        return [i for i in items if getattr(i, "database_version_id", None) is None]
    current_items = [
        i for i in items if getattr(i, "database_version_id", None) == current_version_id
    ]
    if current_items:
        return current_items
    return [i for i in items if getattr(i, "database_version_id", None) is None]


def get_station_equipment_group_name_map(station_ids):
    """
    Возвращает dict[(station_id, equipment_group_type_id)] -> EquipmentGroup (fuel)
    для отображения EquipmentGroup.name вместо EquipmentGroupType.name.
    """
    if not station_ids:
        return {}
    current_version_id = get_current_db_version_id()
    links = (
        EquipmentGroupSetStation.query.filter(
            EquipmentGroupSetStation.station_id.in_(station_ids)
        )
        .options(
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group),
        )
        .all()
    )
    station_links = _filter_by_version_with_fallback(links, current_version_id)
    result = {}
    for link in station_links:
        group_links = [
            gl
            for gl in (link.equipment_group_links_v2 or [])
            if gl.equipment_group and _is_current_version(gl.equipment_group, current_version_id)
        ]
        if not group_links and current_version_id is not None:
            group_links = [
                gl
                for gl in (link.equipment_group_links_v2 or [])
                if gl.equipment_group and gl.equipment_group.database_version_id is None
            ]
        if group_links:
            key = (link.station_id, link.equipment_group_type_id)
            result[key] = group_links[0].equipment_group
    return result


def _machine_number_sort_key(machine) -> tuple:
    value = (machine.machine_number or "").strip()
    if not value:
        return (1, "", "")
    match = re.search(r"\d+", value)
    if match:
        return (0, int(match.group(0)), value)
    return (1, value, value)


def _equipment_group_sort_key(group: EquipmentGroup | None) -> tuple:
    if group is None:
        return (1, "", 0)
    name = (group.name or group.name_ext or "").strip().lower()
    return (0, name, group.id or 0)


def _min_display_order_from_links(links) -> int | None:
    """Минимальный non-null display_order с типов групп в links (см. refdata /equipment_group)."""
    if not links:
        return None
    min_order = None
    for li in links:
        gt = (li or {}).get("equipment_group_type")
        if gt is None:
            continue
        do = getattr(gt, "display_order", None)
        if do is not None:
            if min_order is None or do < min_order:
                min_order = do
    return min_order


def _group_block_display_sort_key(block) -> tuple:
    """
    Ключ отображения блока на странице stations_equipment_groups.

    Внутри ветки РЭС строки должны идти подряд по электростанции, иначе визуальное
    объединение station-level ячеек работает только в узкой выборке и ломается
    в полном списке.

    Под одной и той же станцией порядок — по display_order (тип группы,
    справочник), без номера — в конец, затем по названию/ id группы.
    """
    entries = block.get("station_entries") or []
    first_station = entries[0].get("station") if entries else None
    first_links = (entries[0].get("links") or []) if entries else []
    type_order = _min_display_order_from_links(first_links)
    # (0, n) < (1, 0) — сначала строки с заданным порядком, затем без номера/типа
    order_key: tuple
    if type_order is not None:
        order_key = (0, type_order)
    else:
        order_key = (1, 0)
    return (
        _station_sort_key(first_station),
        order_key,
        _equipment_group_sort_key(block.get("equipment_group")),
    )


def _equipment_group_type_sort_key(group_type) -> tuple:
    if group_type is None:
        return (1, 10**9, "")
    display_order = (
        group_type.display_order
        if getattr(group_type, "display_order", None) is not None
        else 10**9
    )
    name = (group_type.name or "").strip().lower()
    return (0, display_order, name)


def _machine_belongs_to_fuel_equipment_group(
    machine,
    equipment_group_id: int | None,
    equipment_group_type_id: int | None,
) -> bool:
    """
    Новые данные используют явную привязку MachineFuelParam.equipment_group_id.
    Для legacy-данных без этой привязки сохраняем старый fallback по station+type.
    """
    if machine is None or equipment_group_type_id is None:
        return False
    if getattr(machine, "id_equipment_group", None) != equipment_group_type_id:
        return False
    if equipment_group_id is None:
        return True

    machine_fuel_param = getattr(machine, "machine_fuel_param", None)
    if machine_fuel_param is None:
        return True

    bound_equipment_group_id = getattr(machine_fuel_param, "equipment_group_id", None)
    return bound_equipment_group_id is None or bound_equipment_group_id == equipment_group_id


def build_station_equipment_groups_v2(stations, filters=None, start_year=None, end_year=None):
    """
    Builds v2 equipment-group tree per station.

    Список групп оборудования формируется по модели EquipmentGroup с учетом
    применяемых фильтров (если filters передан).

    Result: dict[station_id] = {"groups": [..], "total_rows": int}
    Each group: {"equipment_group": EquipmentGroup|None, "links": [...], "rowspan": int}
    Each link: {"link": EquipmentGroupSetStation|None, "equipment_group_type": obj|None,
                "machines": list, "rowspan": int}
    """
    station_ids = [s.id for s in (stations or []) if getattr(s, "id", None)]
    if not station_ids:
        return {}

    filtered_equipment_group_ids = None
    if filters:
        filtered_equipment_group_ids = get_filtered_equipment_group_ids(
            filters, start_year=start_year, end_year=end_year
        )

    current_version_id = get_current_db_version_id()

    links = (
        EquipmentGroupSetStation.query.filter(
            EquipmentGroupSetStation.station_id.in_(station_ids)
        )
        .options(
            selectinload(EquipmentGroupSetStation.equipment_group_type),
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group)
            .selectinload(EquipmentGroup.regional_district),
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group)
            .selectinload(EquipmentGroup.regional_energy_system),
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group)
            .selectinload(EquipmentGroup.territories_energy_external_mapping),
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group)
            .selectinload(EquipmentGroup.department_external_mapping),
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group)
            .selectinload(EquipmentGroup.union_energy_system_external_mapping),
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group)
            .selectinload(EquipmentGroup.economic_region_external_mapping),
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group)
            .selectinload(EquipmentGroup.federal_district_external_mapping),
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group)
            .selectinload(EquipmentGroup.business_unit_external_mapping),
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group)
            .selectinload(EquipmentGroup.gen_company_external_mapping),
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group)
            .selectinload(EquipmentGroup.gen_company_branch_external_mapping),
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group)
            .selectinload(EquipmentGroup.cities_external_mapping),
        )
        .all()
    )

    links_by_station = defaultdict(list)
    links_by_station_raw = defaultdict(list)
    for link in links:
        links_by_station_raw[link.station_id].append(link)

    for station_id, station_links in links_by_station_raw.items():
        station_links = _filter_by_version_with_fallback(station_links, current_version_id)
        for link in station_links:
            group_links = [
                gl
                for gl in (link.equipment_group_links_v2 or [])
                if gl.equipment_group and _is_current_version(gl.equipment_group, current_version_id)
            ]
            if not group_links and current_version_id is not None:
                group_links = [
                    gl
                    for gl in (link.equipment_group_links_v2 or [])
                    if gl.equipment_group and gl.equipment_group.database_version_id is None
                ]
            if not group_links:
                links_by_station[station_id].append(
                    {"equipment_group": None, "link": link}
                )
                continue
            for gl in group_links:
                links_by_station[station_id].append(
                    {"equipment_group": gl.equipment_group, "link": link}
                )

    from app.generation.services.station_services.station_services import _apply_machine_display_names

    result = {}
    for station in stations:
        machines = [
            m
            for m in (station.machines or [])
            if current_version_id is None
            or getattr(m, "database_version_id", None) == current_version_id
        ]
        _apply_machine_display_names(machines)
        machines_by_type = defaultdict(list)
        machines_without_type = []
        for machine in machines:
            if machine.id_equipment_group is None:
                machines_without_type.append(machine)
            else:
                machines_by_type[machine.id_equipment_group].append(machine)

        for group_list in machines_by_type.values():
            group_list.sort(key=_machine_number_sort_key)
        machines_without_type.sort(key=_machine_number_sort_key)

        group_nodes = {}
        type_ids_with_links = set()
        for entry in links_by_station.get(station.id, []):
            link = entry["link"]
            type_id = link.equipment_group_type_id
            group = entry["equipment_group"]
            machine_list = [
                machine
                for machine in machines_by_type.get(type_id, [])
                if _machine_belongs_to_fuel_equipment_group(
                    machine,
                    getattr(group, "id", None),
                    type_id,
                )
            ]
            if filtered_equipment_group_ids is not None and group is not None:
                if group.id not in filtered_equipment_group_ids:
                    continue
            type_ids_with_links.add(type_id)
            group_key = group.id if group else None
            node = group_nodes.setdefault(
                group_key, {"equipment_group": group, "links": []}
            )
            node["links"].append(
                {
                    "link": link,
                    "equipment_group_type": link.equipment_group_type,
                    "machines": machine_list,
                }
            )

        missing_type_ids = [
            type_id for type_id in machines_by_type.keys() if type_id not in type_ids_with_links
        ]
        if missing_type_ids or machines_without_type:
            node = group_nodes.setdefault(None, {"equipment_group": None, "links": []})
            for type_id in missing_type_ids:
                machine_list = machines_by_type.get(type_id, [])
                if not machine_list:
                    continue
                node["links"].append(
                    {
                        "link": None,
                        "equipment_group_type": machine_list[0].equipment_group
                        if machine_list
                        else None,
                        "machines": machine_list,
                    }
                )
            if machines_without_type:
                node["links"].append(
                    {
                        "link": None,
                        "equipment_group_type": None,
                        "machines": machines_without_type,
                    }
                )

        groups_sorted = sorted(
            group_nodes.values(), key=lambda item: _equipment_group_sort_key(item["equipment_group"])
        )
        total_rows = 0
        for group in groups_sorted:
            group["links"].sort(
                key=lambda item: _equipment_group_type_sort_key(item["equipment_group_type"])
            )
            group_rowspan = 0
            for link in group["links"]:
                link_rows = max(1, len(link["machines"]))
                link["rowspan"] = link_rows
                group_rowspan += link_rows
            group["rowspan"] = group_rowspan
            total_rows += group_rowspan

        result[station.id] = {"groups": groups_sorted, "total_rows": total_rows}

    return result


def _station_sort_key(station) -> tuple:
    """Sort key for stations: по столбцу «Станция» (название)."""
    if station is None:
        return (2, "", 0)
    name = (getattr(station, "name") or "").strip().lower()
    raw_id = getattr(station, "id", None)
    if raw_id is None:
        return (2, name, 0)
    return (0, name, raw_id)


def reorganize_by_equipment_group_first(stations, v2_groups_map):
    """
    Reorganizes per-station equipment groups into equipment-group-first structure.

    Иерархия: EquipmentGroup -> Station (через EquipmentGroupSet) -> EquipmentGroupType -> Machines

    Returns: list of blocks, each:
        {
            "equipment_group": EquipmentGroup|None,
            "rowspan": int,
            "station_entries": [
                {
                    "station": Station,
                    "station_rowspan": int,
                    "links": [{"equipment_group_type": obj, "machines": list, "rowspan": int}, ...]
                },
                ...
            ]
        }
    """
    if not stations:
        return []

    # Collect (equipment_group, station, link_item) from all stations
    all_entries = []
    for station in stations:
        groups = (v2_groups_map.get(station.id) or {}).get("groups", [])
        for group in groups:
            group_entity = group.get("equipment_group")
            for link_item in group.get("links", []):
                all_entries.append((group_entity, station, link_item))

    # Sort by equipment_group, then station, then equipment_group_type
    all_entries.sort(key=lambda x: (
        _equipment_group_sort_key(x[0]),
        _station_sort_key(x[1]),
        _equipment_group_type_sort_key(x[2].get("equipment_group_type")),
    ))

    # Group by equipment_group (use id for grouping - None for null group)
    from itertools import groupby

    def _group_key(entry):
        eg = entry[0]
        return eg.id if eg else -1

    blocks = []
    for _eg_id, grp in groupby(all_entries, key=_group_key):
        entries = list(grp)
        eq_group = entries[0][0] if entries else None
        # Group by station within this equipment_group
        station_entries = []
        for station_id, st_iter in groupby(entries, key=lambda x: x[1].id):
            st_list = list(st_iter)
            station = st_list[0][1]
            links_data = []
            station_rowspan = 0
            for _, _, link_item in st_list:
                machines = link_item.get("machines", [])
                rowspan = max(1, len(machines))
                links_data.append({
                    "equipment_group_type": link_item.get("equipment_group_type"),
                    "machines": machines,
                    "rowspan": rowspan,
                })
                station_rowspan += rowspan
            station_entries.append({
                "station": station,
                "station_rowspan": station_rowspan,
                "links": links_data,
            })

        total_rowspan = sum(se["station_rowspan"] for se in station_entries)
        distinct_station_keys = {
            _station_identity_key(se.get("station"))
            for se in station_entries
        }
        has_multiple_eg_set_station = len(distinct_station_keys) > 1
        blocks.append({
            "equipment_group": eq_group,
            "rowspan": total_rowspan,
            "station_entries": station_entries,
            "has_multiple_equipment_group_set_station": has_multiple_eg_set_station,
        })

    return blocks


def build_equipment_group_blocks_aggregation(blocks, regional_energy_system_names=None):
    """
    Строит данные для агрегационных строк «РЭС X, всего» по EquipmentGroup.regional_energy_system_id.
    Блоки группируются по РЭС группы оборудования, а не по ключу иерархии станций.

    :param blocks: список блоков из build_equipment_group_blocks_from_model
    :param regional_energy_system_names: dict[res_id, name] для подписей
    :return: dict с ключами:
        - last_row_index_by_res: dict[res_id, int] — индекс последней строки для каждой РЭС
        - res_aggregations: dict[res_id, {res_name, machine_count}]
        - rows_flat: list для согласования индексов (опционально)
    """
    res_names = regional_energy_system_names or {}
    rows_flat = []
    res_machine_counts = {}

    for block in blocks or []:
        eg = block.get("equipment_group")
        res_id = None
        if eg:
            res = getattr(eg, "regional_energy_system", None)
            res_id = res.id if res else getattr(eg, "regional_energy_system_id", None)
        res_id = res_id if res_id is not None else -1

        for station_entry in block.get("station_entries") or []:
            for link in station_entry.get("links") or []:
                machines = link.get("machines") or []
                for machine in (machines if machines else [None]):
                    rows_flat.append((block, station_entry, link, machine))
                    prev = res_machine_counts.get(res_id, {"res_name": res_names.get(res_id, "—"), "machine_count": 0})
                    res_machine_counts[res_id] = {
                        "res_name": prev["res_name"],
                        "machine_count": prev["machine_count"] + 1,
                    }

    last_row_index_by_res = {}
    for i, (block, _se, _link, _machine) in enumerate(rows_flat):
        eg = block.get("equipment_group")
        res_id = -1
        if eg:
            res = getattr(eg, "regional_energy_system", None)
            res_id = res.id if res else getattr(eg, "regional_energy_system_id", None)
            res_id = res_id if res_id is not None else -1
        last_row_index_by_res[res_id] = i

    for res_id, data in res_machine_counts.items():
        data["res_name"] = res_names.get(res_id, "—") if res_id != -1 else "—"

    return {
        "last_row_index_by_res": last_row_index_by_res,
        "res_aggregations": res_machine_counts,
        "rows_flat": rows_flat,
    }


def build_equipment_group_items_with_aggregation(blocks, regional_energy_system_names=None):
    """
    Строит плоский список элементов (строки данных + агрегационные строки по РЭС)
    для отображения в шаблоне. Группировка по EquipmentGroup.regional_energy_system_id.

    :param blocks: список блоков из build_equipment_group_blocks_from_model
    :param regional_energy_system_names: dict[res_id, name] для подписей
    :return: list of dict с type: "row" | "res_summary"
    """
    agg = build_equipment_group_blocks_aggregation(blocks, regional_energy_system_names)
    last_idx = agg.get("last_row_index_by_res", {})
    res_aggs = agg.get("res_aggregations", {})
    rows_flat = agg.get("rows_flat", [])

    items = []
    for i, (block, station_entry, link, machine) in enumerate(rows_flat):
        items.append({
            "type": "row",
            "block": block,
            "station_entry": station_entry,
            "link": link,
            "machine": machine,
        })
        eg = block.get("equipment_group")
        res_id = -1
        if eg:
            res = getattr(eg, "regional_energy_system", None)
            res_id = res.id if res else getattr(eg, "regional_energy_system_id", None)
            res_id = res_id if res_id is not None else -1
        if last_idx.get(res_id) == i:
            data = res_aggs.get(res_id, {"res_name": "—", "machine_count": 0})
            items.append({
                "type": "res_summary",
                "res_name": data.get("res_name", "—"),
                "machine_count": data.get("machine_count", 0),
            })
    return items


def build_equipment_group_station_blocks(blocks):
    """
    Преобразует блоки EquipmentGroup -> Station -> Type -> Machines
    в структуру Station -> EquipmentGroup -> Type -> Machines.

    Используется для рендера страницы stations_equipment_groups с группировкой
    по EST -> UES -> РЭС, как на странице удельных показателей.
    """
    station_groups = {}

    for block in blocks or []:
        equipment_group = block.get("equipment_group")
        for station_entry in block.get("station_entries") or []:
            station = station_entry.get("station")
            station_key = (
                getattr(station, "id", None),
                (getattr(station, "name", None) or "—").strip().lower(),
            )
            station_bucket = station_groups.setdefault(
                station_key,
                {
                    "station": station,
                    "group_blocks": [],
                },
            )

            links = sorted(
                (station_entry.get("links") or []),
                key=lambda item: _equipment_group_type_sort_key(
                    item.get("equipment_group_type")
                ),
            )
            group_rowspan = station_entry.get("station_rowspan")
            if not group_rowspan:
                group_rowspan = sum(
                    max(1, len((link or {}).get("machines") or []))
                    for link in links
                ) or 1

            station_bucket["group_blocks"].append(
                {
                    "equipment_group": equipment_group,
                    "rowspan": group_rowspan,
                    "links": links,
                    "has_multiple_equipment_group_set_station": block.get(
                        "has_multiple_equipment_group_set_station", False
                    ),
                }
            )

    station_blocks = []
    for bucket in station_groups.values():
        group_blocks = sorted(
            bucket.get("group_blocks") or [],
            key=lambda item: _equipment_group_sort_key(item.get("equipment_group")),
        )
        station_rowspan = sum(
            max(1, item.get("rowspan") or 1) for item in group_blocks
        ) or 1
        station_blocks.append(
            {
                "station": bucket.get("station"),
                "rowspan": station_rowspan,
                "group_blocks": group_blocks,
            }
        )

    station_blocks.sort(key=lambda item: _station_sort_key(item.get("station")))
    return station_blocks


def _station_identity_key(station) -> tuple:
    return (
        getattr(station, "id", None),
        (getattr(station, "name", None) or "—").strip().lower(),
    )


def _normalize_display_merge_text(value) -> str:
    cleaned = _clean_name(value) if value is not None else ""
    normalized = str(cleaned or "").strip().lower()
    return normalized or "—"


def _station_display_merge_key(station) -> str:
    if not station:
        return "—"
    return _normalize_display_merge_text(getattr(station, "name", None) or "—")


def _equipment_group_display_merge_key(group) -> str:
    if not group:
        return "—"
    return _normalize_display_merge_text(
        getattr(group, "name", None) or getattr(group, "name_ext", None) or "—"
    )


def _eg_station_regional_district_consistent(station, equipment_group) -> bool:
    """
    Одна запись EquipmentGroup может быть ошибочно связана с несколькими станциями
    в разных субъектах РФ. Для строки таблицы «группа + станция» показываем связь
    только если субъект электростанции совпадает с субъектом группы (модуль «Топливо»),
    когда оба заданы. Иначе строка дублируется под «чужой» ОЭС с тем же названием электростанции.
    """
    if not station or not equipment_group:
        return True
    st_rd = getattr(station, "id_regional_district", None)
    eg_rd = getattr(equipment_group, "regional_district_id", None)
    if eg_rd is None:
        eg_rd_obj = getattr(equipment_group, "regional_district", None)
        if eg_rd_obj is not None:
            eg_rd = getattr(eg_rd_obj, "id", None)
    if st_rd is None or eg_rd is None:
        return True
    return st_rd == eg_rd


def _normalize_station_name_for_match(value) -> str:
    if not value:
        return ""
    cleaned = _clean_name(value)
    if not cleaned:
        return ""
    return str(cleaned).strip().lower()


def _station_identity_name_for_match(station) -> str:
    if not station:
        return ""
    for attr in ("name", "name_combined", "name_so", "name_archive"):
        normalized = _normalize_station_name_for_match(getattr(station, attr, None))
        if normalized:
            return normalized
    return ""


def _eg_name_has_station_type_suffix_brackets(equipment_group_name: str) -> bool:
    """
    Типовой импорт задаёт name как «<станция> (<тип группы>)».
    Скобки могут быть ASCII или полноширинными (часто после копирования из Excel/Word);
    проверка только на '(' и ')' пропускала такие строки и оставляла ложные связи
    «одна группа — несколько станций».
    """
    if not equipment_group_name:
        return False
    for open_b, close_b in (("(", ")"), ("（", "）")):
        if open_b in equipment_group_name and close_b in equipment_group_name:
            return True
    return False


def _eg_station_name_consistent(
    station,
    equipment_group,
    equipment_group_type_id: int | None = None,
) -> bool:
    """
    Отсекает ложные связи одной EquipmentGroup с несколькими станциями одного региона.

    При штатном импорте name группы формируется как "<станция> (<тип группы>)".
    Если такая группа уже явно названа по одной электростанции, но в выборку попадает
    другая станция, на странице она ошибочно отображается как "две электростанции одной
    группы". Для generic/legacy названий, где это уверенно определить нельзя,
    связь сохраняем.
    """
    if not station or not equipment_group:
        return True

    # После ручного объединения одна группа оборудования может быть намеренно
    # связана с несколькими станциями. В этом сценарии нельзя требовать, чтобы
    # имя каждой электростанции полностью входило в name группы, иначе часть станций
    # скрывается на витрине stations_equipment_groups.
    linked_station_ids = set()
    for link in (getattr(equipment_group, "equipment_group_links_v2", None) or []):
        link_station = getattr(link, "equipment_group_set_station", None)
        link_station_id = getattr(link_station, "station_id", None)
        if link_station_id is not None:
            linked_station_ids.add(link_station_id)
            if len(linked_station_ids) > 1:
                return True

    # Ровно одна станция в связях — связь в БД однозначна; не требуем, чтобы
    # `name` группы оставалось в формате «<имя той же электростанции> (тип)» после
    # ручного переименования (иначе скобки вызывали return False и строка
    # пропадала на stations_equipment_groups).
    if len(linked_station_ids) == 1:
        return True

    # Для котельных и других grouping-only связей без агрегатов
    # показываем группу под явно выбранной «Станцией для группировки»,
    # даже если имя группы не похоже на имя электростанции.
    if equipment_group_type_id is not None:
        current_version_id = get_current_db_version_id()
        station_machines = [
            machine
            for machine in (getattr(station, "machines", None) or [])
            if current_version_id is None
            or getattr(machine, "database_version_id", None) == current_version_id
        ]
        has_bound_machines = any(
            _machine_belongs_to_fuel_equipment_group(
                machine,
                getattr(equipment_group, "id", None),
                equipment_group_type_id,
            )
            for machine in station_machines
        )
        if not has_bound_machines:
            return True

    station_name = _station_identity_name_for_match(station)
    if not station_name:
        return True

    equipment_group_name = _normalize_station_name_for_match(
        getattr(equipment_group, "name", None)
    )
    if equipment_group_name:
        if station_name in equipment_group_name:
            return True
        # Типовой импорт задает station-specific name в формате
        # "<станция> (<тип группы>)"; если имя электростанции не совпало,
        # значит связь, скорее всего, подтянулась от другой электростанции.
        if _eg_name_has_station_type_suffix_brackets(equipment_group_name):
            return False

    equipment_group_name_ext = _normalize_station_name_for_match(
        getattr(equipment_group, "name_ext", None)
    )
    if equipment_group_name_ext and station_name in equipment_group_name_ext:
        return True

    return True


def _normalize_group_block(block):
    station_entries = []
    total_rowspan = 0
    distinct_station_keys = set()

    for station_entry in block.get("station_entries") or []:
        station = station_entry.get("station")
        links = sorted(
            (link for link in (station_entry.get("links") or []) if link),
            key=lambda item: _equipment_group_type_sort_key(
                item.get("equipment_group_type")
            ),
        )
        if not links:
            continue
        station_rowspan = station_entry.get("station_rowspan")
        if not station_rowspan:
            station_rowspan = sum(
                max(1, len((link or {}).get("machines") or []))
                for link in links
            ) or 1

        station_entries.append(
            {
                "station": station,
                "station_rowspan": station_rowspan,
                "links": links,
            }
        )
        total_rowspan += station_rowspan
        distinct_station_keys.add(_station_identity_key(station))

    station_entries.sort(key=lambda item: _station_sort_key(item.get("station")))
    return {
        "equipment_group": block.get("equipment_group"),
        "rowspan": total_rowspan or 1,
        "station_entries": station_entries,
        "has_multiple_equipment_group_set_station": len(distinct_station_keys) > 1,
    }


def _hierarchy_key_from_equipment_group(equipment_group) -> tuple:
    """Иерархический ключ EST -> UES -> RES -> RD для группы оборудования."""
    rd = getattr(equipment_group, "regional_district", None) if equipment_group else None
    res = getattr(equipment_group, "regional_energy_system", None) if equipment_group else None
    if rd and getattr(rd, "regional_energy_systems", None):
        rd_res_list = list(rd.regional_energy_systems)
        rd_res_ids = {r.id for r in rd_res_list}
        if not res or getattr(res, "id", None) not in rd_res_ids:
            # Для standalone-групп после смены субъекта РЭС может остаться пустой
            # или несогласованной. Берем первую РЭС выбранного субъекта, чтобы
            # группа попадала в корректную ветку иерархии, а не в «Не указано».
            res = sorted(rd_res_list, key=lambda item: item.id or 0)[0]
    ues = getattr(res, "union_energy_system", None) if res else None
    est = getattr(ues, "energy_system_type", None) if ues else None
    est_id = est.id if est else -1
    ues_id = ues.id if ues else -1
    res_id = res.id if res else -1
    rd_id = rd.id if rd else -1
    eu_id = rd_id
    return (est_id, ues_id, res_id, rd_id, eu_id)


def _resolve_regional_energy_system_for_hierarchy(station, equipment_group=None):
    """
    РЭС для построения EST/ОЭС/РЭС в таблице групп оборудования.

    Нельзя опираться только на station.regional_energy_system_obj: при ошибочном
    id_regional_energy_system у электростанции строка попадала в чужой регион иерархии,
    при этом столбец «Субъект» оставался верным (из regional_district).

    Приоритет:
    1) РЭС группы оборудования, если она входит в список РЭС субъекта электростанции;
    2) прямой FK электростанции на РЭС, если он согласован с субъектом электростанции;
    3) первая РЭС из M2M субъекта (стабильный порядок по id);
    4) только FK, если у субъекта нет списка РЭС (legacy).
    """
    if not station:
        return None

    res_obj = getattr(station, "regional_energy_system_obj", None)
    rd = getattr(station, "regional_district", None)
    rd_res_list = []
    if rd and getattr(rd, "regional_energy_systems", None):
        rd_res_list = list(rd.regional_energy_systems)
    rd_res_ids = {r.id for r in rd_res_list}

    eg_res_id = getattr(equipment_group, "regional_energy_system_id", None) if equipment_group else None
    if eg_res_id is not None and eg_res_id in rd_res_ids:
        for r in rd_res_list:
            if r.id == eg_res_id:
                return r

    if res_obj is not None and rd_res_list:
        if res_obj.id in rd_res_ids:
            return res_obj
    elif res_obj is not None and not rd_res_list:
        return res_obj

    if rd_res_list:
        return sorted(rd_res_list, key=lambda x: x.id)[0]

    return res_obj


def _hierarchy_key_from_station(station, equipment_group=None) -> tuple | None:
    """
    Иерархический ключ для электростанции.

    Важно для случаев, когда одна EquipmentGroup ошибочно связана с несколькими
    станциями из разных регионов: такие station_entry нужно раскладывать по
    иерархии электростанции, а не по полям самой EquipmentGroup.

    :param equipment_group: используется для согласования РЭС с данными «Топливо»,
        если у электростанции несколько РЭС через субъект или конфликт FK.
    """
    if not station:
        return None

    rd = getattr(station, "regional_district", None)
    res = _resolve_regional_energy_system_for_hierarchy(station, equipment_group)
    ues = getattr(res, "union_energy_system", None) if res else None
    est = getattr(ues, "energy_system_type", None) if ues else None

    est_id = est.id if est else -1
    ues_id = ues.id if ues else -1
    res_id = res.id if res else -1
    rd_id = rd.id if rd else -1
    eu_id = rd_id
    return (est_id, ues_id, res_id, rd_id, eu_id)


def _station_matches_selected_territory_filters(station, filters=None, equipment_group=None) -> bool:
    """
    Для linked-групп территориальные фильтры должны отсеивать и station-level строки,
    иначе при фильтре по субъекту / ФО / РЭС в блоке остаются электростанции из соседних
    территорий той же EquipmentGroup.

    Для standalone-котельных эта проверка не применяется: они фильтруются отдельно
    по полям самой группы оборудования и legacy-mapping'ам.
    """
    if not station:
        return False

    _filters = filters or {}
    rd_ids = _filters.get("regional_district_filter") or []
    fd_ids = _filters.get("federal_district_filter") or []
    res_ids = _filters.get("regional_energy_system_filter") or []
    ues_ids = _filters.get("union_energy_system_filter") or []
    est_ids = _filters.get("energy_system_type_filter") or []

    rd = getattr(station, "regional_district", None)
    rd_id = getattr(station, "id_regional_district", None)
    if rd_ids and rd_id not in rd_ids:
        return False

    fd_id = getattr(rd, "id_federal_district", None) if rd else None
    if fd_ids and fd_id not in fd_ids:
        return False

    res = _resolve_regional_energy_system_for_hierarchy(station, equipment_group)
    res_id = getattr(res, "id", None) if res else None
    if res_ids and res_id not in res_ids:
        return False

    ues = getattr(res, "union_energy_system", None) if res else None
    ues_id = getattr(ues, "id", None) if ues else None
    if ues_ids and ues_id not in ues_ids:
        return False

    est = getattr(ues, "energy_system_type", None) if ues else None
    est_id = getattr(est, "id", None) if est else None
    if est_ids and est_id not in est_ids:
        return False

    return True


def _split_group_block_by_station_hierarchy(block):
    """
    Делит block EquipmentGroup -> station_entries на подблоки по иерархии электростанции.

    Это устраняет ситуацию, когда одна и та же EquipmentGroup уже связана в БД
    с несколькими станциями из разных РЭС/субъектов: без разбиения весь блок
    попадал в раздел региона самой EquipmentGroup.
    """
    normalized = _normalize_group_block(block)
    equipment_group = normalized.get("equipment_group")
    station_entries = normalized.get("station_entries") or []
    if not station_entries:
        return [(_hierarchy_key_from_equipment_group(equipment_group), normalized)]

    entries_by_key = defaultdict(list)
    for station_entry in station_entries:
        station = station_entry.get("station")
        # Станция и группа с одним субъектом РФ: иерархию ЕЭС/ОЭС/РЭС берём из
        # EquipmentGroup (модуль «Топливо»). Иначе при нескольких РЭС у субъекта
        # или при ошибочном id_regional_energy_system у электростанции строка попадала
        # не в ту ветку, хотя столбец «Субъект» был верным.
        st_rd = getattr(station, "id_regional_district", None)
        eg_rd = (
            getattr(equipment_group, "regional_district_id", None)
            if equipment_group
            else None
        )
        if eg_rd is None and equipment_group:
            eg_rd_obj = getattr(equipment_group, "regional_district", None)
            if eg_rd_obj is not None:
                eg_rd = getattr(eg_rd_obj, "id", None)

        if (
            st_rd is not None
            and eg_rd is not None
            and st_rd == eg_rd
        ):
            key = _hierarchy_key_from_equipment_group(equipment_group)
        else:
            key = _hierarchy_key_from_station(station, equipment_group)
            if key is None:
                key = _hierarchy_key_from_equipment_group(equipment_group)
        entries_by_key[key].append(station_entry)

    result = []
    for key, grouped_entries in entries_by_key.items():
        result.append(
            (
                key,
                _normalize_group_block(
                    {
                        "equipment_group": equipment_group,
                        "station_entries": grouped_entries,
                    }
                ),
            )
        )
    return result


def prepare_equipment_group_blocks_for_display(blocks):
    """
    Подготавливает блоки для отображения на странице stations_equipment_groups.

    На странице строки должны строиться по таблице EquipmentGroup, а раздел
    «Модуль Генерация» дополняется связями EquipmentGroupSet ->
    EquipmentGroupSetStation -> Station / EquipmentGroupType / Machine.

    Дополнительной перегруппировки в Station-first нет: блоки остаются в формате
    EquipmentGroup -> Station -> Type -> Machines, но для корректного rowspan
    отображаются в порядке station-first, затем equipment-group.
    """
    prepared_blocks = []

    for raw_block in blocks or []:
        block = _normalize_group_block(raw_block)
        if not (block.get("station_entries") or []):
            continue
        prepared_blocks.append(block)

    prepared_blocks.sort(key=_group_block_display_sort_key)
    _merge_adjacent_group_blocks_for_display(prepared_blocks)
    _merge_adjacent_station_entries_for_display(prepared_blocks)
    return prepared_blocks


def _merge_adjacent_group_blocks_for_display(group_blocks):
    """
    Объединяет ячейки «Группа оборудования» и колонки модуля «Топливо»
    для подряд идущих блоков с одинаковым отображаемым названием группы.

    Блоки остаются отдельными на уровне данных, но в HTML рендерятся как одна
    визуальная группа с rowspan на сервере, без post-processing в браузере.
    """
    for block in group_blocks or []:
        block["show_merged_group_cells"] = True
        block["merged_group_rowspan"] = block.get("rowspan") or 1

    def _flush_run(run):
        if len(run) <= 1:
            return
        total_rowspan = sum((block.get("rowspan") or 1) for block in run)
        run[0]["merged_group_rowspan"] = total_rowspan
        for block in run[1:]:
            block["show_merged_group_cells"] = False

    current_run = []
    current_key = None
    for block in group_blocks or []:
        group_key = _equipment_group_display_merge_key(block.get("equipment_group"))
        if current_key is None or group_key == current_key:
            current_run.append(block)
            current_key = group_key
            continue
        _flush_run(current_run)
        current_run = [block]
        current_key = group_key

    _flush_run(current_run)


def _merge_adjacent_station_entries_for_display(group_blocks):
    """
    Объединяет station-level ячейки для подряд идущих station_entry одной и той же
    электростанции по отображаемому названию, если эта станция встречается более чем в
    одной группе оборудования.

    Используется только для отображения на странице: сами блоки остаются
    EquipmentGroup-first, но колонки модуля «Генерация» визуально объединяются
    по электростанции на высоту нескольких групп оборудования.
    """
    ordered_entries = []
    for block in group_blocks or []:
        for station_entry in block.get("station_entries") or []:
            station_entry["show_merged_station_cells"] = True
            station_entry["merged_station_rowspan"] = (
                station_entry.get("station_rowspan") or 1
            )
            ordered_entries.append(station_entry)

    def _flush_run(run):
        if len(run) <= 1:
            return
        total_rowspan = sum((entry.get("station_rowspan") or 1) for entry in run)
        run[0]["merged_station_rowspan"] = total_rowspan
        for entry in run[1:]:
            entry["show_merged_station_cells"] = False

    current_run = []
    current_key = None
    for station_entry in ordered_entries:
        station = station_entry.get("station")
        station_key = _station_display_merge_key(station)
        if current_key is None or station_key == current_key:
            current_run.append(station_entry)
            current_key = station_key
            continue
        _flush_run(current_run)
        current_run = [station_entry]
        current_key = station_key

    _flush_run(current_run)


def build_equipment_group_blocks_hierarchy(
    blocks_by_key,
    energy_system_type_names=None,
    union_energy_system_names=None,
    regional_energy_system_names=None,
    union_energy_system_display_orders=None,
):
    """
    Строит иерархию EST -> UES -> РЭС -> Station -> EquipmentGroup -> Type -> Machines
    по уже подготовленным блокам групп оборудования.
    """
    est_names = dict(energy_system_type_names or {})
    ues_names = dict(union_energy_system_names or {})
    res_names = dict(regional_energy_system_names or {})
    ues_display_orders = dict(union_energy_system_display_orders or {})
    from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
        get_union_energy_system_display_order_map,
        union_energy_system_hierarchy_sort_key,
    )
    if not ues_display_orders:
        ues_display_orders = get_union_energy_system_display_order_map()
    est_names[-1] = est_names.get(-1) or "Не указано"
    ues_names[-1] = ues_names.get(-1) or "Не указано"
    res_names[-1] = res_names.get(-1) or "Не указано"

    hierarchy = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for key, blocks in (blocks_by_key or {}).items():
        est_id, ues_id, res_id, _rd_id, _eu_id = key
        hierarchy[est_id][ues_id][res_id].extend(blocks or [])

    def _name_sort_key(entity_id, names_map):
        return (
            1 if entity_id == -1 else 0,
            (names_map.get(entity_id) or "").strip().lower(),
            entity_id,
        )

    def _ues_sort_key(entity_id):
        return union_energy_system_hierarchy_sort_key(
            entity_id, ues_names, ues_display_orders
        )

    hierarchy_flat = []
    for est_id in sorted(hierarchy.keys(), key=lambda item: _name_sort_key(item, est_names)):
        ues_list = []
        for ues_id in sorted(
            hierarchy[est_id].keys(),
            key=_ues_sort_key,
        ):
            res_list = []
            for res_id in sorted(
                hierarchy[est_id][ues_id].keys(),
                key=lambda item: _name_sort_key(item, res_names),
            ):
                res_blocks = hierarchy[est_id][ues_id][res_id]
                display_blocks = prepare_equipment_group_blocks_for_display(
                    res_blocks or []
                )
                res_list.append(
                    {
                        "res_id": res_id,
                        "res_name": res_names.get(res_id, "—"),
                        "equipment_group_blocks": display_blocks,
                    }
                )
            ues_list.append(
                {
                    "ues_id": ues_id,
                    "ues_name": ues_names.get(ues_id, "—"),
                    "res_list": res_list,
                }
            )
        hierarchy_flat.append(
            {
                "est_id": est_id,
                "est_name": est_names.get(est_id, "—"),
                "ues_list": ues_list,
            }
        )

    return hierarchy_flat


def build_equipment_group_hierarchy_eg_first(
    filters=None,
    start_year=None,
    end_year=None,
    energy_system_type_names=None,
    union_energy_system_names=None,
    regional_energy_system_names=None,
    page=1,
    per_page=None,
):
    """
    EquipmentGroup-first: строит иерархию EST -> UES -> РЭС из групп оборудования.
    Фильтры применяются к EquipmentGroup, затем подтягиваются электростанции и агрегаты.

    Возвращает:
      - иерархию для текущей страницы;
      - общее число групп по фильтру;
      - число страниц;
      - фактическую текущую страницу.
    """
    version_id = get_current_db_version_id()
    standalone_ids = get_standalone_equipment_group_ids(version_id)
    filtered_eg_ids = get_filtered_equipment_group_ids_all(
        filters,
        version_id=version_id,
        strict_version=False,
        standalone_ids_precalc=standalone_ids,
    )
    if not filtered_eg_ids:
        return [], 0, 1, 1

    linked_ids = filtered_eg_ids - standalone_ids
    filtered_standalone_ids = filtered_eg_ids & standalone_ids

    blocks = []
    if linked_ids:
        blocks.extend(
            build_equipment_group_blocks_from_eg_ids(
                linked_ids,
                filters=filters,
                start_year=start_year,
                end_year=end_year,
            )
        )
    if filtered_standalone_ids:
        blocks.extend(
            get_standalone_equipment_group_blocks(
                version_id, only_ids=filtered_standalone_ids
            )
        )

    # Раскладываем блоки по иерархии электростанции, а не только по полям EquipmentGroup.
    # Это важно для ошибочно "склеенных" групп, связанных со станциями из разных регионов.
    blocks_by_key = defaultdict(list)
    for block in blocks:
        for key, split_block in _split_group_block_by_station_hierarchy(block):
            blocks_by_key[key].append(split_block)

    hierarchy = build_equipment_group_blocks_hierarchy(
        dict(blocks_by_key),
        energy_system_type_names=energy_system_type_names,
        union_energy_system_names=union_energy_system_names,
        regional_energy_system_names=regional_energy_system_names,
    )
    paged_hierarchy, total_count, total_pages, current_page = _paginate_equipment_group_hierarchy(
        hierarchy,
        page=page,
        per_page=per_page,
    )
    return paged_hierarchy, total_count, total_pages, current_page


def build_equipment_group_blocks_from_eg_ids(
    equipment_group_ids,
    filters=None,
    start_year=None,
    end_year=None,
):
    """
    EquipmentGroup-first: строит блоки по списку ID групп оборудования.
    Подтягивает все электростанции и агрегаты для каждой группы (без фильтра по станциям).

    :param equipment_group_ids: множество ID групп оборудования (EquipmentGroup)
    :return: list of blocks (формат как reorganize_by_equipment_group_first)
    """
    if not equipment_group_ids:
        return []

    from app.generation.models.station.station_model import Station
    from app.refdata.models.territories.regional_district_model import RegionalDistrict

    current_version_id = get_current_db_version_id()

    equipment_groups = (
        EquipmentGroup.query.filter(EquipmentGroup.id.in_(equipment_group_ids))
        .options(
            selectinload(EquipmentGroup.equipment_group_links_v2).selectinload(
                EquipmentGroupSet.equipment_group_set_station
            ).selectinload(EquipmentGroupSetStation.station).options(
                selectinload(Station.machines).selectinload(Machine.machine_fuel_param),
                selectinload(Station.regional_district).selectinload(
                    RegionalDistrict.regional_energy_systems
                ),
                selectinload(Station.regional_energy_system_obj),
            ),
            selectinload(EquipmentGroup.equipment_group_links_v2).selectinload(
                EquipmentGroupSet.equipment_group_set_station
            ).selectinload(EquipmentGroupSetStation.equipment_group_type),
            selectinload(EquipmentGroup.regional_district),
            selectinload(EquipmentGroup.regional_energy_system),
            selectinload(EquipmentGroup.territories_energy_external_mapping),
            selectinload(EquipmentGroup.department_external_mapping),
            selectinload(EquipmentGroup.union_energy_system_external_mapping),
            selectinload(EquipmentGroup.economic_region_external_mapping),
            selectinload(EquipmentGroup.federal_district_external_mapping),
            selectinload(EquipmentGroup.business_unit_external_mapping),
            selectinload(EquipmentGroup.gen_company_external_mapping),
            selectinload(EquipmentGroup.gen_company_branch_external_mapping),
            selectinload(EquipmentGroup.cities_external_mapping),
        )
        .order_by(EquipmentGroup.name, EquipmentGroup.name_ext, EquipmentGroup.id)
        .all()
    )

    all_entries = []
    for eg in equipment_groups:
        for eg_set in (eg.equipment_group_links_v2 or []):
            eg_set_station = eg_set.equipment_group_set_station
            if not eg_set_station:
                continue
            station = eg_set_station.station
            equipment_group_type = eg_set_station.equipment_group_type
            if not station:
                continue
            if not _is_current_version(eg_set_station, current_version_id):
                continue
            if not _is_current_version(eg, current_version_id):
                if current_version_id is not None and eg.database_version_id is not None:
                    continue
            if not _eg_station_regional_district_consistent(station, eg):
                continue
            if not _station_matches_selected_territory_filters(station, filters, eg):
                continue
            if not _eg_station_name_consistent(
                station,
                eg,
                eg_set_station.equipment_group_type_id,
            ):
                continue
            machines = [
                m
                for m in (station.machines or [])
                if (
                    current_version_id is None
                    or getattr(m, "database_version_id", None) == current_version_id
                )
                and _machine_belongs_to_fuel_equipment_group(
                    m,
                    getattr(eg, "id", None),
                    eg_set_station.equipment_group_type_id,
                )
            ]
            machines.sort(key=_machine_number_sort_key)
            all_entries.append(
                (eg, station, {"equipment_group_type": equipment_group_type, "machines": machines})
            )

    all_entries.sort(
        key=lambda x: (
            _equipment_group_sort_key(x[0]),
            _station_sort_key(x[1]),
            _equipment_group_type_sort_key(x[2].get("equipment_group_type")),
        )
    )

    from itertools import groupby

    def _group_key(entry):
        eg = entry[0]
        return eg.id if eg else -1

    blocks = []
    for _eg_id, grp in groupby(all_entries, key=_group_key):
        entries = list(grp)
        eq_group = entries[0][0] if entries else None
        station_entries = []
        for _st_id, st_iter in groupby(entries, key=lambda x: x[1].id):
            st_list = list(st_iter)
            station = st_list[0][1]
            links_data = []
            station_rowspan = 0
            for _, _, link_item in st_list:
                machines = link_item.get("machines", [])
                rowspan = max(1, len(machines))
                links_data.append({
                    "equipment_group_type": link_item.get("equipment_group_type"),
                    "machines": machines,
                    "rowspan": rowspan,
                })
                station_rowspan += rowspan
            if not links_data:
                continue
            station_entries.append({
                "station": station,
                "station_rowspan": station_rowspan,
                "links": links_data,
            })
        if not station_entries:
            continue
        total_rowspan = sum(se["station_rowspan"] for se in station_entries)
        distinct_station_keys = {
            _station_identity_key(se.get("station"))
            for se in station_entries
        }
        has_multiple_eg_set_station = len(distinct_station_keys) > 1
        blocks.append({
            "equipment_group": eq_group,
            "rowspan": total_rowspan,
            "station_entries": station_entries,
            "has_multiple_equipment_group_set_station": has_multiple_eg_set_station,
        })

    return blocks


def build_equipment_group_blocks_from_model(
    equipment_group_ids,
    stations,
    filters=None,
    start_year=None,
    end_year=None,
):
    """
    Строит блоки групп оборудования по модели EquipmentGroup.
    Данные по станциям и агрегатам подтягиваются из EquipmentGroupSet и Station.

    :param equipment_group_ids: множество ID групп оборудования (EquipmentGroup)
    :param stations: список станций (Station) для фильтрации
    :return: list of blocks (формат как reorganize_by_equipment_group_first)
    """
    if not equipment_group_ids or not stations:
        return []

    from app.generation.models.station.station_model import Station

    station_ids = {s.id for s in stations}
    current_version_id = get_current_db_version_id()

    equipment_groups = (
        EquipmentGroup.query.filter(EquipmentGroup.id.in_(equipment_group_ids))
        .options(
            selectinload(EquipmentGroup.equipment_group_links_v2).selectinload(
                EquipmentGroupSet.equipment_group_set_station
            ).selectinload(EquipmentGroupSetStation.station).options(
                selectinload(Station.machines).selectinload(Machine.machine_fuel_param),
                selectinload(Station.regional_district),
                selectinload(Station.regional_energy_system_obj),
            ),
            selectinload(EquipmentGroup.equipment_group_links_v2).selectinload(
                EquipmentGroupSet.equipment_group_set_station
            ).selectinload(EquipmentGroupSetStation.equipment_group_type),
            selectinload(EquipmentGroup.regional_district),
            selectinload(EquipmentGroup.regional_energy_system),
            selectinload(EquipmentGroup.territories_energy_external_mapping),
            selectinload(EquipmentGroup.department_external_mapping),
            selectinload(EquipmentGroup.union_energy_system_external_mapping),
            selectinload(EquipmentGroup.economic_region_external_mapping),
            selectinload(EquipmentGroup.federal_district_external_mapping),
            selectinload(EquipmentGroup.business_unit_external_mapping),
            selectinload(EquipmentGroup.gen_company_external_mapping),
            selectinload(EquipmentGroup.gen_company_branch_external_mapping),
            selectinload(EquipmentGroup.cities_external_mapping),
        )
        .order_by(EquipmentGroup.name, EquipmentGroup.name_ext, EquipmentGroup.id)
        .all()
    )

    all_entries = []
    for eg in equipment_groups:
        for eg_set in (eg.equipment_group_links_v2 or []):
            eg_set_station = eg_set.equipment_group_set_station
            if not eg_set_station or eg_set_station.station_id not in station_ids:
                continue
            station = eg_set_station.station
            equipment_group_type = eg_set_station.equipment_group_type
            if not station:
                continue
            if not _is_current_version(eg_set_station, current_version_id):
                continue
            if not _is_current_version(eg, current_version_id):
                if current_version_id is not None and eg.database_version_id is not None:
                    continue
            if not _eg_station_regional_district_consistent(station, eg):
                continue
            if not _station_matches_selected_territory_filters(station, filters, eg):
                continue
            if not _eg_station_name_consistent(
                station,
                eg,
                eg_set_station.equipment_group_type_id,
            ):
                continue
            machines = [
                m
                for m in (station.machines or [])
                if (
                    current_version_id is None
                    or getattr(m, "database_version_id", None) == current_version_id
                )
                and _machine_belongs_to_fuel_equipment_group(
                    m,
                    getattr(eg, "id", None),
                    eg_set_station.equipment_group_type_id,
                )
            ]
            machines.sort(key=_machine_number_sort_key)
            all_entries.append(
                (eg, station, {"equipment_group_type": equipment_group_type, "machines": machines})
            )

    all_entries.sort(
        key=lambda x: (
            _equipment_group_sort_key(x[0]),
            _station_sort_key(x[1]),
            _equipment_group_type_sort_key(x[2].get("equipment_group_type")),
        )
    )

    from itertools import groupby

    def _group_key(entry):
        eg = entry[0]
        return eg.id if eg else -1

    blocks = []
    for _eg_id, grp in groupby(all_entries, key=_group_key):
        entries = list(grp)
        eq_group = entries[0][0] if entries else None
        station_entries = []
        for _st_id, st_iter in groupby(entries, key=lambda x: x[1].id):
            st_list = list(st_iter)
            station = st_list[0][1]
            links_data = []
            station_rowspan = 0
            for _, _, link_item in st_list:
                machines = link_item.get("machines", [])
                rowspan = max(1, len(machines))
                links_data.append({
                    "equipment_group_type": link_item.get("equipment_group_type"),
                    "machines": machines,
                    "rowspan": rowspan,
                })
                station_rowspan += rowspan
            if not links_data:
                continue
            station_entries.append({
                "station": station,
                "station_rowspan": station_rowspan,
                "links": links_data,
            })
        if not station_entries:
            continue
        total_rowspan = sum(se["station_rowspan"] for se in station_entries)
        distinct_station_keys = {
            _station_identity_key(se.get("station"))
            for se in station_entries
        }
        has_multiple_eg_set_station = len(distinct_station_keys) > 1
        blocks.append({
            "equipment_group": eq_group,
            "rowspan": total_rowspan,
            "station_entries": station_entries,
            "has_multiple_equipment_group_set_station": has_multiple_eg_set_station,
        })

    return blocks


def build_standalone_equipment_group_hierarchy(filters=None, allowed_prefixes=None):
    """
    Возвращает иерархию для standalone-групп (котельные) в формате:
    grouped_stations, blocks_by_key, hierarchy_keys, unmatched_blocks.
    """
    version_id = get_current_db_version_id()
    standalone_ids = get_filtered_standalone_equipment_group_ids(
        filters, version_id=version_id, strict_version=False
    )
    if not standalone_ids:
        return {
            "grouped_stations": {},
            "blocks_by_key": {},
            "hierarchy_keys": set(),
            "unmatched_blocks": [],
        }

    blocks = get_standalone_equipment_group_blocks(version_id, only_ids=standalone_ids)
    if not blocks:
        return {
            "grouped_stations": {},
            "blocks_by_key": {},
            "hierarchy_keys": set(),
            "unmatched_blocks": [],
        }

    from app.refdata.models.territories.regional_district_model import RegionalDistrict
    from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
    from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
    from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType

    def _is_allowed_key(key):
        if not allowed_prefixes:
            return True
        for prefix in allowed_prefixes:
            if not prefix:
                continue
            if key[: len(prefix)] == tuple(prefix):
                return True
        return False

    blocks_by_key = defaultdict(list)
    hierarchy_keys = set()
    for block in blocks:
        eg = block.get("equipment_group")
        if not eg:
            continue
        rd = getattr(eg, "regional_district", None)
        res = getattr(eg, "regional_energy_system", None)
        if not rd or not res:
            continue
        ues = getattr(res, "union_energy_system", None) if res else None
        est = getattr(ues, "energy_system_type", None) if ues else None
        if not ues or not est:
            continue
        est_id = est.id
        ues_id = ues.id
        res_id = res.id
        rd_id = rd.id
        eu_id = rd_id
        key = (est_id, ues_id, res_id, rd_id, eu_id)
        if not _is_allowed_key(key):
            continue
        blocks_by_key[key].append(block)
        hierarchy_keys.add(key)

    grouped_stations = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        )
    )
    for key in hierarchy_keys:
        est_id, ues_id, res_id, rd_id, eu_id = key
        grouped_stations[est_id][ues_id][res_id][rd_id][eu_id] = []

    unmatched = []
    for block in blocks:
        eg = block.get("equipment_group")
        if not eg:
            unmatched.append(block)
            continue
        rd = getattr(eg, "regional_district", None)
        res = getattr(eg, "regional_energy_system", None)
        if not rd or not res:
            unmatched.append(block)
            continue
        ues = getattr(res, "union_energy_system", None) if res else None
        est = getattr(ues, "energy_system_type", None) if ues else None
        if not ues or not est:
            unmatched.append(block)
            continue
        key = (est.id, ues.id, res.id, rd.id, rd.id)
        if not _is_allowed_key(key):
            unmatched.append(block)

    return {
        "grouped_stations": dict(grouped_stations),
        "blocks_by_key": dict(blocks_by_key),
        "hierarchy_keys": hierarchy_keys,
        "unmatched_blocks": unmatched,
    }


def reorganize_by_station_first(stations, v2_groups_map):
    """
    Reorganizes per-station equipment groups into station-first structure.

    Если несколько групп оборудования входят в состав одной электростанции,
    ячейка «Станция» объединяется (rowspan) на все группы оборудования.

    Иерархия: Station -> EquipmentGroup -> EquipmentGroupType -> Machines

    Returns: list of blocks, each:
        {
            "station": Station,
            "station_rowspan": int,  # суммарное число строк для всех групп этой электростанции
            "group_entries": [
                {
                    "equipment_group": EquipmentGroup|None,
                    "rowspan": int,
                    "links": [{"equipment_group_type": obj, "machines": list, "rowspan": int}, ...]
                },
                ...
            ]
        }
    """
    if not stations:
        return []

    # Collect (equipment_group, station, link_item) from all stations
    all_entries = []
    for station in stations:
        groups = (v2_groups_map.get(station.id) or {}).get("groups", [])
        for group in groups:
            group_entity = group.get("equipment_group")
            for link_item in group.get("links", []):
                all_entries.append((group_entity, station, link_item))

    # Sort by station first, then equipment_group, then equipment_group_type
    all_entries.sort(key=lambda x: (
        _station_sort_key(x[1]),
        _equipment_group_sort_key(x[0]),
        _equipment_group_type_sort_key(x[2].get("equipment_group_type")),
    ))

    from itertools import groupby

    def _station_key(entry):
        return entry[1].id if entry[1] else -1

    blocks = []
    for _st_id, st_grp in groupby(all_entries, key=_station_key):
        st_entries = list(st_grp)
        station = st_entries[0][1] if st_entries else None

        # Group by equipment_group within this station
        def _eg_key(entry):
            eg = entry[0]
            return eg.id if eg else -1

        group_entries = []
        for _eg_id, eg_grp in groupby(st_entries, key=_eg_key):
            eg_list = list(eg_grp)
            eq_group = eg_list[0][0] if eg_list else None
            links_data = []
            group_rowspan = 0
            for _, _, link_item in eg_list:
                machines = link_item.get("machines", [])
                rowspan = max(1, len(machines))
                links_data.append({
                    "equipment_group_type": link_item.get("equipment_group_type"),
                    "machines": machines,
                    "rowspan": rowspan,
                })
                group_rowspan += rowspan
            group_entries.append({
                "equipment_group": eq_group,
                "rowspan": group_rowspan,
                "links": links_data,
            })

        station_rowspan = sum(ge["rowspan"] for ge in group_entries)
        blocks.append({
            "station": station,
            "station_rowspan": station_rowspan,
            "group_entries": group_entries,
        })

    return blocks

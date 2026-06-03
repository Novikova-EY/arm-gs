# -*- coding: utf-8 -*-
"""Сервис фильтрации перспективных площадок ГЭС по ОЭС, РЭС, ФО, субъекту РФ."""

from sqlalchemy import nullslast, or_

from app.generation.prospective_places.models import StationProspectivePlaceGES, ProspectivePlaceGesTepSource
from app.common.services.get_services.territories.federal_district_get_services import (
    get_fd_to_rd_ids_map,
)
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_ues_to_rd_ids_map,
)
from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
    get_res_to_rd_ids_map,
)
from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
    get_est_to_rd_ids_map,
)
from app.generation.prospective_places.models.ges.prospective_place_type_ges_model import (
    PROSPECTIVE_PLACE_TYPE_GES_CANONICAL_NAMES,
)

# Тип «Перечень дополнительных ГЭС…» — порядок строк только по полю площадки display_order.
_ADDITIONAL_GES_PLACE_TYPE_NAME = PROSPECTIVE_PLACE_TYPE_GES_CANONICAL_NAMES[1]


def extract_prospective_places_filters(args):
    """Извлекает параметры фильтров из request.args."""
    def _parse_list(name):
        """Возвращает список значений; '' означает «не указано»."""
        raw = args.getlist(name)
        return [str(x) if x == "" else str(x).strip() for x in raw]

    return {
        "energy_system_type_filter": args.getlist("energy_system_type_filter", type=int),
        "union_energy_system_filter": args.getlist("union_energy_system_filter", type=int),
        "regional_energy_system_filter": args.getlist("regional_energy_system_filter", type=int),
        "federal_district_filter": args.getlist("federal_district_filter", type=int),
        "regional_district_filter": args.getlist("regional_district_filter", type=int),
        "site_name_filter": _parse_list("site_name_filter"),
        "hydro_turbine_type_filter": _parse_list("hydro_turbine_type_filter"),
        "prospective_place_type_filter": args.getlist("prospective_place_type_filter", type=int),
    }


def _get_prospective_place_type_list():
    """Список типов перспективных площадок ГЭС для фильтра."""
    from app.generation.prospective_places.models.ges.prospective_place_type_ges_model import ProspectivePlaceTypeGES
    types = ProspectivePlaceTypeGES.query.order_by(ProspectivePlaceTypeGES.name).all()
    return [{"id": t.id, "name": t.name} for t in types]


def _get_distinct_site_names():
    """Уникальные наименования площадок для выпадающего фильтра (как в Excel)."""
    from app.extensions import db
    rows = (
        db.session.query(StationProspectivePlaceGES.site_name)
        .distinct()
        .order_by(StationProspectivePlaceGES.site_name)
        .all()
    )
    return [r[0] or "" for r in rows]


def _get_distinct_hydro_turbine_types():
    """Уникальные типы гидротурбин (перечень ТЭП) для выпадающего фильтра."""
    from app.extensions import db
    rows = (
        db.session.query(ProspectivePlaceGesTepSource.hydro_turbine_type)
        .distinct()
        .order_by(ProspectivePlaceGesTepSource.hydro_turbine_type)
        .all()
    )
    return [r[0] or "" for r in rows]


def _get_union_energy_systems_in_table():
    """ОЭС, которые реально есть в таблице перспективных площадок."""
    from app.extensions import db
    from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
    from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem

    subq = (
        db.session.query(RegionalEnergySystem.id_union_energy_system)
        .join(StationProspectivePlaceGES, StationProspectivePlaceGES.id_regional_energy_system == RegionalEnergySystem.id)
        .filter(RegionalEnergySystem.id_union_energy_system.isnot(None))
        .distinct()
    )
    ues_rows = (
        db.session.query(UnionEnergySystem.id, UnionEnergySystem.name)
        .filter(UnionEnergySystem.id.in_(subq))
        .order_by(UnionEnergySystem.name)
        .all()
    )
    result = [{"id": r[0], "name": r[1]} for r in ues_rows]

    # Добавляем «не указано», если есть площадки без ОЭС
    has_null = (
        db.session.query(StationProspectivePlaceGES.id)
        .outerjoin(RegionalEnergySystem, StationProspectivePlaceGES.id_regional_energy_system == RegionalEnergySystem.id)
        .filter(
            (StationProspectivePlaceGES.id_regional_energy_system.is_(None)) |
            (RegionalEnergySystem.id_union_energy_system.is_(None))
        )
        .limit(1)
        .first()
    )
    if has_null:
        result.insert(0, {"id": 0, "name": "не указано"})
    return result


def _get_regional_districts_in_table():
    """Субъекты РФ, которые реально есть в таблице перспективных площадок."""
    from app.extensions import db
    from app.refdata.models.territories.regional_district_model import RegionalDistrict

    subq = (
        db.session.query(StationProspectivePlaceGES.id_regional_district)
        .filter(StationProspectivePlaceGES.id_regional_district.isnot(None))
        .distinct()
    )
    rd_rows = (
        db.session.query(RegionalDistrict.id, RegionalDistrict.name_full)
        .filter(RegionalDistrict.id.in_(subq))
        .order_by(RegionalDistrict.name_full)
        .all()
    )
    result = [{"id": r[0], "name": r[1]} for r in rd_rows]

    # Добавляем «не указано», если есть площадки без субъекта
    has_null = (
        db.session.query(StationProspectivePlaceGES.id)
        .filter(StationProspectivePlaceGES.id_regional_district.is_(None))
        .limit(1)
        .first()
    )
    if has_null:
        result.insert(0, {"id": 0, "name": "не указано"})
    return result


def _get_regional_district_ids_from_filters(filters):
    """
    По каскадным фильтрам (ОЭС, РЭС, ФО, субъект) возвращает множество ID субъектов РФ.
    Приоритет: если выбран субъект — только он; иначе объединяем по ОЭС, РЭС, ФО.
    """
    rd_ids = set()

    # Прямой выбор субъектов РФ
    rd_filter = filters.get("regional_district_filter") or []
    if rd_filter:
        rd_ids.update(rd_filter)

    # Иначе собираем из каскада
    if not rd_ids:
        fd_filter = filters.get("federal_district_filter") or []
        res_filter = filters.get("regional_energy_system_filter") or []
        ues_filter = filters.get("union_energy_system_filter") or []
        est_filter = filters.get("energy_system_type_filter") or []

        fd_to_rd = get_fd_to_rd_ids_map()
        res_to_rd = get_res_to_rd_ids_map()
        ues_to_rd = get_ues_to_rd_ids_map()
        est_to_rd = get_est_to_rd_ids_map()

        if fd_filter:
            for fd_id in fd_filter:
                rd_ids.update(fd_to_rd.get(fd_id, []))
        if res_filter:
            for res_id in res_filter:
                rd_ids.update(res_to_rd.get(res_id, []))
        if ues_filter:
            for ues_id in ues_filter:
                if ues_id and ues_id != 0:
                    rd_ids.update(ues_to_rd.get(ues_id, []))
        if est_filter:
            for est_id in est_filter:
                rd_ids.update(est_to_rd.get(est_id, []))

    return rd_ids


def apply_prospective_places_ges_station_order(query):
    """
    Сортировка площадок ГЭС для списка и экспорта:
    сначала UnionEnergySystem.display_order (ОЭС), затем display_order площадки,
    затем site_name. NULL у порядка ОЭС и площадки — в конце соответствующих ключей.
    """
    from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
    from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem

    return (
        query.outerjoin(
            RegionalEnergySystem,
            StationProspectivePlaceGES.id_regional_energy_system == RegionalEnergySystem.id,
        )
        .outerjoin(
            UnionEnergySystem,
            RegionalEnergySystem.id_union_energy_system == UnionEnergySystem.id,
        )
        .order_by(
            nullslast(UnionEnergySystem.display_order.asc()),
            nullslast(StationProspectivePlaceGES.display_order.asc()),
            StationProspectivePlaceGES.site_name.asc(),
        )
    )


def apply_prospective_places_ges_filters(query, filters):
    """
    Применяет фильтры к запросу StationProspectivePlaceGES.
    Фильтрация по субъекту РФ через FK id_regional_district.
    """
    from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem

    # Фильтр по ОЭС (прямая фильтрация по union_energy_system)
    ues_filter = filters.get("union_energy_system_filter") or []
    if ues_filter:
        ues_ids_real = [x for x in ues_filter if x and x != 0]
        has_ues_empty = 0 in ues_filter
        conditions = []
        if ues_ids_real:
            conditions.append(
                StationProspectivePlaceGES.regional_energy_system.has(
                    RegionalEnergySystem.id_union_energy_system.in_(ues_ids_real)
                )
            )
        if has_ues_empty:
            conditions.append(
                or_(
                    StationProspectivePlaceGES.id_regional_energy_system.is_(None),
                    StationProspectivePlaceGES.regional_energy_system.has(
                        RegionalEnergySystem.id_union_energy_system.is_(None)
                    ),
                )
            )
        if conditions:
            query = query.filter(or_(*conditions))

    rd_ids = _get_regional_district_ids_from_filters(filters)

    # Фильтр по субъекту РФ (FK id_regional_district)
    if rd_ids:
        has_rd_empty = 0 in rd_ids
        rd_ids_real = [x for x in rd_ids if x and x != 0]
        conditions = []
        if has_rd_empty:
            conditions.append(StationProspectivePlaceGES.id_regional_district.is_(None))
        if rd_ids_real:
            conditions.append(StationProspectivePlaceGES.id_regional_district.in_(rd_ids_real))
        if conditions:
            query = query.filter(or_(*conditions))

    # Фильтр по наименованию площадки (список значений, как в Excel)
    site_name_filter = filters.get("site_name_filter") or []
    if site_name_filter:
        has_empty = "" in site_name_filter
        non_empty = [v for v in site_name_filter if v]
        conditions = []
        if has_empty:
            conditions.append(
                or_(
                    StationProspectivePlaceGES.site_name.is_(None),
                    StationProspectivePlaceGES.site_name == "",
                )
            )
        if non_empty:
            conditions.append(StationProspectivePlaceGES.site_name.in_(non_empty))
        if conditions:
            query = query.filter(or_(*conditions))

    # Фильтр по типу гидротурбины (в перечне ТЭП)
    hydro_filter = filters.get("hydro_turbine_type_filter") or []
    if hydro_filter:
        has_empty = "" in hydro_filter
        non_empty = [v for v in hydro_filter if v]
        if has_empty and non_empty:
            query = query.filter(
                StationProspectivePlaceGES.ges_tep_source_indicators.any(
                    or_(
                        ProspectivePlaceGesTepSource.hydro_turbine_type.is_(None),
                        ProspectivePlaceGesTepSource.hydro_turbine_type == "",
                        ProspectivePlaceGesTepSource.hydro_turbine_type.in_(non_empty),
                    )
                )
            )
        elif has_empty:
            query = query.filter(
                StationProspectivePlaceGES.ges_tep_source_indicators.any(
                    or_(
                        ProspectivePlaceGesTepSource.hydro_turbine_type.is_(None),
                        ProspectivePlaceGesTepSource.hydro_turbine_type == "",
                    )
                )
            )
        else:
            query = query.filter(
                StationProspectivePlaceGES.ges_tep_source_indicators.any(
                    ProspectivePlaceGesTepSource.hydro_turbine_type.in_(non_empty)
                )
            )

    # Фильтр по типу площадки (в записях перечня ТЭП)
    ppt_filter = filters.get("prospective_place_type_filter") or []
    if ppt_filter:
        query = query.filter(
            StationProspectivePlaceGES.ges_tep_source_indicators.any(
                ProspectivePlaceGesTepSource.id_prospective_place_type_ges.in_(ppt_filter)
            )
        )

    return query


def get_prospective_places_ges_filter_context(filters):
    """Возвращает контекст для шаблона фильтров (списки и маппинги для каскада)."""
    from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
        get_energy_system_type_list_full,
        get_est_to_ues_ids_map,
        get_est_to_res_ids_map,
        get_est_to_rd_ids_map,
        get_est_to_fd_ids_map,
    )
    from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
        get_ues_to_est_id_map,
        get_ues_to_res_ids_map,
        get_ues_to_rd_ids_map,
        get_ues_to_fd_ids_map,
    )
    from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
        get_regional_energy_system_list_full,
        get_res_to_ues_id_map,
        get_res_to_est_id_map,
        get_res_to_rd_ids_map,
        get_res_to_fd_ids_map,
    )
    from app.common.services.get_services.territories.federal_district_get_services import (
        get_federal_district_list_full,
        get_fd_to_rd_ids_map,
        get_fd_to_res_ids_map,
        get_fd_to_ues_ids_map,
        get_fd_to_est_ids_map,
    )
    from app.common.services.get_services.territories.regional_district_get_services import (
        get_rd_to_fd_id_map,
        get_rd_to_res_ids_map,
        get_rd_to_ues_ids_map,
        get_rd_to_est_ids_map,
    )
    from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
        get_ues_to_res_ids_map,
    )

    ues_to_res_mapping = get_ues_to_res_ids_map()
    fd_to_rd_mapping = get_fd_to_rd_ids_map()

    est_objects = get_energy_system_type_list_full()
    energy_system_type_list = [{"id": est.id, "name": est.name} for est in est_objects]

    res_objects = get_regional_energy_system_list_full()
    regional_energy_system_list = [{"id": res.id, "name": res.name} for res in res_objects]

    fd_objects = get_federal_district_list_full()
    federal_district_list = [{"id": fd.id, "name": fd.name} for fd in fd_objects]

    # ОЭС и Субъект РФ — только те значения, которые есть в таблице
    union_energy_system_list = _get_union_energy_systems_in_table()
    regional_district_list = _get_regional_districts_in_table()

    return {
        "energy_system_type_list": energy_system_type_list,
        "union_energy_system_list": union_energy_system_list,
        "regional_energy_system_list": regional_energy_system_list,
        "federal_district_list": federal_district_list,
        "regional_district_list": regional_district_list,
        "energy_system_type_filter": filters.get("energy_system_type_filter") or [],
        "union_energy_system_filter": filters.get("union_energy_system_filter") or [],
        "regional_energy_system_filter": filters.get("regional_energy_system_filter") or [],
        "federal_district_filter": filters.get("federal_district_filter") or [],
        "regional_district_filter": filters.get("regional_district_filter") or [],
        "site_name_filter": filters.get("site_name_filter") or [],
        "hydro_turbine_type_filter": filters.get("hydro_turbine_type_filter") or [],
        "prospective_place_type_filter": filters.get("prospective_place_type_filter") or [],
        "prospective_place_type_list": _get_prospective_place_type_list(),
        "site_name_list": _get_distinct_site_names(),
        "hydro_turbine_type_list": _get_distinct_hydro_turbine_types(),
        "est_to_ues_mapping": get_est_to_ues_ids_map(),
        "est_to_res_mapping": get_est_to_res_ids_map(),
        "est_to_rd_mapping": get_est_to_rd_ids_map(),
        "est_to_fd_mapping": get_est_to_fd_ids_map(),
        "ues_to_est_mapping": get_ues_to_est_id_map(),
        "ues_to_res_mapping": get_ues_to_res_ids_map(),
        "ues_to_rd_mapping": get_ues_to_rd_ids_map(),
        "ues_to_fd_mapping": get_ues_to_fd_ids_map(),
        "res_to_est_mapping": get_res_to_est_id_map(),
        "res_to_ues_mapping_one": get_res_to_ues_id_map(),
        "res_to_rd_mapping": get_res_to_rd_ids_map(),
        "res_to_fd_mapping": get_res_to_fd_ids_map(),
        "rd_to_fd_mapping_one": get_rd_to_fd_id_map(),
        "rd_to_res_mapping": get_rd_to_res_ids_map(),
        "rd_to_ues_mapping": get_rd_to_ues_ids_map(),
        "rd_to_est_mapping": get_rd_to_est_ids_map(),
        "fd_to_rd_mapping": fd_to_rd_mapping,
        "regional_energy_system_mapping": ues_to_res_mapping,
        "regional_district_mapping": fd_to_rd_mapping,
        "fd_to_res_mapping": get_fd_to_res_ids_map(),
        "fd_to_ues_mapping": get_fd_to_ues_ids_map(),
        "fd_to_est_mapping": get_fd_to_est_ids_map(),
    }


def _ges_station_sort_key_by_display_order(s) -> tuple:
    """Порядок площадки: display_order (NULLS LAST), затем site_name."""
    st_od = s.display_order
    name = (s.site_name or "") or ""
    return (
        st_od is None,
        st_od if st_od is not None else 0,
        name.lower(),
    )


def _ges_station_sort_key_ues_then_display_order(s) -> tuple:
    """Порядок площадки: ОЭС display_order, затем display_order площадки, затем site_name."""
    ues_od = None
    if s.regional_energy_system and s.regional_energy_system.union_energy_system:
        ues_od = s.regional_energy_system.union_energy_system.display_order
    st_od = s.display_order
    name = (s.site_name or "") or ""
    return (
        ues_od is None,
        ues_od if ues_od is not None else 0,
        st_od is None,
        st_od if st_od is not None else 0,
        name.lower(),
    )


def _ges_place_type_group_label(tid, sts) -> str:
    if tid is None:
        return "Тип площадки не указан"
    if sts and sts[0].prospective_place_type_ges:
        return sts[0].prospective_place_type_ges.name
    return "Тип площадки не указан"


def _ges_sort_stations_within_place_type_group(tid, sts) -> None:
    """Сортирует площадки внутри одной группы по типу площадки."""
    label = _ges_place_type_group_label(tid, sts)
    if label == _ADDITIONAL_GES_PLACE_TYPE_NAME:
        sts.sort(key=_ges_station_sort_key_by_display_order)
    else:
        sts.sort(key=_ges_station_sort_key_ues_then_display_order)


def build_ges_stations_grouped_by_place_type(stations):
    """Группирует площадки по типу площадки (карточка station).

    Порядок групп: группа «тип не указан» — в начале; с указанным типом — по
    минимальному display_order ОЭС в группе, затем по названию типа.
    Внутри группы «Перечень дополнительных ГЭС…»: только display_order площадки
    (как на карточке /ges/<id>/), затем site_name.
    В остальных группах: UnionEnergySystem.display_order, затем display_order
    площадки, затем site_name.
    """
    from collections import defaultdict

    if not stations:
        return []

    def ues_display_order(s):
        if s.regional_energy_system and s.regional_energy_system.union_energy_system:
            return s.regional_energy_system.union_energy_system.display_order
        return None

    by_type = defaultdict(list)
    for s in stations:
        by_type[s.id_prospective_place_type_ges].append(s)

    for tid in by_type:
        _ges_sort_stations_within_place_type_group(tid, by_type[tid])

    def group_sort_key(tid):
        sts = by_type[tid]
        min_od = None
        for s in sts:
            od = ues_display_order(s)
            if od is not None:
                if min_od is None or od < min_od:
                    min_od = od
        if tid is None:
            tlabel = ""
        elif sts and sts[0].prospective_place_type_ges:
            tlabel = (sts[0].prospective_place_type_ges.name or "").lower()
        else:
            tlabel = ""
        return (
            1 if tid is not None else 0,
            min_od is None,
            min_od if min_od is not None else 0,
            tlabel,
        )

    sorted_ids = sorted(by_type.keys(), key=group_sort_key)

    out = []
    for tid in sorted_ids:
        sts = by_type[tid]
        out.append(
            {
                "type_id": tid,
                "type_label": _ges_place_type_group_label(tid, sts),
                "stations": sts,
            }
        )
    return out

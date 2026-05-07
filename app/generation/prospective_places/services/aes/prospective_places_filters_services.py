# -*- coding: utf-8 -*-
"""Сервис фильтрации перспективных площадок АЭС по ОЭС, РЭС, ФО, субъекту РФ."""

from sqlalchemy import nullslast, or_

from app.generation.prospective_places.models import StationProspectivePlaceAES, MachineProspectivePlaceAES
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
        "unit_type_filter": _parse_list("unit_type_filter"),
        "possible_implementation_period_filter": _parse_list("possible_implementation_period_filter"),
        "prospective_place_type_filter": args.getlist("prospective_place_type_filter", type=int),
        "selection_factor_filter": _parse_list("selection_factor_filter"),
    }


def _get_prospective_place_type_list():
    """Список типов перспективных площадок для фильтра."""
    from app.generation.prospective_places.models.aes.prospective_place_type_aes_model import ProspectivePlaceTypeAES
    types = ProspectivePlaceTypeAES.query.order_by(ProspectivePlaceTypeAES.name).all()
    return [{"id": t.id, "name": t.name} for t in types]


def _get_distinct_site_names():
    """Уникальные наименования площадок для выпадающего фильтра (как в Excel)."""
    from app.extensions import db
    rows = (
        db.session.query(StationProspectivePlaceAES.site_name)
        .distinct()
        .order_by(StationProspectivePlaceAES.site_name)
        .all()
    )
    return [r[0] or "" for r in rows]


def _get_distinct_unit_types():
    """Уникальные типы энергоблоков для выпадающего фильтра."""
    from app.extensions import db
    rows = (
        db.session.query(MachineProspectivePlaceAES.unit_type)
        .distinct()
        .order_by(MachineProspectivePlaceAES.unit_type)
        .all()
    )
    return [r[0] or "" for r in rows]


def _get_distinct_possible_periods():
    """Уникальные сроки реализации для выпадающего фильтра."""
    from app.extensions import db
    rows = (
        db.session.query(MachineProspectivePlaceAES.possible_implementation_period)
        .distinct()
        .order_by(MachineProspectivePlaceAES.possible_implementation_period)
        .all()
    )
    return [r[0] or "" for r in rows]


def _get_distinct_selection_factors():
    """Уникальные факторы отбора для выпадающего фильтра."""
    from app.extensions import db
    rows = (
        db.session.query(StationProspectivePlaceAES.selection_factor)
        .distinct()
        .order_by(StationProspectivePlaceAES.selection_factor)
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
        .join(StationProspectivePlaceAES, StationProspectivePlaceAES.id_regional_energy_system == RegionalEnergySystem.id)
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
        db.session.query(StationProspectivePlaceAES.id)
        .outerjoin(RegionalEnergySystem, StationProspectivePlaceAES.id_regional_energy_system == RegionalEnergySystem.id)
        .filter(
            (StationProspectivePlaceAES.id_regional_energy_system.is_(None)) |
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
        db.session.query(StationProspectivePlaceAES.id_regional_district)
        .filter(StationProspectivePlaceAES.id_regional_district.isnot(None))
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
        db.session.query(StationProspectivePlaceAES.id)
        .filter(StationProspectivePlaceAES.id_regional_district.is_(None))
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


def apply_prospective_places_aes_station_order(query):
    """
    Сортировка площадок АЭС для списка и экспорта:
    сначала по порядку отображения ОЭС (refdata UnionEnergySystem.display_order),
    затем по алфавиту по наименованию площадки (site_name).
    Площадки без ОЭС / без РЭС — в конце блока по display_order (NULLS LAST).
    """
    from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
    from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem

    return (
        query.outerjoin(
            RegionalEnergySystem,
            StationProspectivePlaceAES.id_regional_energy_system == RegionalEnergySystem.id,
        )
        .outerjoin(
            UnionEnergySystem,
            RegionalEnergySystem.id_union_energy_system == UnionEnergySystem.id,
        )
        .order_by(
            nullslast(UnionEnergySystem.display_order.asc()),
            StationProspectivePlaceAES.site_name.asc(),
        )
    )


def apply_prospective_places_filters(query, filters):
    """
    Применяет фильтры к запросу StationProspectivePlaceAES.
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
                StationProspectivePlaceAES.regional_energy_system.has(
                    RegionalEnergySystem.id_union_energy_system.in_(ues_ids_real)
                )
            )
        if has_ues_empty:
            conditions.append(
                or_(
                    StationProspectivePlaceAES.id_regional_energy_system.is_(None),
                    StationProspectivePlaceAES.regional_energy_system.has(
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
            conditions.append(StationProspectivePlaceAES.id_regional_district.is_(None))
        if rd_ids_real:
            conditions.append(StationProspectivePlaceAES.id_regional_district.in_(rd_ids_real))
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
                    StationProspectivePlaceAES.site_name.is_(None),
                    StationProspectivePlaceAES.site_name == "",
                )
            )
        if non_empty:
            conditions.append(StationProspectivePlaceAES.site_name.in_(non_empty))
        if conditions:
            query = query.filter(or_(*conditions))

    # Фильтр по типу энергоблока (в машинах, список значений)
    unit_type_filter = filters.get("unit_type_filter") or []
    if unit_type_filter:
        has_empty = "" in unit_type_filter
        non_empty = [v for v in unit_type_filter if v]
        if has_empty and non_empty:
            query = query.filter(
                StationProspectivePlaceAES.machine_prospective_places.any(
                    or_(
                        MachineProspectivePlaceAES.unit_type.is_(None),
                        MachineProspectivePlaceAES.unit_type == "",
                        MachineProspectivePlaceAES.unit_type.in_(non_empty),
                    )
                )
            )
        elif has_empty:
            query = query.filter(
                StationProspectivePlaceAES.machine_prospective_places.any(
                    or_(
                        MachineProspectivePlaceAES.unit_type.is_(None),
                        MachineProspectivePlaceAES.unit_type == "",
                    )
                )
            )
        else:
            query = query.filter(
                StationProspectivePlaceAES.machine_prospective_places.any(
                    MachineProspectivePlaceAES.unit_type.in_(non_empty)
                )
            )

    # Фильтр по возможному сроку реализации (в машинах, список значений)
    period_filter = filters.get("possible_implementation_period_filter") or []
    if period_filter:
        has_empty = "" in period_filter
        non_empty = [v for v in period_filter if v]
        if has_empty and non_empty:
            query = query.filter(
                StationProspectivePlaceAES.machine_prospective_places.any(
                    or_(
                        MachineProspectivePlaceAES.possible_implementation_period.is_(None),
                        MachineProspectivePlaceAES.possible_implementation_period == "",
                        MachineProspectivePlaceAES.possible_implementation_period.in_(non_empty),
                    )
                )
            )
        elif has_empty:
            query = query.filter(
                StationProspectivePlaceAES.machine_prospective_places.any(
                    or_(
                        MachineProspectivePlaceAES.possible_implementation_period.is_(None),
                        MachineProspectivePlaceAES.possible_implementation_period == "",
                    )
                )
            )
        else:
            query = query.filter(
                StationProspectivePlaceAES.machine_prospective_places.any(
                    MachineProspectivePlaceAES.possible_implementation_period.in_(non_empty)
                )
            )

    # Фильтр по типу площадки (в машинах)
    ppt_filter = filters.get("prospective_place_type_filter") or []
    if ppt_filter:
        query = query.filter(
            StationProspectivePlaceAES.machine_prospective_places.any(
                MachineProspectivePlaceAES.id_prospective_place_type.in_(ppt_filter)
            )
        )

    # Фильтр по фактору отбора (на электростанции, список значений)
    selection_factor_filter = filters.get("selection_factor_filter") or []
    if selection_factor_filter:
        has_empty = "" in selection_factor_filter
        non_empty = [v for v in selection_factor_filter if v]
        conditions = []
        if has_empty:
            conditions.append(
                or_(
                    StationProspectivePlaceAES.selection_factor.is_(None),
                    StationProspectivePlaceAES.selection_factor == "",
                )
            )
        if non_empty:
            conditions.append(StationProspectivePlaceAES.selection_factor.in_(non_empty))
        if conditions:
            query = query.filter(or_(*conditions))

    return query


def get_prospective_places_filter_context(filters):
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
        "unit_type_filter": filters.get("unit_type_filter") or [],
        "possible_implementation_period_filter": filters.get("possible_implementation_period_filter") or [],
        "prospective_place_type_filter": filters.get("prospective_place_type_filter") or [],
        "selection_factor_filter": filters.get("selection_factor_filter") or [],
        "prospective_place_type_list": _get_prospective_place_type_list(),
        "site_name_list": _get_distinct_site_names(),
        "unit_type_list": _get_distinct_unit_types(),
        "possible_implementation_period_list": _get_distinct_possible_periods(),
        "selection_factor_list": _get_distinct_selection_factors(),
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

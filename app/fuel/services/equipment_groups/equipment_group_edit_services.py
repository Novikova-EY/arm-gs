# -*- coding: utf-8 -*-
"""Сервис редактирования групп оборудования (EquipmentGroup)."""

from app.generation.models.station.station_model import Station
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import (
    EquipmentGroupSetStation,
)
from app.fuel.models.external_mapping.fue_em_territories_energy_model import (
    TerritoriesEnergyExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_department_model import (
    DepartmentExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_union_energy_system_model import (
    UnionEnergySystemExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_economic_region_model import (
    EconomicRegionExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_federal_district_model import (
    FederalDistrictExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_cities_model import CitiesExternalMapping
from app.fuel.models.external_mapping.fue_em_business_unit_model import (
    BusinessUnitExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_gen_company_model import (
    GenCompanyExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_gen_company_branch_model import (
    GenCompanyBranchExternalMapping,
)
from sqlalchemy import and_
from sqlalchemy.orm import joinedload

from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
    EquipmentGroupType,
)
from app.generation.models.machine.machine_model import Machine
from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
from app.common.services.database_version_filter import filter_by_explicit_db_version
from app.common.services.refdata_fk_resolve import (
    coerce_regional_district_id_for_db_version,
    coerce_regional_energy_system_id_for_db_version,
    resolve_regional_district_id_for_db_version,
    resolve_regional_energy_system_id_for_db_version,
)


def _effective_group_database_version_id(group) -> int | None:
    """
    Версия БД для справочника типов групп и смены типа в связях:
    явная у EquipmentGroup или текущая из сессии (если у группы legacy NULL).
    """
    from app.common.services.database_version_filter import get_current_db_version_id

    if group is None:
        return get_current_db_version_id()
    gv = getattr(group, "database_version_id", None)
    if gv is not None:
        return gv
    return get_current_db_version_id()


def _load_composite_member_groups(group: EquipmentGroup) -> list[dict]:
    """
    Дочерние группы оборудования составной станции (MAIN = parent.NUMB)
    для блока «Группы оборудования, входящие в эту группу» при COMP=1.
    """
    from app.fuel.services.equipment_groups.composite_station_semantics import (
        _as_int,
    )

    if group is None or _as_int(getattr(group, "comp", None)) != 1:
        return []
    parent_numb = _as_int(getattr(group, "numb", None))
    if parent_numb is None:
        return []

    effective_vid = _effective_group_database_version_id(group)
    child_q = EquipmentGroup.query.filter(EquipmentGroup.main == parent_numb)
    if effective_vid is not None:
        # Сначала строки текущей версии; если пусто — legacy NULL (как у связей SetStation).
        versioned = (
            child_q.filter(EquipmentGroup.database_version_id == effective_vid)
            .order_by(
                EquipmentGroup.ordnumb.asc().nullslast(),
                EquipmentGroup.numb.asc().nullslast(),
                EquipmentGroup.id.asc(),
            )
            .all()
        )
        if versioned:
            children = versioned
        else:
            children = (
                child_q.filter(EquipmentGroup.database_version_id.is_(None))
                .order_by(
                    EquipmentGroup.ordnumb.asc().nullslast(),
                    EquipmentGroup.numb.asc().nullslast(),
                    EquipmentGroup.id.asc(),
                )
                .all()
            )
    else:
        children = (
            child_q.filter(EquipmentGroup.database_version_id.is_(None))
            .order_by(
                EquipmentGroup.ordnumb.asc().nullslast(),
                EquipmentGroup.numb.asc().nullslast(),
                EquipmentGroup.id.asc(),
            )
            .all()
        )

    if not children:
        return []

    child_ids = [c.id for c in children]
    set_rows = (
        EquipmentGroupSet.query.filter(
            EquipmentGroupSet.equipment_group_id.in_(child_ids)
        )
        .options(
            joinedload(EquipmentGroupSet.equipment_group_set_station).joinedload(
                EquipmentGroupSetStation.equipment_group_type
            )
        )
        .all()
    )
    types_by_eg: dict[int, list[str]] = {}
    for es in set_rows:
        lnk = getattr(es, "equipment_group_set_station", None)
        egt = getattr(lnk, "equipment_group_type", None) if lnk else None
        name = (getattr(egt, "name", None) or "").strip() if egt else ""
        if not name:
            continue
        types_by_eg.setdefault(es.equipment_group_id, [])
        if name not in types_by_eg[es.equipment_group_id]:
            types_by_eg[es.equipment_group_id].append(name)

    machine_counts: dict[int, int] = {cid: 0 for cid in child_ids}
    if child_ids:
        from sqlalchemy import func

        rows = (
            MachineFuelParam.query.filter(
                MachineFuelParam.equipment_group_id.in_(child_ids),
                MachineFuelParam.machine_id.isnot(None),
            )
            .with_entities(
                MachineFuelParam.equipment_group_id,
                func.count(func.distinct(MachineFuelParam.machine_id)),
            )
            .group_by(MachineFuelParam.equipment_group_id)
            .all()
        )
        for eg_id, cnt in rows:
            machine_counts[int(eg_id)] = int(cnt or 0)

    result = []
    for child in children:
        type_names = types_by_eg.get(child.id) or []
        result.append(
            {
                "equipment_group": child,
                "types_display": ", ".join(type_names) if type_names else "—",
                "machines_count": machine_counts.get(child.id, 0),
            }
        )
    return result


def _display_relevant_set_station_links(set_rows, preferred_version_id):
    """
    Связи EquipmentGroupSetStation для карточки группы: по одной на каждую станцию.

    Для станции берётся связь текущей/эффективной версии, иначе legacy NULL,
    иначе любая. Раньше при наличии хотя бы одной «точной» версии остальные
    станции (legacy) пропадали с карточки — сохранение numb снимало их с группы.
    """
    by_station: dict[int, object] = {}
    no_station = []

    def _rank(link) -> int:
        link_vid = getattr(link, "database_version_id", None)
        if preferred_version_id is None:
            return 2 if link_vid is None else 0
        if link_vid == preferred_version_id:
            return 2
        if link_vid is None:
            return 1
        return 0

    for es in set_rows or []:
        lnk = getattr(es, "equipment_group_set_station", None)
        if not lnk:
            continue
        sid = getattr(lnk, "station_id", None)
        if sid is None:
            no_station.append(lnk)
            continue
        sid = int(sid)
        prev = by_station.get(sid)
        if prev is None or _rank(lnk) > _rank(prev):
            by_station[sid] = lnk

    if by_station:
        return list(by_station.values())
    if preferred_version_id is None:
        return [lnk for lnk in no_station if getattr(lnk, "database_version_id", None) is None]
    exact = [
        lnk for lnk in no_station
        if getattr(lnk, "database_version_id", None) == preferred_version_id
    ]
    if exact:
        return exact
    legacy = [
        lnk for lnk in no_station if getattr(lnk, "database_version_id", None) is None
    ]
    return legacy or no_station


def get_equipment_group_edit_context(equipment_group_id):
    """
    Загружает EquipmentGroup и справочники для выпадающих списков.
    Возвращает dict с equipment_group и choices для каждого FK-поля.
    """
    from app.common.services.database_version_filter import get_current_db_version_id
    from app.common.services.version_entity_resolve_services import load_by_id_with_version

    group = load_by_id_with_version(
        EquipmentGroup,
        equipment_group_id,
        get_current_db_version_id(),
    )
    if not group:
        return None
    equipment_group_id = group.id

    # При первом открытии формы для части групп regional_district_id / regional_energy_system_id
    # могут еще не быть сохранены в БД (они вычисляются по связям или по obl).
    # В таком случае заполним их на лету, чтобы выпадающие списки сразу показывали корректные значения.
    if group.regional_district_id is None and group.regional_energy_system_id is None:
        # Метод использует связи EquipmentGroupSet/Station и mapping по obl,
        # изменяет только текущий объект в сессии, без коммита.
        group._populate_regional_ids()

    group_version_id = getattr(group, "database_version_id", None)
    crd = coerce_regional_district_id_for_db_version(
        group.regional_district_id, group_version_id
    )
    crs = coerce_regional_energy_system_id_for_db_version(
        group.regional_energy_system_id, group_version_id
    )
    if crd != group.regional_district_id:
        group.regional_district_id = crd
    if crs != group.regional_energy_system_id:
        group.regional_energy_system_id = crs

    from app.extensions import db

    with db.session.no_autoflush:
        return _build_equipment_group_edit_context_after_coerce(group, group_version_id)


def _station_id_from_group_set_rows(set_rows, group_version_id) -> int | None:
    """
    Станция(и), с которыми группа связана через EquipmentGroupSet → EquipmentGroupSetStation.
    При нескольких связях — первая по порядку обхода (для логики сохранения).
    """
    ids = _station_ids_from_group_set_rows(set_rows, group_version_id)
    return ids[0] if ids else None


def _station_ids_from_group_set_rows(set_rows, group_version_id) -> list[int]:
    """Все station_id группы в выбранной версии БД, по имени станции."""
    return [
        item["id"]
        for item in _station_bindings_from_set_station_links(
            _display_relevant_set_station_links(set_rows, group_version_id)
        )
    ]


def _station_bindings_from_set_station_links(links) -> list[dict]:
    """Уникальные станции из связей группы: [{id, name}, ...], по имени."""
    by_id: dict[int, dict] = {}
    for lnk in links or []:
        sid = getattr(lnk, "station_id", None)
        if sid is None or sid in by_id:
            continue
        st = getattr(lnk, "station", None)
        name = "—"
        if st is not None:
            name = ((getattr(st, "name", None) or "—").strip() or "—")
        by_id[int(sid)] = {"id": int(sid), "name": name}
    return sorted(
        by_id.values(),
        key=lambda item: ((item["name"] or "").lower(), item["id"]),
    )


def _build_equipment_group_edit_context_after_coerce(group, group_version_id):
    # Для групп с legacy NULL database_version_id связи EquipmentGroupSetStation
    # обычно хранят явную версию — совпадаем с сессией/эффективной версией (как у типов ЕГО).
    effective_vid = _effective_group_database_version_id(group)
    # Справочники для выпадающих списков (external_id -> display_name)
    obl_choices = [
        ("", "—"),
        *[
            (m.external_id, m.external_name or m.external_id)
            for m in TerritoriesEnergyExternalMapping.query.filter(
                TerritoriesEnergyExternalMapping.external_id.isnot(None)
            )
            .order_by(TerritoriesEnergyExternalMapping.external_name, TerritoriesEnergyExternalMapping.external_id)
            .all()
        ],
    ]
    dep_choices = [
        ("", "—"),
        *[
            (m.external_id, m.external_name or m.external_id)
            for m in DepartmentExternalMapping.query.order_by(
                DepartmentExternalMapping.external_name
            ).all()
        ],
    ]
    oes_choices = [
        ("", "—"),
        *[
            (m.external_id, (m.external_nameoes or m.external_name or m.external_id))
            for m in UnionEnergySystemExternalMapping.query.filter(
                UnionEnergySystemExternalMapping.external_id.isnot(None)
            )
            .order_by(UnionEnergySystemExternalMapping.external_nameoes)
            .all()
        ],
    ]
    er_choices = [
        ("", "—"),
        *[
            (m.external_id, m.external_name or m.external_id)
            for m in EconomicRegionExternalMapping.query.filter(
                EconomicRegionExternalMapping.external_id.isnot(None)
            )
            .order_by(EconomicRegionExternalMapping.external_name)
            .all()
        ],
    ]
    fo_choices = [
        ("", "—"),
        *[
            (m.external_id, m.external_name or m.external_id)
            for m in FederalDistrictExternalMapping.query.filter(
                FederalDistrictExternalMapping.external_id.isnot(None)
            )
            .order_by(FederalDistrictExternalMapping.external_name)
            .all()
        ],
    ]
    # codegor -> CitiesExternalMapping.code (Integer), EquipmentGroup.codegor - string
    cities_list = CitiesExternalMapping.query.order_by(CitiesExternalMapping.name).all()
    codegor_choices = [
        ("", "—"),
        *[(str(m.code), (m.name or str(m.code))) for m in cities_list],
    ]
    be_choices = [
        ("", "—"),
        *[
            (m.external_id, m.external_name or m.external_id)
            for m in BusinessUnitExternalMapping.query.order_by(
                BusinessUnitExternalMapping.external_name
            ).all()
        ],
    ]
    gk_choices = [
        ("", "—"),
        *[
            (m.external_id, m.external_name or m.external_id)
            for m in GenCompanyExternalMapping.query.filter(
                GenCompanyExternalMapping.external_id.isnot(None)
            )
            .order_by(GenCompanyExternalMapping.external_name)
            .all()
        ],
    ]
    gkf_choices = [
        ("", "—"),
        *[
            (m.external_id, m.external_name or m.external_id)
            for m in GenCompanyBranchExternalMapping.query.filter(
                GenCompanyBranchExternalMapping.external_id.isnot(None)
            )
            .order_by(GenCompanyBranchExternalMapping.external_name)
            .all()
        ],
    ]

    # Как на странице stations_equipment_groups
    d_choices = [("", "—"), ("1", "да")]
    r_choices = [("", "—"), ("1", "да")]
    forem_choices = [("", "—"), ("1", "да")]
    vedomstvo_choices = [
        ("", "—"),
        ("1", "станция отрасли"),
        ("2", "пром. предприятие"),
    ]

    # Субъект РФ и Региональная энергосистема (regional_district_id, regional_energy_system_id)
    rd_query = filter_by_explicit_db_version(
        RegionalDistrict.query, RegionalDistrict, group_version_id
    )
    regional_district_choices = [
        ("", "—"),
        *[(str(r.id), r.name or str(r.id)) for r in rd_query.order_by(RegionalDistrict.name).all()],
    ]
    res_query = filter_by_explicit_db_version(
        RegionalEnergySystem.query, RegionalEnergySystem, group_version_id
    )
    regional_energy_system_choices = [
        ("", "—"),
        *[(str(r.id), r.name or str(r.id)) for r in res_query.order_by(RegionalEnergySystem.name).all()],
    ]
    # Станция для группировки: выпадающий список — все Station текущей версии БД.
    # Подпись для выбранного id: приоритет — Station.name по связке
    # EquipmentGroupSet -> EquipmentGroupSetStation -> Station; иначе — из справочника Station.
    set_rows = (
        EquipmentGroupSet.query.filter_by(equipment_group_id=group.id)
        .options(
            joinedload(EquipmentGroupSet.equipment_group_set_station).joinedload(
                EquipmentGroupSetStation.station
            )
        )
        .all()
    )
    display_links = _display_relevant_set_station_links(set_rows, effective_vid)
    grouping_station_bindings = _station_bindings_from_set_station_links(display_links)
    grouping_station_effective_id = (
        grouping_station_bindings[0]["id"] if grouping_station_bindings else None
    )
    station_q = filter_by_explicit_db_version(
        Station.query, Station, effective_vid
    ).order_by(Station.name, Station.id)
    all_stations = list(station_q.all())
    _station_ids = {s.id for s in all_stations}
    for extra_sid in [b["id"] for b in grouping_station_bindings]:
        if not extra_sid or extra_sid in _station_ids:
            continue
        st_e = (
            filter_by_explicit_db_version(Station.query, Station, effective_vid)
            .filter(Station.id == extra_sid)
            .first()
        )
        if not st_e:
            extra_lnk = (
                filter_by_explicit_db_version(
                    EquipmentGroupSetStation.query,
                    EquipmentGroupSetStation,
                    effective_vid,
                )
                .filter(EquipmentGroupSetStation.station_id == extra_sid)
                .first()
            )
            if extra_lnk and extra_lnk.station:
                st_e = extra_lnk.station
        if not st_e:
            st_e = Station.query.get(extra_sid)
        if st_e and st_e.id not in _station_ids:
            all_stations.append(st_e)
            all_stations.sort(
                key=lambda s: ((s.name or "").lower() if s.name else "", s.id)
            )
            _station_ids.add(st_e.id)
    grouping_station_choices = [
        ("", "не указано"),
        *[(str(s.id), ((s.name or "").strip() or "—")) for s in all_stations],
    ]

    # Отображаемые значения для режима чтения (по choices)
    def _label_for(choices, val):
        """
        Универсальный поиск метки по значению, допускает как строки, так и числа.
        """
        if val is None:
            v = ""
        else:
            v = str(val).strip()

        for cval, clabel in choices:
            # Значения в choices тоже могут быть как строками, так и числами
            if cval is None:
                c = ""
            else:
                c = str(cval).strip()

            if c == v:
                return clabel

        # Если метка не найдена — возвращаем исходное значение или "—"
        return str(val) if val not in (None, "") else "—"

    def _label_for_id(choices, val):
        """Для integer FK (regional_district_id, regional_energy_system_id)."""
        if val is None:
            return "—"
        return _label_for(choices, str(val))

    # Типы групп оборудования (refdata): та же эффективная версия, что и при сохранении
    eg_type_query = filter_by_explicit_db_version(
        EquipmentGroupType.query,
        EquipmentGroupType,
        _effective_group_database_version_id(group),
    )
    equipment_group_type_choices = [
        ("", "—"),
        *[
            (str(t.id), ((t.name or str(t.id)).strip() or "—"))
            for t in eg_type_query.order_by(
                EquipmentGroupType.display_order.asc().nullslast(),
                EquipmentGroupType.name,
                EquipmentGroupType.id,
            ).all()
        ],
    ]
    tids = set()
    for lnk in display_links:
        if lnk.equipment_group_type_id is not None:
            tids.add(lnk.equipment_group_type_id)
    equipment_group_type_selected = str(next(iter(tids))) if len(tids) == 1 else ""

    _gstation_display = ", ".join(
        b["name"] for b in grouping_station_bindings if b.get("name")
    ) or None
    choice_displays = {
        "grouping_station_id": (
            _gstation_display
            if _gstation_display is not None
            else (
                "не указано"
                if grouping_station_effective_id is None
                else _label_for_id(
                    grouping_station_choices,
                    grouping_station_effective_id,
                )
            )
        ),
        "regional_district_id": _label_for_id(regional_district_choices, group.regional_district_id),
        "regional_energy_system_id": _label_for_id(regional_energy_system_choices, group.regional_energy_system_id),
        "obl": _label_for(obl_choices, group.obl),
        "dep": _label_for(dep_choices, group.dep),
        "oes": _label_for(oes_choices, group.oes),
        "er": _label_for(er_choices, group.er),
        "fo": _label_for(fo_choices, group.fo),
        "codegor": _label_for(codegor_choices, group.codegor),
        "be": _label_for(be_choices, group.be),
        "gk": _label_for(gk_choices, group.gk),
        "gkf": _label_for(gkf_choices, group.gkf),
        "d": _label_for(d_choices, group.d),
        "r": _label_for(r_choices, group.r),
        "forem": _label_for(forem_choices, group.forem),
        "vedomstvo": _label_for(vedomstvo_choices, group.vedomstvo),
    }

    from app.fuel.services.equipment_groups.composite_station_semantics import (
        is_composite_child_group,
        is_composite_parent_group,
        is_main_empty,
    )

    if is_composite_parent_group(group):
        composite_role = "parent"
        composite_role_label = "Родитель составной станции (COMP=1)"
    elif is_composite_child_group(group):
        composite_role = "child"
        composite_role_label = f"Дочерняя группа оборудования (MAIN={group.main})"
    elif not is_main_empty(getattr(group, "main", None)):
        composite_role = "child"
        composite_role_label = f"Часть станции (MAIN={group.main})"
    else:
        composite_role = "plain"
        composite_role_label = "Обычная станция / группа без разбиения"

    parent_eg_for_main = None
    if is_composite_child_group(group) and group.main is not None:
        parent_q = EquipmentGroup.query.filter(EquipmentGroup.numb == int(group.main))
        if getattr(group, "database_version_id", None) is not None:
            parent_q = parent_q.filter(
                (EquipmentGroup.database_version_id == group.database_version_id)
                | (EquipmentGroup.database_version_id.is_(None))
            )
        parent_eg_for_main = parent_q.order_by(EquipmentGroup.id).first()

    member_equipment_groups = _load_composite_member_groups(group)

    from app.fuel.services.equipment_groups.equipment_group_rebind_services import (
        count_machines_bound_to_equipment_group,
        get_rebind_target_choices_for_group,
    )

    rebind_target_choices = get_rebind_target_choices_for_group(
        group,
        _effective_group_database_version_id(group),
    )
    rebind_bound_machines_count = count_machines_bound_to_equipment_group(
        group.id,
        _effective_group_database_version_id(group),
    )

    return {
        "equipment_group": group,
        "equipment_group_type_choices": equipment_group_type_choices,
        "equipment_group_type_selected": equipment_group_type_selected,
        "grouping_station_effective_id": grouping_station_effective_id,
        "grouping_station_bindings": grouping_station_bindings,
        "grouping_station_choices": grouping_station_choices,
        "regional_district_choices": regional_district_choices,
        "regional_energy_system_choices": regional_energy_system_choices,
        "obl_choices": obl_choices,
        "dep_choices": dep_choices,
        "oes_choices": oes_choices,
        "er_choices": er_choices,
        "fo_choices": fo_choices,
        "codegor_choices": codegor_choices,
        "be_choices": be_choices,
        "gk_choices": gk_choices,
        "gkf_choices": gkf_choices,
        "d_choices": d_choices,
        "r_choices": r_choices,
        "forem_choices": forem_choices,
        "vedomstvo_choices": vedomstvo_choices,
        "choice_displays": choice_displays,
        "composite_role": composite_role,
        "composite_role_label": composite_role_label,
        "parent_eg_for_main": parent_eg_for_main,
        "member_equipment_groups": member_equipment_groups,
        "rebind_target_choices": rebind_target_choices,
        "rebind_bound_machines_count": rebind_bound_machines_count,
    }


def _update_machines_id_equipment_group_for_fuel_group(
    equipment_group_id: int,
    station_id: int | None,
    old_type_id: int | None,
    new_type_id: int | None,
    version_id,
) -> None:
    """Обновляет Machine.id_equipment_group у агрегатов, привязанных к этой fuel-группе."""
    if old_type_id == new_type_id or station_id is None:
        return
    from app.extensions import db

    q = (
        db.session.query(Machine)
        .join(
            MachineFuelParam,
            and_(
                MachineFuelParam.machine_id == Machine.id,
                MachineFuelParam.equipment_group_id == equipment_group_id,
            ),
        )
        .filter(Machine.id_station == station_id)
    )
    if old_type_id is None:
        q = q.filter(Machine.id_equipment_group.is_(None))
    else:
        q = q.filter(Machine.id_equipment_group == old_type_id)
    q = filter_by_explicit_db_version(q, Machine, version_id)
    for m in q.all():
        m.id_equipment_group = new_type_id
        db.session.add(m)


def _find_equipment_group_set_station_link(
    station_id: int | None, equipment_group_type_id: int, version_id
) -> EquipmentGroupSetStation | None:
    q = EquipmentGroupSetStation.query.filter(
        EquipmentGroupSetStation.equipment_group_type_id == equipment_group_type_id,
    )
    if station_id is None:
        q = q.filter(EquipmentGroupSetStation.station_id.is_(None))
    else:
        q = q.filter(EquipmentGroupSetStation.station_id == station_id)
    if version_id is None:
        q = q.filter(EquipmentGroupSetStation.database_version_id.is_(None))
    else:
        q = q.filter(EquipmentGroupSetStation.database_version_id == version_id)
    return q.first()


def _count_sets_using_link(set_station_id: int) -> int:
    from app.extensions import db

    return (
        db.session.query(EquipmentGroupSet)
        .filter(EquipmentGroupSet.equipment_group_set_station_id == set_station_id)
        .count()
    )


def _apply_equipment_group_type_change_from_form(
    equipment_group_id: int,
    new_type_id: int | None,
    group_version_id,
) -> str | None:
    """
    Меняет equipment_group_type_id у связей EquipmentGroupSetStation,
    ведущих к данной equipment group, на new_type_id (None — прочерк / без типа).
    При необходимости переносит EquipmentGroupSet на существующую запись
    (station, type, version) и снимает дубликат.

    Синхронизирует Machine.id_equipment_group для агрегатов из этой fuel-группы.
    Возвращает None при успехе или строку с ошибкой.
    """
    from app.extensions import db
    from app.fuel.services.equipment_groups.equipment_group_set_services import (
        _point_group_set_at_link,
        find_or_create_versioned_equipment_group_set_station,
        resolve_station_and_type_for_version,
    )

    if new_type_id is not None:
        tq = filter_by_explicit_db_version(
            EquipmentGroupType.query, EquipmentGroupType, group_version_id
        ).filter(EquipmentGroupType.id == new_type_id)
        if tq.first() is None:
            return "Тип группы оборудования не найден в текущей версии БД."

    set_rows = (
        EquipmentGroupSet.query.filter_by(equipment_group_id=equipment_group_id)
        .order_by(EquipmentGroupSet.id.asc())
        .all()
    )
    if not set_rows:
        return None

    for set_row in set_rows:
        old_link = EquipmentGroupSetStation.query.get(
            set_row.equipment_group_set_station_id
        )
        if not old_link:
            return "Связь станция — тип группы оборудования (EquipmentGroupSetStation) не найдена."
        v_id = (
            group_version_id
            if group_version_id is not None
            else old_link.database_version_id
        )
        resolved_station_id, resolved_type_id = resolve_station_and_type_for_version(
            old_link.station_id, new_type_id, v_id
        )
        if old_link.station_id is not None and resolved_station_id is None:
            return "Станция связи не найдена в версии БД этой группы."
        st_id = (
            resolved_station_id
            if resolved_station_id is not None
            else old_link.station_id
        )
        type_id = resolved_type_id if resolved_type_id is not None else new_type_id
        old_tid = old_link.equipment_group_type_id
        if (
            old_link.station_id == st_id
            and old_tid == type_id
            and old_link.database_version_id == v_id
        ):
            continue

        _update_machines_id_equipment_group_for_fuel_group(
            equipment_group_id, st_id, old_tid, type_id, group_version_id
        )

        target = find_or_create_versioned_equipment_group_set_station(
            st_id, type_id, v_id
        )
        if target is None:
            return "Не удалось создать связь станция — тип группы оборудования."
        if target.id == old_link.id:
            if old_link.equipment_group_type_id != type_id:
                old_link.equipment_group_type_id = type_id
                db.session.add(old_link)
                db.session.flush()
            continue
        _point_group_set_at_link(set_row, target)

    return None


def _apply_grouping_station_on_type_station_links(
    equipment_group_id: int,
    new_station_id: int | None,
    version_id=None,
) -> str | None:
    """
    Записывает «Станция для группировки» в gs_fue_equipment_group_type_stations.station_id
    для всех связей EquipmentGroupSet данной группы. При конфликте уникального ключа
    переносит EquipmentGroupSet на существующую строку (station_id, type, version).

    Станция и тип приводятся к version_id (или к версии самой связи).
    """
    from app.fuel.services.equipment_groups.equipment_group_set_services import (
        _point_group_set_at_link,
        find_or_create_versioned_equipment_group_set_station,
        resolve_station_and_type_for_version,
    )

    set_rows = (
        EquipmentGroupSet.query.filter_by(equipment_group_id=equipment_group_id)
        .order_by(EquipmentGroupSet.id.asc())
        .all()
    )
    if not set_rows:
        return None

    for set_row in set_rows:
        old_link = EquipmentGroupSetStation.query.get(
            set_row.equipment_group_set_station_id
        )
        if not old_link:
            return "Связь станция — тип группы оборудования (EquipmentGroupSetStation) не найдена."
        type_id = old_link.equipment_group_type_id
        v_id = version_id if version_id is not None else old_link.database_version_id
        resolved_station_id, resolved_type_id = resolve_station_and_type_for_version(
            new_station_id, type_id, v_id
        )
        if new_station_id is not None and resolved_station_id is None:
            return (
                "Выбранная станция для группировки не найдена в версии БД этой группы."
            )
        if type_id is not None and resolved_type_id is None:
            return "Тип группы оборудования не найден в версии БД этой группы."
        if resolved_type_id is not None:
            type_id = resolved_type_id
        if resolved_station_id is not None:
            new_station_id = resolved_station_id
        if (
            old_link.station_id == new_station_id
            and old_link.equipment_group_type_id == type_id
            and old_link.database_version_id == v_id
        ):
            continue

        target = find_or_create_versioned_equipment_group_set_station(
            new_station_id, type_id, v_id
        )
        if target is None:
            return "Не удалось создать связь станция — тип группы оборудования."
        if target.id == old_link.id:
            continue

        _point_group_set_at_link(set_row, target)

    return None


def _get_station_id_for_equipment_group(equipment_group_id: int):
    """Возвращает station_id из первой связи группы, или 0 если связей нет."""
    sets = EquipmentGroupSet.query.filter_by(equipment_group_id=equipment_group_id).all()
    for s in sets:
        link = EquipmentGroupSetStation.query.get(s.equipment_group_set_station_id)
        if link:
            return link.station_id
    return 0


def _resolve_grouping_station_id_for_db_version(
    anchor_station_id: int | None,
    version_id,
) -> int | None:
    """
    ID станции для группировки в версии version_id.
    Якорь — id из формы (обычно текущая версия); в других версиях — по external_code.
  """
    if anchor_station_id is None:
        return None
    anchor = Station.query.get(anchor_station_id)
    if not anchor:
        return None
    anchor_vid = getattr(anchor, "database_version_id", None)
    if (anchor_vid is None and version_id is None) or (anchor_vid == version_id):
        return anchor_station_id
    external_code = (getattr(anchor, "external_code", None) or "").strip()
    if external_code:
        q = filter_by_explicit_db_version(
            Station.query.filter(Station.external_code == external_code),
            Station,
            version_id,
        )
        found = q.first()
        if found:
            return found.id
        return None
    station_obj = filter_by_explicit_db_version(
        Station.query,
        Station,
        version_id,
    ).filter(Station.id == anchor_station_id).first()
    return anchor_station_id if station_obj else None


def sync_composite_children_subject_rf_from_parents() -> int:
    """
    Для всех дочерних групп (main>0) проставляет Субъект РФ с родителя.
    Нужен после импорта Excel: дети могут обработаться раньше родителя.
    Возвращает число групп, у которых изменился regional_district_id.
    """
    children = EquipmentGroup.query.filter(
        EquipmentGroup.main.isnot(None),
        EquipmentGroup.main > 0,
    ).all()
    updated = 0
    for child in children:
        old_rd = child.regional_district_id
        if child._apply_regional_ids_from_parent() and child.regional_district_id != old_rd:
            updated += 1
    return updated


def _form_getlist(form_data, key) -> list:
    """Значения ключа из Flask MultiDict или dict (в т.ч. list-значение)."""
    if not form_data:
        return []
    if hasattr(form_data, "getlist"):
        return [v for v in form_data.getlist(key) if v is not None]
    val = form_data.get(key)
    if val is None:
        return []
    if isinstance(val, (list, tuple)):
        return list(val)
    return [val]


def _parse_int_form_id(val) -> int | None:
    if val is None or not str(val).strip():
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def form_has_grouping_station_sync(form_data) -> bool:
    """Форма задаёт полный набор станций (карточка группы / fuelParamsForm)."""
    if not form_data:
        return False
    return (
        "grouping_station_ids_present" in form_data
        or "grouping_station_ids" in form_data
    )


def grouping_station_ids_from_form(form_data, key: str = "grouping_station_ids") -> list[int]:
    """Уникальные id станций из ключа формы (+ устаревший grouping_station_id)."""
    ids: list[int] = []
    seen: set[int] = set()
    values = _form_getlist(form_data, key)
    if key == "grouping_station_ids":
        extra = form_data.get("grouping_station_id") if form_data else None
        if extra is not None:
            values = list(values) + [extra]
    for raw in values:
        parsed = _parse_int_form_id(raw)
        if parsed is None or parsed in seen:
            continue
        seen.add(parsed)
        ids.append(parsed)
    return ids


def _unique_type_id_from_group_sets(equipment_group_id: int, version_id) -> int | None:
    set_rows = EquipmentGroupSet.query.filter_by(
        equipment_group_id=equipment_group_id
    ).all()
    type_ids = {
        lnk.equipment_group_type_id
        for lnk in _display_relevant_set_station_links(set_rows, version_id)
        if getattr(lnk, "equipment_group_type_id", None) is not None
    }
    if len(type_ids) != 1:
        return None
    return next(iter(type_ids))


def _unlink_equipment_group_from_station(
    equipment_group_id: int,
    station_id: int,
    version_id=None,
) -> None:
    """Снимает связи EquipmentGroupSet группы с указанной станцией в версии БД."""
    from app.extensions import db

    query = EquipmentGroupSet.query.join(
        EquipmentGroupSetStation,
        EquipmentGroupSetStation.id == EquipmentGroupSet.equipment_group_set_station_id,
    ).filter(
        EquipmentGroupSet.equipment_group_id == equipment_group_id,
        EquipmentGroupSetStation.station_id == station_id,
    )
    if version_id is None:
        query = query.filter(EquipmentGroupSetStation.database_version_id.is_(None))
    else:
        query = query.filter(EquipmentGroupSetStation.database_version_id == version_id)
    for set_row in query.all():
        old_link_id = set_row.equipment_group_set_station_id
        db.session.delete(set_row)
        db.session.flush()
        if old_link_id and _count_sets_using_link(old_link_id) == 0:
            old_link = db.session.get(EquipmentGroupSetStation, old_link_id)
            if old_link is not None:
                db.session.delete(old_link)
                db.session.flush()


def sync_equipment_group_grouping_stations(
    equipment_group_id: int,
    desired_station_ids: list[int] | None,
    *,
    version_id=None,
    equipment_group_type_id: int | None = None,
    loaded_station_ids: list[int] | None = None,
) -> str | None:
    """
    Приводит набор станций группы к desired_station_ids: добавляет недостающие
    связи. Снимает только те станции, которые были на карточке (loaded) и
    пользователь убрал. Станции, которых не было в форме, не трогает —
    иначе сохранение numb отвязывало ТЭС-3, если её чипа не было на карточке.
    """
    from app.fuel.services.equipment_groups.equipment_group_rebind_services import (
        ensure_equipment_group_linked_to_station,
        linked_station_ids_for_equipment_group,
    )

    desired: list[int] = []
    seen: set[int] = set()
    for raw_id in desired_station_ids or []:
        if raw_id is None:
            continue
        sid = int(raw_id)
        if sid in seen:
            continue
        seen.add(sid)
        desired.append(sid)

    current_ids = linked_station_ids_for_equipment_group(equipment_group_id, version_id)
    current_set = set(current_ids)
    desired_set = set(desired)
    if loaded_station_ids is None:
        keep_hidden = set()
        to_unlink = current_set - desired_set
    else:
        loaded_set = {int(sid) for sid in loaded_station_ids if sid is not None}
        keep_hidden = current_set - loaded_set
        to_unlink = (loaded_set & current_set) - desired_set
    final_desired = list(desired)
    for sid in keep_hidden:
        if sid not in desired_set:
            final_desired.append(sid)
            desired_set.add(sid)

    type_id = equipment_group_type_id
    if type_id is None:
        type_id = _unique_type_id_from_group_sets(equipment_group_id, version_id)

    for sid in final_desired:
        created = ensure_equipment_group_linked_to_station(
            equipment_group_id=equipment_group_id,
            station_id=sid,
            version_id=version_id,
            equipment_group_type_id=type_id,
        )
        if created is None and sid not in current_set:
            return (
                "Не удалось создать привязку к выбранной станции. "
                "Укажите тип группы оборудования и сохраните."
            )

    for sid in to_unlink:
        _unlink_equipment_group_from_station(equipment_group_id, sid, version_id)
    return None


def _bind_equipment_group_grouping_station(
    equipment_group_id: int,
    new_station_id: int | None,
    *,
    version_id=None,
    equipment_group_type_id: int | None = None,
) -> str | None:
    """
    Привязывает группу к станции Generation: обновляет существующие связи
    EquipmentGroupSet или создаёт новую, если связей ещё нет.

    Для составной станции (ребёнок берёт Station родителя) — замена на одну
    станцию. Для карточки группы используйте sync_equipment_group_grouping_stations.
    """
    has_sets = (
        EquipmentGroupSet.query.filter_by(equipment_group_id=equipment_group_id).first()
        is not None
    )
    if has_sets:
        return _apply_grouping_station_on_type_station_links(
            equipment_group_id,
            new_station_id,
            version_id=version_id,
        )
    if new_station_id is None:
        return None

    from app.fuel.services.equipment_groups.equipment_group_rebind_services import (
        ensure_equipment_group_linked_to_station,
    )

    created = ensure_equipment_group_linked_to_station(
        equipment_group_id=equipment_group_id,
        station_id=new_station_id,
        version_id=version_id,
        equipment_group_type_id=equipment_group_type_id,
    )
    if created is None:
        return (
            "Не удалось создать привязку к выбранной станции. "
            "Укажите тип группы оборудования и сохраните."
        )
    return None


def persist_equipment_group_grouping_station_if_in_form(
    target_group: EquipmentGroup,
    form_data,
    *,
    version_id=None,
) -> str | None:
    """
    Если в form_data задан набор станций (grouping_station_ids) — синхронизирует
    связи группы со станциями Generation. Устаревший ключ grouping_station_id
    без списка только добавляет станцию, не снимая уже привязанные.

    version_id — версия БД целевой группы (для «сохранить во всех версиях»);
    станции из формы разрешаются по external_code.
    """
    if not form_data:
        return None

    has_sync = form_has_grouping_station_sync(form_data)
    has_legacy = "grouping_station_id" in form_data
    if not has_sync and not has_legacy:
        return None

    effective_vid = (
        version_id
        if version_id is not None
        else _effective_group_database_version_id(target_group)
    )
    type_id = _parse_int_form_id(form_data.get("equipment_group_type_id"))
    target_id = target_group.id

    def _resolve_or_skip(anchor_id: int) -> int | None:
        resolved = _resolve_grouping_station_id_for_db_version(anchor_id, effective_vid)
        if resolved is not None:
            return resolved
        if version_id is not None:
            return None
        return None

    if has_sync:
        anchors = grouping_station_ids_from_form(form_data)
        resolved_ids: list[int] = []
        unresolved = False
        for anchor in anchors:
            resolved = _resolve_grouping_station_id_for_db_version(anchor, effective_vid)
            if resolved is None:
                unresolved = True
                if version_id is None:
                    return "Выбранная станция для группировки не найдена в текущей версии БД."
                continue
            if resolved not in resolved_ids:
                resolved_ids.append(resolved)
        if anchors and unresolved and not resolved_ids and version_id is not None:
            return None
        loaded_ids = None
        if (
            "grouping_station_ids_loaded" in form_data
            or "grouping_station_ids_loaded_present" in form_data
        ):
            loaded_ids = []
            for anchor in grouping_station_ids_from_form(
                form_data, key="grouping_station_ids_loaded"
            ):
                resolved = _resolve_grouping_station_id_for_db_version(
                    anchor, effective_vid
                )
                if resolved is None:
                    if version_id is None:
                        loaded_ids.append(int(anchor))
                    continue
                if resolved not in loaded_ids:
                    loaded_ids.append(resolved)
        return sync_equipment_group_grouping_stations(
            target_id,
            resolved_ids,
            version_id=effective_vid,
            equipment_group_type_id=type_id,
            loaded_station_ids=loaded_ids,
        )

    grouping_station_val = form_data.get("grouping_station_id")
    anchor_grouping_station_id = _parse_int_form_id(grouping_station_val)
    if anchor_grouping_station_id is None:
        return None
    new_grouping_station_id = _resolve_or_skip(anchor_grouping_station_id)
    if new_grouping_station_id is None:
        if version_id is not None:
            return None
        return "Выбранная станция для группировки не найдена в текущей версии БД."
    from app.fuel.services.equipment_groups.equipment_group_rebind_services import (
        ensure_equipment_group_linked_to_station,
    )

    created = ensure_equipment_group_linked_to_station(
        equipment_group_id=target_id,
        station_id=new_grouping_station_id,
        version_id=effective_vid,
        equipment_group_type_id=type_id,
    )
    if created is None:
        return (
            "Не удалось создать привязку к выбранной станции. "
            "Укажите тип группы оборудования и сохраните."
        )
    return None


def update_equipment_group_from_form(equipment_group_id, form_data):
    """
    Обновляет EquipmentGroup из данных формы.
    При совпадении наименования с другой группой — объединяет дубликаты (как на station_details).
    Возвращает
    (success: bool, message: str, change_details: list[(field_label, old_val, new_val)], target_group_id: int|None).
    """
    from app.extensions import db
    from app.common.services.database_version_filter import get_current_db_version_id
    from app.fuel.services.equipment_groups.equipment_group_merge_services import (
        rename_or_merge_equipment_group_for_station,
        _EQUIPMENT_GROUP_FIELD_LABELS,
        _format_val_for_log,
    )

    group = EquipmentGroup.query.filter_by(id=equipment_group_id).first()
    if not group:
        return False, "Группа оборудования не найдена", [], None

    new_name = (form_data.get("name") or "").strip()
    current_version_id = get_current_db_version_id()
    station_id = _get_station_id_for_equipment_group(equipment_group_id)

    # Сначала объединяем дубликаты по имени (как на station_details)
    result = rename_or_merge_equipment_group_for_station(
        station_id=station_id,
        equipment_group_id=equipment_group_id,
        new_name=new_name or (group.name or "").strip(),
        current_version_id=current_version_id,
    )
    target_id = result["primary_id"] if result["merged"] else equipment_group_id

    # Применяем данные формы к целевой группе
    target_group = EquipmentGroup.query.filter_by(id=target_id).first()
    if not target_group:
        return False, "Группа оборудования не найдена", [], None

    def _parse_int(val):
        if not val or not str(val).strip():
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    group_version_id = getattr(target_group, "database_version_id", None)
    if "regional_district_id" in form_data:
        rd_val = form_data.get("regional_district_id")
        new_rd_id = _parse_int(rd_val)
        if new_rd_id is not None:
            resolved_rd, err = resolve_regional_district_id_for_db_version(
                new_rd_id, group_version_id
            )
            if err:
                db.session.rollback()
                return False, err, [], None
            new_rd_id = resolved_rd
    else:
        new_rd_id = target_group.regional_district_id

    if "regional_energy_system_id" in form_data:
        res_val = form_data.get("regional_energy_system_id")
        new_res_id = _parse_int(res_val)
        if new_res_id is not None:
            resolved_res, err = resolve_regional_energy_system_id_for_db_version(
                new_res_id, group_version_id
            )
            if err:
                db.session.rollback()
                return False, err, [], None
            new_res_id = resolved_res
    else:
        new_res_id = target_group.regional_energy_system_id

    if new_rd_id is not None:
        rd_obj = filter_by_explicit_db_version(
            RegionalDistrict.query,
            RegionalDistrict,
            group_version_id,
        ).filter(RegionalDistrict.id == new_rd_id).first()
        if rd_obj:
            allowed_res_ids = {
                res.id
                for res in (getattr(rd_obj, "regional_energy_systems", None) or [])
                if res.id is not None
            }
            if allowed_res_ids and new_res_id is not None and new_res_id not in allowed_res_ids:
                new_res_id = sorted(allowed_res_ids)[0]

    change_details = []

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
    for field in text_fields:
        val = form_data.get(field)
        if val is not None:
            new_val = val.strip() if val else None
            old_val = getattr(target_group, field, None)
            if old_val != new_val:
                setattr(target_group, field, new_val)
                label = _EQUIPMENT_GROUP_FIELD_LABELS.get(field, field)
                change_details.append((
                    label,
                    _format_val_for_log(old_val),
                    _format_val_for_log(new_val),
                ))

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
    for field in int_fields:
        if field not in form_data:
            continue
        new_val = _parse_int(form_data.get(field))
        old_val = getattr(target_group, field, None)
        if old_val != new_val:
            setattr(target_group, field, new_val)
            label = _EQUIPMENT_GROUP_FIELD_LABELS.get(field, field)
            change_details.append((
                label,
                _format_val_for_log(old_val),
                _format_val_for_log(new_val),
            ))

    # Валидация / синхронизация составности (comp/main) вместо «Станция для группировки».
    verr = _validate_and_sync_composite_fields(target_group)
    if verr:
        db.session.rollback()
        return False, verr, [], None

    def _format_fk_for_log(model_class, pk_id, name_attr="name"):
        """Форматирует FK для лога: название или ID, или —."""
        if pk_id is None:
            return "—"
        obj = model_class.query.get(pk_id)
        if obj and hasattr(obj, name_attr):
            return getattr(obj, name_attr) or str(pk_id)
        return str(pk_id)

    # regional_district_id и regional_energy_system_id (уже сопоставлены с версией БД группы)
    if new_rd_id != target_group.regional_district_id:
        old_val = target_group.regional_district_id
        target_group.regional_district_id = new_rd_id
        label = _EQUIPMENT_GROUP_FIELD_LABELS.get("regional_district_id", "regional_district_id")
        change_details.append((
            label,
            _format_fk_for_log(RegionalDistrict, old_val),
            _format_fk_for_log(RegionalDistrict, new_rd_id),
        ))

    if new_res_id != target_group.regional_energy_system_id:
        old_val = target_group.regional_energy_system_id
        target_group.regional_energy_system_id = new_res_id
        label = _EQUIPMENT_GROUP_FIELD_LABELS.get("regional_energy_system_id", "regional_energy_system_id")
        change_details.append((
            label,
            _format_fk_for_log(RegionalEnergySystem, old_val),
            _format_fk_for_log(RegionalEnergySystem, new_res_id),
        ))

    # Дочерняя группа: Субъект РФ / РЭС / obl с родителя по main, даже если в форме другое значение.
    from app.fuel.services.equipment_groups.composite_station_semantics import (
        is_composite_child_group,
    )

    if is_composite_child_group(target_group):
        before_rd = target_group.regional_district_id
        before_res = target_group.regional_energy_system_id
        before_obl = target_group.obl
        if target_group._apply_regional_ids_from_parent():
            if target_group.regional_district_id != before_rd:
                label = _EQUIPMENT_GROUP_FIELD_LABELS.get(
                    "regional_district_id", "regional_district_id"
                )
                change_details.append((
                    label,
                    _format_fk_for_log(RegionalDistrict, before_rd),
                    _format_fk_for_log(RegionalDistrict, target_group.regional_district_id),
                ))
            if target_group.regional_energy_system_id != before_res:
                label = _EQUIPMENT_GROUP_FIELD_LABELS.get(
                    "regional_energy_system_id", "regional_energy_system_id"
                )
                change_details.append((
                    label,
                    _format_fk_for_log(RegionalEnergySystem, before_res),
                    _format_fk_for_log(RegionalEnergySystem, target_group.regional_energy_system_id),
                ))
            if target_group.obl != before_obl:
                label = _EQUIPMENT_GROUP_FIELD_LABELS.get("obl", "obl")
                change_details.append((
                    label,
                    _format_val_for_log(before_obl),
                    _format_val_for_log(target_group.obl),
                ))

    egt_key = "equipment_group_type_id"
    if egt_key in form_data:
        egt_raw = form_data.get(egt_key)
        new_egt_id = _parse_int(egt_raw) if (egt_raw is not None and str(egt_raw).strip()) else None
        set_rows_egt = EquipmentGroupSet.query.filter_by(
            equipment_group_id=target_id
        ).all()
        needs_egt_change = False
        old_egt_ids: list[int | None] = []
        for s in set_rows_egt:
            lnk_egt = EquipmentGroupSetStation.query.get(
                s.equipment_group_set_station_id
            )
            if lnk_egt:
                old_egt_ids.append(lnk_egt.equipment_group_type_id)
                if lnk_egt.equipment_group_type_id != new_egt_id:
                    needs_egt_change = True
        if needs_egt_change and set_rows_egt:
            egt_err = _apply_equipment_group_type_change_from_form(
                target_id,
                new_egt_id,
                _effective_group_database_version_id(target_group),
            )
            if egt_err:
                db.session.rollback()
                return False, egt_err, [], None
            old_egt_labels = " / ".join(
                _format_fk_for_log(EquipmentGroupType, t)
                for t in sorted(set(old_egt_ids), key=lambda x: (x is None, x))
            ) or "—"
            change_details.append((
                "Тип группы оборудования (связь со станцией)",
                old_egt_labels,
                _format_fk_for_log(EquipmentGroupType, new_egt_id),
            ))

    if form_has_grouping_station_sync(form_data) or "grouping_station_id" in form_data:
        old_ids = _station_ids_from_group_set_rows(
            EquipmentGroupSet.query.filter_by(
                equipment_group_id=target_id
            ).all(),
            _effective_group_database_version_id(target_group),
        )
        gerr = persist_equipment_group_grouping_station_if_in_form(
            target_group, form_data
        )
        if gerr:
            db.session.rollback()
            return False, gerr, [], None
        new_ids = _station_ids_from_group_set_rows(
            EquipmentGroupSet.query.filter_by(
                equipment_group_id=target_id
            ).all(),
            _effective_group_database_version_id(target_group),
        )
        if old_ids != new_ids:
            change_details.append((
                "Привязка к станции (Модуль «Генерация»)",
                ", ".join(_format_fk_for_log(Station, sid) for sid in old_ids) or "не указано",
                ", ".join(_format_fk_for_log(Station, sid) for sid in new_ids) or "не указано",
            ))

    try:
        db.session.commit()
        if result["merged"]:
            return True, "Группа оборудования объединена с существующей группой с таким же наименованием.", change_details, target_id
        return True, "Данные успешно сохранены", change_details, target_id
    except Exception as e:
        db.session.rollback()
        return False, str(e), [], None


def _validate_and_sync_composite_fields(group: EquipmentGroup) -> str | None:
    """
    Проверяет comp/main и при MAIN>0 подтягивает Station родителя на связи ребёнка.
    Возвращает текст ошибки или None.
    """
    from app.extensions import db
    from app.fuel.services.equipment_groups.composite_station_semantics import (
        is_composite_parent_group,
        _as_int,
    )

    main = _as_int(getattr(group, "main", None))
    if main == 0:
        group.main = None
        main = None

    if is_composite_parent_group(group) and main is not None and main > 0:
        return "У родителя составной станции (comp=1) поле main должно быть пустым."

    if main is not None and main > 0:
        gvid = getattr(group, "database_version_id", None)

        def _parent_by_numb(numb: int):
            q = EquipmentGroup.query.filter(EquipmentGroup.numb == numb)
            if gvid is not None:
                q = q.filter(
                    (EquipmentGroup.database_version_id == gvid)
                    | (EquipmentGroup.database_version_id.is_(None))
                )
            return q.order_by(EquipmentGroup.id).first()

        parent = _parent_by_numb(main)
        # Частая ошибка UI: в main вводят id карточки родителя вместо его numb.
        if parent is None:
            by_id = EquipmentGroup.query.get(main)
            if by_id is not None and _as_int(getattr(by_id, "numb", None)):
                parent_numb = int(by_id.numb)
                resolved = _parent_by_numb(parent_numb)
                if resolved is not None:
                    group.main = parent_numb
                    parent = resolved

        if parent is None:
            return (
                f"Код родителя (main={main}): группа с numb={main} не найдена. "
                "В поле main нужен код родителя (numb), не id из URL."
            )

        # Синхронизация Station с родителя (машины/фильтры), не замена main.
        parent_station_id = _get_station_id_for_equipment_group(parent.id)
        if parent_station_id:
            resolved_station_id = _resolve_grouping_station_id_for_db_version(
                parent_station_id, gvid
            )
            if resolved_station_id:
                has_sets = (
                    EquipmentGroupSet.query.filter_by(equipment_group_id=group.id).first()
                    is not None
                )
                if has_sets:
                    egs_err = _apply_grouping_station_on_type_station_links(
                        group.id, resolved_station_id, version_id=gvid
                    )
                    if egs_err:
                        return egs_err
                else:
                    parent_type_id = None
                    parent_sets = EquipmentGroupSet.query.filter_by(
                        equipment_group_id=parent.id
                    ).all()
                    for parent_set in parent_sets:
                        parent_link = getattr(
                            parent_set, "equipment_group_set_station", None
                        )
                        if parent_link and parent_link.equipment_group_type_id:
                            parent_type_id = parent_link.equipment_group_type_id
                            break
                    from app.fuel.services.equipment_groups.equipment_group_rebind_services import (
                        ensure_equipment_group_linked_to_station,
                    )

                    ensure_equipment_group_linked_to_station(
                        equipment_group_id=group.id,
                        station_id=resolved_station_id,
                        version_id=gvid,
                        equipment_group_type_id=parent_type_id,
                    )
                db.session.flush()

        group._apply_regional_ids_from_parent(parent=parent)

    return None


def _delete_equipment_groups_by_ids(group_ids: list[int]) -> dict:
    """Удаляет группы оборудования вместе с зависимыми fuel-данными и связями."""
    from app.extensions import db
    from app.fuel.models.fue_equipment_group_coefficient_result_model import (
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
    from app.fuel.models.fue_equipment_group_fuel_param_model import (
        EquipmentGroupFuelParam,
    )
    from app.fuel.models.fue_equipment_group_heat_and_tariffs_model import (
        EquipmentGroupHeatAndTariffs,
    )
    from app.fuel.models.fue_equipment_group_natural_fuel_model import (
        EquipmentGroupNaturalFuel,
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

    group_ids = [gid for gid in dict.fromkeys(group_ids or []) if gid]
    if not group_ids:
        return {
            "deleted_groups": 0,
            "deleted_sets": 0,
            "deleted_set_stations": 0,
            "deleted_related_rows": 0,
        }

    # Все дочерние таблицы с ondelete=RESTRICT на equipment_group_id.
    detail_models = [
        EquipmentGroupFuelParam,
        EquipmentGroupExtraFuelParam,
        EquipmentGroupNaturalFuel,
        EquipmentGroupHeatAndTariffs,
        EquipmentGroupElectricityProductionCost,
        EquipmentGroupSpecificFuelConsumption,
        EquipmentGroupSpecificFuelCost,
        EquipmentGroupSpecificFuelPrice,
        EquipmentGroupFuelFormula,
        EquipmentGroupCoefficientResult,
    ]
    deleted_by_model = {}
    deleted_related_rows = 0
    for model in detail_models:
        deleted_count = (
            model.query.filter(model.equipment_group_id.in_(group_ids))
            .delete(synchronize_session=False)
        )
        deleted_by_model[model.__name__] = deleted_count
        deleted_related_rows += deleted_count

    sets = EquipmentGroupSet.query.filter(
        EquipmentGroupSet.equipment_group_id.in_(group_ids)
    ).all()
    orphan_link_ids = {
        row.equipment_group_set_station_id
        for row in sets
        if row.equipment_group_set_station_id
    }
    deleted_sets = (
        EquipmentGroupSet.query.filter(EquipmentGroupSet.equipment_group_id.in_(group_ids))
        .delete(synchronize_session=False)
    )

    deleted_set_stations = 0
    if orphan_link_ids:
        orphan_links = EquipmentGroupSetStation.query.filter(
            EquipmentGroupSetStation.id.in_(orphan_link_ids)
        ).all()
        for link in orphan_links:
            still_used = EquipmentGroupSet.query.filter_by(
                equipment_group_set_station_id=link.id
            ).first()
            if not still_used:
                db.session.delete(link)
                deleted_set_stations += 1

    deleted_groups = (
        EquipmentGroup.query.filter(EquipmentGroup.id.in_(group_ids))
        .delete(synchronize_session=False)
    )

    return {
        "deleted_groups": deleted_groups,
        "deleted_sets": deleted_sets,
        "deleted_set_stations": deleted_set_stations,
        "deleted_related_rows": deleted_related_rows,
        "deleted_by_model": deleted_by_model,
    }


def delete_equipment_group(equipment_group_id: int) -> dict:
    """Удаляет одну группу оборудования из текущей версии вместе с зависимыми данными."""
    group = EquipmentGroup.query.filter_by(id=equipment_group_id).first()
    if not group:
        return {"deleted_groups": 0, "not_found": True}

    result = _delete_equipment_groups_by_ids([equipment_group_id])
    result.update(
        {
            "group_name": (group.name or group.name_ext or "").strip(),
            "external_code": (group.external_code or "").strip(),
            "deleted_group_ids": [equipment_group_id],
        }
    )
    return result


def delete_equipment_group_all_versions(*, equipment_group_id: int) -> dict:
    """Удаляет эквивалентные группы оборудования во всех версиях БД по external_code."""
    current_group = EquipmentGroup.query.filter_by(id=equipment_group_id).first()
    if not current_group:
        return {"deleted_groups": 0, "not_found": True}

    group_name = (current_group.name or current_group.name_ext or "").strip()
    external_code = (current_group.external_code or "").strip()
    if not external_code:
        result = delete_equipment_group(equipment_group_id)
        result["fallback_single"] = True
        return result

    groups_to_delete = EquipmentGroup.query.filter_by(external_code=external_code).all()
    if not groups_to_delete:
        return {
            "deleted_groups": 0,
            "group_name": group_name,
            "external_code": external_code,
        }

    group_ids = [group.id for group in groups_to_delete if group.id]
    versions_touched = len(
        {
            getattr(group, "database_version_id", None)
            for group in groups_to_delete
        }
    )
    result = _delete_equipment_groups_by_ids(group_ids)
    result.update(
        {
            "group_name": group_name,
            "external_code": external_code,
            "deleted_group_ids": group_ids,
            "versions_touched": versions_touched,
        }
    )
    return result


def delete_station_equipment_group_type_station_links(
    *,
    station_id: int,
    equipment_group_set_station_ids: list,
    all_versions: bool = False,
) -> dict:
    """
    Удаляет строки EquipmentGroupSetStation («станция + тип группы») и связанные
    EquipmentGroupSet. Карточки EquipmentGroup не удаляет.

    Идентификаторы должны принадлежать station_id и входить в активный набор
    для текущей версии БД (та же логика отбора, что у списка связей электростанции).
    При all_versions=True дополнительно удаляются все EquipmentGroupSetStation
    с теми же парами (station_id, equipment_group_type_id) в любых версиях.
    """
    from app.extensions import db
    from app.common.services.database_version_filter import get_current_db_version_id

    parsed: list[int] = []
    for raw in equipment_group_set_station_ids or []:
        try:
            parsed.append(int(raw))
        except (TypeError, ValueError):
            return {"ok": False, "error": "invalid_id"}
    ids = sorted(set(parsed))
    if not ids:
        return {"ok": False, "error": "empty_ids"}

    current_version_id = get_current_db_version_id()

    def _filter_egs_by_version(items, version_id):
        if not items:
            return []
        if version_id is None:
            return [i for i in items if getattr(i, "database_version_id", None) is None]
        current_items = [
            i
            for i in items
            if getattr(i, "database_version_id", None) == version_id
        ]
        if current_items:
            return current_items
        return [i for i in items if getattr(i, "database_version_id", None) is None]

    raw_station_links = EquipmentGroupSetStation.query.filter(
        EquipmentGroupSetStation.station_id == station_id
    ).all()
    active_links = _filter_egs_by_version(raw_station_links, current_version_id)
    active_ids = {r.id for r in active_links}

    if not set(ids).issubset(active_ids):
        return {"ok": False, "error": "ids_not_in_active_version"}

    rows = [r for r in active_links if r.id in ids]
    if len(rows) != len(ids):
        return {"ok": False, "error": "row_load_mismatch"}

    if all_versions:
        targets_by_id: dict[int, EquipmentGroupSetStation] = {}
        for r in rows:
            for row in EquipmentGroupSetStation.query.filter(
                EquipmentGroupSetStation.station_id == r.station_id,
                EquipmentGroupSetStation.equipment_group_type_id
                == r.equipment_group_type_id,
            ).all():
                targets_by_id[row.id] = row
        targets = list(targets_by_id.values())
    else:
        targets = rows

    deleted_sets = 0
    for link in targets:
        deleted_sets += EquipmentGroupSet.query.filter_by(
            equipment_group_set_station_id=link.id
        ).delete(synchronize_session=False)
        db.session.delete(link)

    return {
        "ok": True,
        "deleted_set_stations": len(targets),
        "deleted_sets": deleted_sets,
        "all_versions": all_versions,
    }

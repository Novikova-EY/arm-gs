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


def _display_relevant_set_station_links(set_rows, preferred_version_id):
    """
    Возвращает связи EquipmentGroupSetStation для отображения карточки группы.

    Приоритет:
    1. Связи явной текущей/эффективной версии.
    2. Если таких нет, legacy-связи с database_version_id = NULL.
    3. Если и их нет, любые имеющиеся связи группы, чтобы карточка не выглядела пустой
       после merge между legacy/версионированными записями.
    """
    exact_links = []
    legacy_links = []
    other_links = []

    for es in set_rows or []:
        lnk = getattr(es, "equipment_group_set_station", None)
        if not lnk:
            continue
        link_vid = getattr(lnk, "database_version_id", None)
        if preferred_version_id is None:
            if link_vid is None:
                legacy_links.append(lnk)
            continue
        if link_vid == preferred_version_id:
            exact_links.append(lnk)
        elif link_vid is None:
            legacy_links.append(lnk)
        else:
            other_links.append(lnk)

    if exact_links:
        return exact_links
    if legacy_links:
        return legacy_links
    return other_links


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
    При нескольких связях (редко) — первая по порядку обхода.
    """
    relevant_links = _display_relevant_set_station_links(set_rows, group_version_id)
    for lnk in relevant_links:
        if lnk.station_id is not None:
            return lnk.station_id
    return None


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
    station_from_sets = _station_id_from_group_set_rows(set_rows, effective_vid)
    grouping_station_effective_id = station_from_sets
    station_q = filter_by_explicit_db_version(
        Station.query, Station, effective_vid
    ).order_by(Station.name, Station.id)
    all_stations = list(station_q.all())
    _station_ids = {s.id for s in all_stations}
    for extra_sid in (grouping_station_effective_id,):
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

    def _grouping_station_label_from_set_chain(sid) -> str | None:
        if sid is None:
            return None
        for lnk in display_links:
            if lnk.station_id != sid:
                continue
            st = lnk.station
            if st:
                return ((getattr(st, "name", None) or "—").strip() or "—")
        return None

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

    _gstation_display = _grouping_station_label_from_set_chain(grouping_station_effective_id)
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

    return {
        "equipment_group": group,
        "equipment_group_type_choices": equipment_group_type_choices,
        "equipment_group_type_selected": equipment_group_type_selected,
        "grouping_station_effective_id": grouping_station_effective_id,
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
    }


def _update_machines_id_equipment_group_for_fuel_group(
    equipment_group_id: int,
    station_id: int,
    old_type_id: int,
    new_type_id: int,
    version_id,
) -> None:
    """Обновляет Machine.id_equipment_group у агрегатов, привязанных к этой fuel-группе."""
    if old_type_id == new_type_id:
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
        .filter(
            Machine.id_station == station_id,
            Machine.id_equipment_group == old_type_id,
        )
    )
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
    new_type_id: int,
    group_version_id,
) -> str | None:
    """
    Меняет equipment_group_type_id у связей EquipmentGroupSetStation,
    ведущих к данной equipment group, на new_type_id. При необходимости переносит
    EquipmentGroupSet на существующую запись (station, type, version) и снимает дубликат.

    Синхронизирует Machine.id_equipment_group для агрегатов из этой fuel-группы.
    Возвращает None при успехе или строку с ошибкой.
    """
    from app.extensions import db

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

    changed_any = False
    for set_row in set_rows:
        old_link = EquipmentGroupSetStation.query.get(
            set_row.equipment_group_set_station_id
        )
        if not old_link:
            return "Связь станция — тип группы оборудования (EquipmentGroupSetStation) не найдена."
        st_id = old_link.station_id
        v_id = old_link.database_version_id
        old_tid = old_link.equipment_group_type_id
        if old_tid == new_type_id:
            continue

        _update_machines_id_equipment_group_for_fuel_group(
            equipment_group_id, st_id, old_tid, new_type_id, group_version_id
        )
        changed_any = True

        target = _find_equipment_group_set_station_link(st_id, new_type_id, v_id)

        if target is None or target.id == old_link.id:
            old_link.equipment_group_type_id = new_type_id
            db.session.add(old_link)
            db.session.flush()
            continue

        dup = (
            EquipmentGroupSet.query.filter_by(
                equipment_group_id=equipment_group_id,
                equipment_group_set_station_id=target.id,
            )
            .first()
        )
        if dup is not None and dup.id != set_row.id:
            db.session.delete(set_row)
        else:
            set_row.equipment_group_set_station_id = target.id
            db.session.add(set_row)
        db.session.flush()

        if _count_sets_using_link(old_link.id) == 0:
            db.session.delete(old_link)
        db.session.flush()

    return None


def _apply_grouping_station_on_type_station_links(
    equipment_group_id: int,
    new_station_id: int | None,
) -> str | None:
    """
    Записывает «Станция для группировки» в gs_fue_equipment_group_type_stations.station_id
    для всех связей EquipmentGroupSet данной группы. При конфликте уникального ключа
    переносит EquipmentGroupSet на существующую строку (station_id, type, version).
    """
    from app.extensions import db

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
        v_id = old_link.database_version_id
        if old_link.station_id == new_station_id:
            continue

        target = _find_equipment_group_set_station_link(new_station_id, type_id, v_id)

        if target is None:
            old_link_usage_count = _count_sets_using_link(old_link.id)
            if old_link_usage_count <= 1:
                old_link.station_id = new_station_id
                db.session.add(old_link)
                db.session.flush()
                continue

            # Не меняем shared link "на месте": иначе перенесутся все группы,
            # которые используют ту же строку связи station+type+version.
            target = EquipmentGroupSetStation(
                station_id=new_station_id,
                equipment_group_type_id=type_id,
                database_version_id=v_id,
            )
            db.session.add(target)
            db.session.flush()

            set_row.equipment_group_set_station_id = target.id
            db.session.add(set_row)
            db.session.flush()

            if _count_sets_using_link(old_link.id) == 0:
                db.session.delete(old_link)
                db.session.flush()
            continue

        if target.id == old_link.id:
            continue

        dup = (
            EquipmentGroupSet.query.filter_by(
                equipment_group_id=equipment_group_id,
                equipment_group_set_station_id=target.id,
            )
            .first()
        )
        if dup is not None and dup.id != set_row.id:
            db.session.delete(set_row)
        else:
            set_row.equipment_group_set_station_id = target.id
            db.session.add(set_row)
        db.session.flush()

        if _count_sets_using_link(old_link.id) == 0:
            db.session.delete(old_link)
        db.session.flush()

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


def persist_equipment_group_grouping_station_if_in_form(
    target_group: EquipmentGroup,
    form_data,
    *,
    version_id=None,
) -> str | None:
    """
    Если в form_data есть ключ grouping_station_id — валидирует станцию и обновляет
    gs_fue_equipment_group_type_stations.station_id (через связи EquipmentGroupSet).
    Иначе ничего не делает. Возвращает текст ошибки или None.

    version_id — версия БД целевой группы (для «сохранить во всех версиях»);
    станция из формы разрешается по external_code, как в update_equipment_group_all_versions.
    """
    if "grouping_station_id" not in form_data:
        return None

    def _parse_int(val):
        if not val or not str(val).strip():
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    grouping_station_val = form_data.get("grouping_station_id")
    anchor_grouping_station_id = _parse_int(grouping_station_val)
    effective_vid = (
        version_id
        if version_id is not None
        else _effective_group_database_version_id(target_group)
    )
    new_grouping_station_id = _resolve_grouping_station_id_for_db_version(
        anchor_grouping_station_id, effective_vid
    )

    if grouping_station_val is not None and anchor_grouping_station_id is not None:
        if new_grouping_station_id is None:
            if version_id is not None:
                return None
            return "Выбранная станция для группировки не найдена в текущей версии БД."

    target_id = target_group.id
    has_sets = (
        EquipmentGroupSet.query.filter_by(equipment_group_id=target_id).first()
        is not None
    )
    if has_sets:
        egs_err = _apply_grouping_station_on_type_station_links(
            target_id,
            new_grouping_station_id,
        )
        if egs_err:
            return egs_err

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

    egt_key = "equipment_group_type_id"
    if egt_key in form_data:
        egt_raw = form_data.get(egt_key)
        new_egt_id = _parse_int(egt_raw) if (egt_raw is not None and str(egt_raw).strip()) else None
        if new_egt_id is not None:
            set_rows_egt = EquipmentGroupSet.query.filter_by(
                equipment_group_id=target_id
            ).all()
            needs_egt_change = False
            old_egt_ids: list[int] = []
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
                    for t in sorted(set(old_egt_ids))
                ) or "—"
                change_details.append((
                    "Тип группы оборудования (связь со станцией)",
                    old_egt_labels,
                    _format_fk_for_log(EquipmentGroupType, new_egt_id),
                ))

    if "grouping_station_id" in form_data:
        old_eff_gs = _station_id_from_group_set_rows(
            EquipmentGroupSet.query.filter_by(
                equipment_group_id=target_id
            ).all(),
            _effective_group_database_version_id(target_group),
        )
        new_grouping_station_id = _parse_int(form_data.get("grouping_station_id"))
        gerr = persist_equipment_group_grouping_station_if_in_form(
            target_group, form_data
        )
        if gerr:
            db.session.rollback()
            return False, gerr, [], None
        if old_eff_gs != new_grouping_station_id:
            change_details.append((
                "Станция для группировки",
                _format_fk_for_log(Station, old_eff_gs),
                _format_fk_for_log(Station, new_grouping_station_id),
            ))

    try:
        db.session.commit()
        if result["merged"]:
            return True, "Группа оборудования объединена с существующей группой с таким же наименованием.", change_details, target_id
        return True, "Данные успешно сохранены", change_details, target_id
    except Exception as e:
        db.session.rollback()
        return False, str(e), [], None


def _delete_equipment_groups_by_ids(group_ids: list[int]) -> dict:
    """Удаляет группы оборудования вместе с зависимыми fuel-данными и связями."""
    from app.extensions import db
    from app.fuel.models.fue_equipment_group_coefficient_result_model import (
        EquipmentGroupCoefficientResult,
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

    detail_models = [
        EquipmentGroupFuelParam,
        EquipmentGroupExtraFuelParam,
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

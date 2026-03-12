#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сервисы для страницы «Топливные параметры групп оборудования» (v2)."""

from collections import defaultdict
from decimal import Decimal, InvalidOperation

from app.common.models.database_version_model import DatabaseVersion
from app.common.services.database_version_filter import (
    get_current_db_version_id,
    set_db_version_on_create,
)
from app.extensions import db
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.external_mapping.fue_em_business_unit_model import (
    BusinessUnitExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_equipment_group_model import (
    EquipmentGroupExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_department_model import (
    DepartmentExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_economic_region_model import (
    EconomicRegionExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_gen_company_model import (
    GenCompanyExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_territories_energy_model import (
    TerritoriesEnergyExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_union_energy_system_model import (
    UnionEnergySystemExternalMapping,
)

# Названия параметров для страницы equipment_group_details (как на stations_equipment_group_fuel_params)
FUEL_PARAM_LABELS = {
    "nust": "Руст", "nr": "Ррасп", "e": "Выр", "ewtp": "Этц", "eotp": "Отпуск ээ",
    "eurt": "Уд.расх ээ", "eust": "Расх топ ээ", "snk": "СН, %",
    "q": "Отпуск, Гкал", "qotr": "Отраб", "turt": "Уд.расх тэ", "tust": "Расх топ тэ", "sn_t": "СН, кВтч/Гкал",
    "b": "Расх топл.",
    "gaz": "Газ", "isk_gaz": "Иск. газ", "mazut": "Мазут", "torf": "Торф", "slan": "Сланцы",
    "proch": "Прочее", "ugol": "Уголь", "don": "Дон", "podm": "Подм", "pech": "Печ",
    "arkt": "Арктикуголь", "kuzn": "Кузбасс", "ural": "Урал", "bashk": "Башкортостан", "kazah": "Казахстан",
    "kan": "Канск", "tung": "Тунгусск", "irkut": "Иркутск", "hak": "Хакасия", "tuv": "Тува",
    "bur": "Бурятия", "chit": "Чита", "yakut": "Якутия", "amur": "Амур", "urg": "Юрга",
    "ushum": "Ушумун", "prim": "Приморье", "mag": "Магадан", "chukot": "Чукотка", "kamch": "Камчатка",
    "sah": "Сахалин",
    "nt": "Тепл. мощн. отборов", "nt_sum": "Сумма NT",
    "numb1120": "Код станции", "numb1": "Номер",
    "obor": "OBOR", "ved": "VED", "ved_cyrillic": "вед", "obl": "OBL", "dep": "DEP",
    "oes": "OES", "ees": "EES", "er": "ER", "gk": "GK", "be": "BE",
}

# Наименования для таблицы «Основные параметры» — как в разделе «Общая информация»
# на странице equipment_group_edit / stations_equipment_groups
MAIN_PARAM_LABELS = {
    "obor": "Группа оборудования (obor)",
    "ved": "Ведомство (ved)",
    "ved_cyrillic": "Ведомство (вед)",
    "obl": "Субъект РФ",
    "dep": "Департамент",
    "oes": "ОЭС",
    "ees": "Энергосистема (ees)",
    "er": "Экономический район",
    "gk": "Генерирующая компания",
    "be": "Тип генерирующей компании",
    "numb1120": "Код станции",
    "numb1": "Номер",
}


def _build_main_param_name_maps(params):
    """
    Строит справочники (id/код -> название) для полей obl, dep, oes, er, gk, be, obor.
    Использует отдельные запросы вместо ORM-relationship, чтобы избежать ошибок
    при несовпадении типов (varchar vs integer) в БД.
    """
    params = list(params) if params else []
    obl_ids = {str(p.obl) for p in params if getattr(p, "obl", None) is not None}
    dep_ids = {str(p.dep) for p in params if getattr(p, "dep", None) is not None}
    oes_ids = {str(p.oes) for p in params if getattr(p, "oes", None) is not None}
    er_ids = {str(p.er) for p in params if getattr(p, "er", None) is not None}
    gk_ids = {str(p.gk) for p in params if getattr(p, "gk", None) is not None}
    be_ids = {str(p.be) for p in params if getattr(p, "be", None) is not None}
    obor_ids = {p.obor for p in params if getattr(p, "obor", None) is not None}

    return {
        "obl": _build_obl_name_map_from_ids(obl_ids),
        "dep": _build_dep_name_map_from_ids(dep_ids),
        "oes": _build_oes_name_map_from_ids(oes_ids),
        "er": _build_er_name_map_from_ids(er_ids),
        "gk": _build_gk_name_map_from_ids(gk_ids),
        "be": _build_be_name_map_from_ids(be_ids),
        "obor": _build_obor_name_map_from_ids(obor_ids),
    }


def _resolve_main_param_display_value(attr, param, name_maps=None):
    """
    Возвращает отображаемое значение параметра (полное наименование по связанным моделям)
    вместо сырого ID/кода. Использует name_maps при наличии, чтобы избежать type mismatch
    (varchar = integer) при JOIN в БД.
    """
    if param is None:
        return None
    raw = getattr(param, attr, None)
    if raw is None and attr not in ("obor", "ved", "ved_cyrillic", "ees"):
        return None
    # Ведомство: 1 — станция отрасли, 2 — пром. предприятие
    if attr in ("ved", "ved_cyrillic"):
        if raw == 1:
            return "станция отрасли"
        if raw == 2:
            return "пром. предприятие"
        return str(raw) if raw is not None else None
    # Используем предпостроенные справочники (безопасно при несовпадении типов)
    if name_maps and attr in name_maps:
        key = str(raw) if attr != "obor" else raw
        resolved = name_maps[attr].get(key)
        return resolved or (str(raw) if raw is not None else None)
    if attr == "obor":
        m = getattr(param, "obor_equipment_group_mapping", None)
        return (m.gruppa_oborud if m else None) or (str(raw) if raw is not None else None)
    if attr == "obl":
        m = getattr(param, "obl_territories_energy", None)
        return (m.external_name if m else None) or (str(raw) if raw is not None else None)
    if attr == "dep":
        m = getattr(param, "dep_department_mapping", None)
        return (m.external_name if m else None) or (str(raw) if raw is not None else None)
    if attr == "oes":
        m = getattr(param, "oes_union_energy_system_mapping", None)
        return (m.external_nameoes or (m.external_name if m else None)) or (str(raw) if raw is not None else None)
    if attr == "er":
        m = getattr(param, "er_economic_region_mapping", None)
        return (m.external_name if m else None) or (str(raw) if raw is not None else None)
    if attr == "gk":
        m = getattr(param, "gk_gen_company_mapping", None)
        return (m.external_name if m else None) or (str(raw) if raw is not None else None)
    if attr == "be":
        m = getattr(param, "be_business_unit_mapping", None)
        return (m.external_name if m else None) or (str(raw) if raw is not None else None)
    # ees, numb1120, numb1 — без внешнего справочника
    return str(raw) if raw is not None else None

# Атрибуты для трёх таблиц на equipment_group_details (attr -> label из FUEL_PARAM_LABELS)
EQUIPMENT_GROUP_DETAILS_MAIN_ATTRS = [
    "obor", "ved", "ved_cyrillic", "obl", "dep", "oes", "ees", "er", "gk", "be",
    "numb1120", "numb1",
]
EQUIPMENT_GROUP_DETAILS_TABLE1_ATTRS = [
    "nust", "nr", "e", "eotp", "eurt", "eust", "q", "turt", "tust",
]
EQUIPMENT_GROUP_DETAILS_TABLE2_ATTRS = [
    "b", "gaz", "isk_gaz", "mazut", "torf", "slan", "proch", "ugol", "don", "podm",
    "pech", "arkt", "kuzn", "ural", "bashk", "kazah", "kan", "tung", "irkut", "hak",
    "tuv", "bur", "chit", "yakut", "amur", "urg", "ushum", "prim", "mag", "chukot",
    "kamch", "sah", "qotr", "snk", "sn_t", "ewtp", "nt", "nt_sum",
]

INTEGER_ATTRS = frozenset([
    "obor", "ved", "ved_cyrillic", "ees", "numb1120", "numb1",
])
STRING_ATTRS = frozenset(["obl", "dep", "oes", "er", "gk", "be"])
NUMERIC_ATTRS = frozenset(EQUIPMENT_GROUP_DETAILS_TABLE1_ATTRS + EQUIPMENT_GROUP_DETAILS_TABLE2_ATTRS)


def _parse_fuel_param_value(attr, value):
    """Парсит значение из формы для атрибута EquipmentGroupFuelParam."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    s = str(value).strip()
    if not s or s.lower() in ("nan", "—", "-", "–"):
        return None
    if attr in INTEGER_ATTRS:
        try:
            return int(Decimal(s))
        except (InvalidOperation, ValueError, TypeError):
            return None
    if attr in STRING_ATTRS:
        return s if s else None
    if attr in NUMERIC_ATTRS:
        try:
            return Decimal(s.replace(",", "."))
        except (InvalidOperation, ValueError, TypeError):
            return None
    return None


def update_equipment_group_fuel_params_from_form(
    equipment_group_id, form_data, start_year, end_year
):
    """
    Обновляет EquipmentGroupFuelParam из данных формы.
    Ожидает ключи вида: fuel_param_{year}_{attr}
    Возвращает (success: bool, message: str).
    """
    version_id = get_current_db_version_id()
    all_attrs = (
        EQUIPMENT_GROUP_DETAILS_MAIN_ATTRS
        + EQUIPMENT_GROUP_DETAILS_TABLE1_ATTRS
        + EQUIPMENT_GROUP_DETAILS_TABLE2_ATTRS
    )
    existing_params = {
        p.year_number: p
        for p in EquipmentGroupFuelParam.query.filter_by(
            equipment_group_id=equipment_group_id,
            database_version_id=version_id,
        ).all()
    }
    changes = 0
    for year in range(start_year, end_year + 1):
        param = existing_params.get(year)
        for attr in all_attrs:
            key = f"fuel_param_{year}_{attr}"
            raw = form_data.get(key)
            val = _parse_fuel_param_value(attr, raw)
            if param is None:
                if val is not None:
                    param = EquipmentGroupFuelParam(
                        equipment_group_id=equipment_group_id,
                        year_number=year,
                        database_version_id=version_id,
                    )
                    set_db_version_on_create(param)
                    db.session.add(param)
                    existing_params[year] = param
            if param is not None:
                old_val = getattr(param, attr, None)
                if old_val != val:
                    setattr(param, attr, val)
                    changes += 1
    return True, "Параметры успешно сохранены." if changes else "Изменений нет."


def load_equipment_group_fuel_params_for_groups(
    equipment_group_ids,
    start_year=None,
    end_year=None,
    version_id=None,
):
    """
    Загружает EquipmentGroupFuelParam для набора EquipmentGroup.id.
    Возвращает map: equipment_group_id -> list[EquipmentGroupFuelParam].
    """
    if not equipment_group_ids:
        return {}
    version_id = get_current_db_version_id() if version_id is None else version_id

    query = EquipmentGroupFuelParam.query.filter(
        EquipmentGroupFuelParam.equipment_group_id.in_(equipment_group_ids)
    )
    if start_year is not None:
        query = query.filter(EquipmentGroupFuelParam.year_number >= start_year)
    if end_year is not None:
        query = query.filter(EquipmentGroupFuelParam.year_number <= end_year)

    if version_id is None:
        query = query.filter(EquipmentGroupFuelParam.database_version_id.is_(None))
    else:
        query = query.filter(EquipmentGroupFuelParam.database_version_id == version_id)

    params = query.all()
    by_group = defaultdict(list)
    for p in params:
        by_group[p.equipment_group_id].append(p)
    return by_group


def attach_fuel_params_to_station_groups(stations, start_year=None, end_year=None):
    """
    Вешает fuel_params на элементы link в station.equipment_group_v2_groups.
    Параметры привязываются по equipment_group_id.
    """
    if not stations:
        return
    equipment_group_ids = []
    for station in stations:
        for group in getattr(station, "equipment_group_v2_groups", []) or []:
            eg = group.get("equipment_group")
            if eg and getattr(eg, "id", None):
                equipment_group_ids.append(eg.id)

    params_map = load_equipment_group_fuel_params_for_groups(
        equipment_group_ids, start_year=start_year, end_year=end_year
    )
    for station in stations:
        for group in getattr(station, "equipment_group_v2_groups", []) or []:
            eg = group.get("equipment_group")
            for link_item in group.get("links", []) or []:
                if not eg or getattr(eg, "id", None) is None:
                    link_item["fuel_params"] = []
                    continue
                params = params_map.get(eg.id, [])
                params_sorted = sorted(params, key=lambda p: p.year_number or 0)
                link_item["fuel_params"] = params_sorted


def _iter_fuel_params(stations):
    for station in stations or []:
        for group in getattr(station, "equipment_group_v2_groups", []) or []:
            for link_item in group.get("links", []) or []:
                for param in link_item.get("fuel_params", []) or []:
                    yield param


def _iter_params_from_rows(rows):
    """Итератор по fuel_param из списка (equipment_group, fuel_param)."""
    for _eg, param in rows or []:
        if param is not None:
            yield param


def _get_all_database_version_ids():
    """Возвращает список ID всех версий БД в системе (включая None для legacy)."""
    version_ids = [None]
    for dv in DatabaseVersion.query.filter(DatabaseVersion.id.isnot(None)).all():
        if dv.id:
            version_ids.append(dv.id)
    return version_ids


def get_equipment_groups_with_fuel_params_data(
    filters=None,
    per_page=10,
    page=1,
    start_year=None,
    end_year=None,
    show_all=False,
):
    """
    Выбирает позиции из gs_fue_equipment_groups с присоединением параметров
    gs_fue_equipment_group_fuel_param. Без постанционной логики.
    Отображаются только группы с текущей database_version_id.

    Возвращает:
        rows: list[(EquipmentGroup, EquipmentGroupFuelParam)]
        total_count: int
        total_pages: int
    """
    from sqlalchemy import or_, and_

    from app.common.services.get_services.years.years_get_services import (
        get_filter_start_year,
        get_filter_end_year,
    )
    from app.extensions import db
    from app.fuel.models.fue_equipment_group_model import EquipmentGroup

    _start = start_year if start_year is not None else get_filter_start_year()
    _end = end_year if end_year is not None else get_filter_end_year()
    current_version_id = get_current_db_version_id()

    # Join: param и group должны иметь совпадающую версию (или оба NULL)
    version_match = or_(
        and_(
            EquipmentGroupFuelParam.database_version_id == EquipmentGroup.database_version_id,
            EquipmentGroup.database_version_id.isnot(None),
        ),
        and_(
            EquipmentGroupFuelParam.database_version_id.is_(None),
            EquipmentGroup.database_version_id.is_(None),
        ),
    )
    join_cond = and_(
        EquipmentGroupFuelParam.equipment_group_id == EquipmentGroup.id,
        EquipmentGroupFuelParam.year_number >= _start,
        EquipmentGroupFuelParam.year_number <= _end,
        version_match,
    )

    base_query = (
        db.session.query(EquipmentGroup, EquipmentGroupFuelParam)
        .outerjoin(EquipmentGroupFuelParam, join_cond)
    )

    # Фильтр по версии БД: только текущая версия или только NULL (если версий нет)
    if hasattr(EquipmentGroup, "database_version_id"):
        if current_version_id is not None:
            base_query = base_query.filter(
                EquipmentGroup.database_version_id == current_version_id
            )
        else:
            base_query = base_query.filter(
                EquipmentGroup.database_version_id.is_(None)
            )

    # Территориальные фильтры (как на stations_equipment_groups)
    territorial_keys = (
        "energy_system_type_filter",
        "union_energy_system_filter",
        "regional_energy_system_filter",
        "federal_district_filter",
        "regional_district_filter",
    )
    _filters = {k: v for k, v in (filters or {}).items()
                if k not in ("page", "start_year", "end_year")}
    if any(_filters.get(k) for k in territorial_keys):
        from app.fuel.services.stations_equipment_groups_v2_services import (
            get_filtered_equipment_group_ids,
            get_filtered_standalone_equipment_group_ids,
        )
        filtered_ids = (
            get_filtered_equipment_group_ids(
                _filters, start_year=_start, end_year=_end
            )
            | get_filtered_standalone_equipment_group_ids(
                _filters,
                version_id=current_version_id,
                strict_version=True,
            )
        )
        if filtered_ids:
            base_query = base_query.filter(EquipmentGroup.id.in_(filtered_ids))
        else:
            base_query = base_query.filter(EquipmentGroup.id != EquipmentGroup.id)

    total_count = base_query.count()

    # Для иерархии EST→ОЭС→РЭС→группы пагинация по строкам разбивает блоки РЭС:
    # части групп одной РЭС оказываются на разных страницах. Поэтому загружаем все группы
    # без limit — каждая РЭС отображается полностью со всеми своими группами.
    from sqlalchemy.orm import selectinload

    from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem

    rows = (
        base_query
        .options(
            selectinload(EquipmentGroup.regional_energy_system).selectinload(
                RegionalEnergySystem.union_energy_system
            ),
        )
        .order_by(EquipmentGroup.name, EquipmentGroup.name_ext, EquipmentGroup.id)
        .all()
    )

    per_page_int = total_count or 1
    total_pages = 1

    return {
        "rows": rows,
        "total_count": total_count,
        "total_pages": total_pages,
        "page": 1,
        "per_page": per_page_int,
    }


def build_obor_name_map(stations):
    obor_ids = {p.obor for p in _iter_fuel_params(stations) if p.obor is not None}
    return _build_obor_name_map_from_ids(obor_ids)


def _build_obor_name_map_from_ids(obor_ids):
    if not obor_ids:
        return {}
    mappings = EquipmentGroupExternalMapping.query.filter(
        EquipmentGroupExternalMapping.code.in_(obor_ids)
    ).all()
    return {
        m.code: (m.gruppa_oborud or str(m.code))
        for m in mappings
        if m.code is not None
    }


def build_obl_name_map(stations):
    obl_ids = {p.obl for p in _iter_fuel_params(stations) if p.obl is not None}
    if not obl_ids:
        return {}
    obl_strs = [str(o) for o in obl_ids]
    mappings = TerritoriesEnergyExternalMapping.query.filter(
        TerritoriesEnergyExternalMapping.external_id.in_(obl_strs)
    ).all()
    return {
        m.external_id: (m.external_name or m.external_id)
        for m in mappings
        if m.external_id
    }


def build_dep_name_map(stations):
    dep_ids = {p.dep for p in _iter_fuel_params(stations) if p.dep is not None}
    if not dep_ids:
        return {}
    dep_strs = [str(d) for d in dep_ids]
    mappings = DepartmentExternalMapping.query.filter(
        DepartmentExternalMapping.external_id.in_(dep_strs)
    ).all()
    return {
        m.external_id: (m.external_name or m.external_id)
        for m in mappings
        if m.external_id
    }


def build_oes_name_map(stations):
    oes_ids = {p.oes for p in _iter_fuel_params(stations) if p.oes is not None}
    if not oes_ids:
        return {}
    oes_strs = [str(o) for o in oes_ids]
    mappings = UnionEnergySystemExternalMapping.query.filter(
        UnionEnergySystemExternalMapping.external_id.in_(oes_strs)
    ).all()
    return {
        m.external_id: (m.external_nameoes or m.external_name or m.external_id)
        for m in mappings
        if m.external_id
    }


def build_er_name_map(stations):
    er_ids = {p.er for p in _iter_fuel_params(stations) if p.er is not None}
    if not er_ids:
        return {}
    er_strs = [str(e) for e in er_ids]
    mappings = EconomicRegionExternalMapping.query.filter(
        EconomicRegionExternalMapping.external_id.in_(er_strs)
    ).all()
    return {
        m.external_id: (m.external_name or m.external_id)
        for m in mappings
        if m.external_id
    }


def build_gk_name_map(stations):
    gk_ids = {p.gk for p in _iter_fuel_params(stations) if p.gk is not None}
    if not gk_ids:
        return {}
    gk_strs = [str(g) for g in gk_ids]
    mappings = GenCompanyExternalMapping.query.filter(
        GenCompanyExternalMapping.external_id.in_(gk_strs)
    ).all()
    return {
        m.external_id: (m.external_name or m.external_id)
        for m in mappings
        if m.external_id
    }


def build_be_name_map(stations):
    be_ids = {p.be for p in _iter_fuel_params(stations) if p.be is not None}
    if not be_ids:
        return {}
    be_strs = [str(b) for b in be_ids]
    mappings = BusinessUnitExternalMapping.query.filter(
        BusinessUnitExternalMapping.external_id.in_(be_strs)
    ).all()
    return {
        m.external_id: (m.external_name or m.external_id)
        for m in mappings
        if m.external_id
    }


def _get_equipment_group_station_mapping(equipment_group_ids, all_versions=False):
    """
    Возвращает equipment_group_id -> list[(station_id, station_name)].
    Группа оборудования может быть привязана к нескольким станциям через EquipmentGroupSetStation.

    :param all_versions: если True, включать станции для всех версий БД (для страницы stations_equipment_group_fuel_params)
    """
    if not equipment_group_ids:
        return {}
    from sqlalchemy import or_

    from app.extensions import db
    from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
    from app.fuel.models.fue_equipment_group_set_station_model import (
        EquipmentGroupSetStation,
    )
    from app.generation.models.station.station_model import Station

    q = (
        db.session.query(
            EquipmentGroupSet.equipment_group_id,
            EquipmentGroupSetStation.station_id,
            Station.name,
        )
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSet.equipment_group_set_station_id == EquipmentGroupSetStation.id,
        )
        .join(Station, EquipmentGroupSetStation.station_id == Station.id)
        .filter(EquipmentGroupSet.equipment_group_id.in_(equipment_group_ids))
    )
    if not all_versions:
        version_id = get_current_db_version_id()
        if version_id is None:
            q = q.filter(EquipmentGroupSetStation.database_version_id.is_(None))
        else:
            q = q.filter(EquipmentGroupSetStation.database_version_id == version_id)
    else:
        all_version_ids = _get_all_database_version_ids()
        non_null_ids = [vid for vid in all_version_ids if vid is not None]
        if non_null_ids:
            q = q.filter(
                or_(
                    EquipmentGroupSetStation.database_version_id.in_(non_null_ids),
                    EquipmentGroupSetStation.database_version_id.is_(None),
                )
            )
        else:
            q = q.filter(EquipmentGroupSetStation.database_version_id.is_(None))
    rows = q.distinct().all()

    result = defaultdict(list)
    seen = set()
    for eg_id, st_id, st_name in rows:
        key = (eg_id, st_id)
        if key in seen:
            continue
        seen.add(key)
        result[eg_id].append((st_id, st_name or "—"))
    # Сортируем по имени станции для стабильного порядка
    for eg_id in result:
        result[eg_id].sort(key=lambda x: (x[1] or "").lower())
    return dict(result)


def build_equipment_group_fuel_params_hierarchy(rows, use_equipment_group_hierarchy_only=False):
    """
    Строит иерархию по группам оборудования: energy_system_type → UES → РЭС → станция → группа оборудования.

    Суммарные строки «станция, всего» показываются для групп, относящихся к одной станции.

    :param use_equipment_group_hierarchy_only: если True (для страницы stations_equipment_group_fuel_params),
        иерархия и агрегация строятся только через EquipmentGroup.regional_energy_system →
        RegionalEnergySystem.union_energy_system → UnionEnergySystem.id_energy_system_type.
        Без группировки по станции: est_id → ues_id → res_id → eg_id → rows.
    """
    from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
        get_energy_system_type_map,
    )
    from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
        get_regional_energy_systems_name_map,
    )
    from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
        get_union_energy_systems_map,
    )

    est_names = dict(get_energy_system_type_map())
    ues_names = dict(get_union_energy_systems_map())
    res_names = dict(get_regional_energy_systems_name_map())
    est_names[-1] = "Не указано"
    ues_names[-1] = "Не указано"
    res_names[-1] = "Не указано"

    equipment_group_ids = [eg.id for eg, _ in (rows or []) if eg]
    eg_to_stations = (
        _get_equipment_group_station_mapping(equipment_group_ids, all_versions=True)
        if not use_equipment_group_hierarchy_only
        else {}
    )

    # Собираем иерархию: est_id -> ues_id -> res_id -> eg_id -> rows
    hierarchy = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))

    for eg, param in rows or []:
        if not eg:
            continue
        # Для stations_equipment_group_fuel_params: всегда через EquipmentGroup.regional_energy_system.
        # Иначе: param (EquipmentGroupFuelParam) при наличии, fallback на eg.
        if use_equipment_group_hierarchy_only:
            res = getattr(eg, "regional_energy_system", None)
            ues = getattr(res, "union_energy_system", None) if res else None
            est_id = getattr(ues, "id_energy_system_type", None) if ues else None
        elif param:
            ues = param.union_energy_system
            res = param.regional_energy_system
            est_id = param.energy_system_type_id
        else:
            res = getattr(eg, "regional_energy_system", None)
            ues = getattr(res, "union_energy_system", None) if res else None
            est_id = getattr(ues, "id_energy_system_type", None) if ues else None
        ues_id = ues.id if ues else None
        res_id = res.id if res else None

        _est = est_id if est_id is not None else -1
        _ues = ues_id if ues_id is not None else -1
        _res = res_id if res_id is not None else -1

        hierarchy[_est][_ues][_res][eg.id].append((eg, param))

    def _sort_key_est(eid):
        return (1 if eid == -1 else 0, est_names.get(eid, ""))

    def _sort_key_ues(uid):
        return (1 if uid == -1 else 0, ues_names.get(uid, ""))

    def _sort_key_res(rid):
        return (1 if rid == -1 else 0, res_names.get(rid, ""))

    def _eg_sort_key(item):
        eg_id, eg_rows = item
        eg = eg_rows[0][0] if eg_rows else None
        name = (eg.name or eg.name_ext or "") if eg else ""
        return (0, (name or "").lower(), eg_id or 0)

    NUMERIC_FUEL_PARAM_ATTRS = [
        "nust", "nr", "e", "ewtp", "eotp", "eurt", "eust", "snk",
        "q", "qotr", "turt", "tust", "sn_t", "b",
        "gaz", "isk_gaz", "mazut", "torf", "slan", "proch", "ugol",
        "don", "podm", "pech", "arkt", "kuzn", "ural", "bashk", "kazah",
        "kan", "tung", "irkut", "hak", "tuv", "bur", "chit", "yakut",
        "amur", "urg", "ushum", "prim", "mag", "chukot", "kamch", "sah",
        "nt", "nt_sum",
    ]

    def _compute_summary(rows_to_sum):
        from decimal import Decimal
        summary = {}
        for attr in NUMERIC_FUEL_PARAM_ATTRS:
            total = Decimal(0)
            for _eg, param in rows_to_sum:
                val = getattr(param, attr, None)
                if val is not None:
                    try:
                        total += Decimal(str(val))
                    except (TypeError, ValueError):
                        pass
            summary[attr] = total
        return summary

    def _get_primary_station(eg_id):
        """Возвращает (station_id, station_name) для первой станции группы или None."""
        stations = eg_to_stations.get(eg_id, [])
        if not stations:
            return None
        st_id, st_name = stations[0]
        return (st_id, st_name or "—")

    def _station_sort_key(station_tuple):
        st_id, st_name = station_tuple or (None, "—")
        return (1 if st_id is None else 0, (st_name or "").lower(), st_id or 0)

    hierarchy_flat = []
    for est_id in sorted(hierarchy.keys(), key=_sort_key_est):
        ues_list = []
        for ues_id in sorted(hierarchy[est_id].keys(), key=_sort_key_ues):
            res_list = []
            for res_id in sorted(hierarchy[est_id][ues_id].keys(), key=_sort_key_res):
                all_res_rows = []
                eg_items = sorted(
                    hierarchy[est_id][ues_id][res_id].items(), key=_eg_sort_key
                )

                # Группируем по станции (если не use_equipment_group_hierarchy_only): station_key -> [(eg, rows), ...]
                # Для stations_equipment_group_fuel_params: одна «виртуальная» станция, без подуровня «станция, всего»
                by_station = defaultdict(list)
                for eg_id, eg_rows in eg_items:
                    all_res_rows.extend(eg_rows)
                    eg = eg_rows[0][0] if eg_rows else None
                    if use_equipment_group_hierarchy_only:
                        station_key = (None, "—")
                    else:
                        station_key = _get_primary_station(eg_id)
                    by_station[station_key].append({
                        "equipment_group": eg,
                        "rows": eg_rows,
                    })

                res_summary = _compute_summary(all_res_rows) if all_res_rows else {}

                station_blocks = []
                for station_key in sorted(by_station.keys(), key=_station_sort_key):
                    group_blocks = by_station[station_key]
                    station_rows = []
                    for gb in group_blocks:
                        station_rows.extend(gb["rows"])
                    station_summary = _compute_summary(station_rows) if station_rows else {}
                    st_id, st_name = station_key if station_key else (None, "—")
                    is_virtual = use_equipment_group_hierarchy_only
                    station_blocks.append({
                        "station_id": st_id,
                        "station_name": st_name,
                        "group_blocks": group_blocks,
                        "station_summary": station_summary,
                        "is_virtual": is_virtual,
                    })

                res_list.append({
                    "res_id": res_id,
                    "res_name": res_names.get(res_id, "—"),
                    "group_blocks": [gb for sb in station_blocks for gb in sb["group_blocks"]],
                    "station_blocks": station_blocks,
                    "res_summary": res_summary,
                })
            ues_list.append({
                "ues_id": ues_id,
                "ues_name": ues_names.get(ues_id, "—"),
                "res_list": res_list,
            })
        hierarchy_flat.append({
            "est_id": est_id,
            "est_name": est_names.get(est_id, "—"),
            "ues_list": ues_list,
        })

    return hierarchy_flat


def build_name_maps_from_rows(rows):
    """Строит все name_map из списка (equipment_group, fuel_param)."""
    params = list(_iter_params_from_rows(rows))
    obor_ids = {p.obor for p in params if p.obor is not None}
    obl_ids = {p.obl for p in params if p.obl is not None}
    dep_ids = {p.dep for p in params if p.dep is not None}
    oes_ids = {p.oes for p in params if p.oes is not None}
    er_ids = {p.er for p in params if p.er is not None}
    gk_ids = {p.gk for p in params if p.gk is not None}
    be_ids = {p.be for p in params if p.be is not None}

    return {
        "obor_name_map": _build_obor_name_map_from_ids(obor_ids),
        "obl_name_map": _build_obl_name_map_from_ids(obl_ids),
        "dep_name_map": _build_dep_name_map_from_ids(dep_ids),
        "oes_name_map": _build_oes_name_map_from_ids(oes_ids),
        "er_name_map": _build_er_name_map_from_ids(er_ids),
        "gk_name_map": _build_gk_name_map_from_ids(gk_ids),
        "be_name_map": _build_be_name_map_from_ids(be_ids),
    }


def _build_obl_name_map_from_ids(obl_ids):
    if not obl_ids:
        return {}
    obl_strs = [str(o) for o in obl_ids]
    mappings = TerritoriesEnergyExternalMapping.query.filter(
        TerritoriesEnergyExternalMapping.external_id.in_(obl_strs)
    ).all()
    return {m.external_id: (m.external_name or m.external_id) for m in mappings if m.external_id}


def _build_dep_name_map_from_ids(dep_ids):
    if not dep_ids:
        return {}
    dep_strs = [str(d) for d in dep_ids]
    mappings = DepartmentExternalMapping.query.filter(
        DepartmentExternalMapping.external_id.in_(dep_strs)
    ).all()
    return {m.external_id: (m.external_name or m.external_id) for m in mappings if m.external_id}


def _build_oes_name_map_from_ids(oes_ids):
    if not oes_ids:
        return {}
    oes_strs = [str(o) for o in oes_ids]
    mappings = UnionEnergySystemExternalMapping.query.filter(
        UnionEnergySystemExternalMapping.external_id.in_(oes_strs)
    ).all()
    return {m.external_id: (m.external_nameoes or m.external_name or m.external_id) for m in mappings if m.external_id}


def _build_er_name_map_from_ids(er_ids):
    if not er_ids:
        return {}
    er_strs = [str(e) for e in er_ids]
    mappings = EconomicRegionExternalMapping.query.filter(
        EconomicRegionExternalMapping.external_id.in_(er_strs)
    ).all()
    return {m.external_id: (m.external_name or m.external_id) for m in mappings if m.external_id}


def _build_gk_name_map_from_ids(gk_ids):
    if not gk_ids:
        return {}
    gk_strs = [str(g) for g in gk_ids]
    mappings = GenCompanyExternalMapping.query.filter(
        GenCompanyExternalMapping.external_id.in_(gk_strs)
    ).all()
    return {m.external_id: (m.external_name or m.external_id) for m in mappings if m.external_id}


def _build_be_name_map_from_ids(be_ids):
    if not be_ids:
        return {}
    be_strs = [str(b) for b in be_ids]
    mappings = BusinessUnitExternalMapping.query.filter(
        BusinessUnitExternalMapping.external_id.in_(be_strs)
    ).all()
    return {m.external_id: (m.external_name or m.external_id) for m in mappings if m.external_id}
